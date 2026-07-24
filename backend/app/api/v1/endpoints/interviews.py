from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import AppException
from app.db.session import get_db
from app.models.interview import InterviewMessage, InterviewSession
from app.models.job import JobPosting
from app.models.resume import Resume, ResumeVersion
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.interview import (
    InterviewAnswerRequest,
    InterviewAnswerResult,
    InterviewQuestion,
    InterviewStartRequest,
)
from app.services.interview_agent import evaluate_answer, start_interview

router = APIRouter()


def _coerce_database_job_id(value: object) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _create_resume_snapshot(db: Session, user: User, resume_text: str) -> Resume:
    resume = Resume(
        user_id=user.id,
        title="模拟面试简历快照",
        current_version_number=1,
    )
    db.add(resume)
    db.flush()
    db.add(
        ResumeVersion(
            resume_id=resume.id,
            version_number=1,
            file_name="interview-input.txt",
            file_path="",
            content=resume_text,
        )
    )
    return resume


def _resolve_target_job_id(db: Session, value: object) -> Optional[int]:
    job_id = _coerce_database_job_id(value)
    if job_id is None:
        return None
    return job_id if db.get(JobPosting, job_id) is not None else None


def _session_summary(session: InterviewSession) -> dict:
    user_messages = [message for message in session.messages if message.role == "user"]
    score = session.score if session.score is not None else 0
    company = session.target_job.company if session.target_job else "目标岗位"
    job_title = session.target_job.title if session.target_job else "综合面试"
    if session.current_question:
        job_title = session.target_job.title if session.target_job else session.current_question[:32]
    duration = 0
    if session.created_at and session.updated_at:
        try:
            duration = max(
                0,
                round((session.updated_at - session.created_at).total_seconds() / 60),
            )
        except TypeError:
            duration = 0
    return {
        "id": session.id,
        "company": company,
        "job_title": job_title,
        "mode": "基础模拟面试",
        "score": score,
        "duration_minutes": duration,
        "questions_count": len(user_messages),
        "status": session.status,
        "created_at": session.created_at,
        "feedback": {
            "overall": session.feedback or "暂无总体评价",
            "strengths": ["回答已完成基础评分"] if score else [],
            "weaknesses": ["建议补充具体场景、行动和量化结果"] if score else [],
        },
    }


@router.post("/start", response_model=ApiResponse[InterviewQuestion])
def start(
    payload: InterviewStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[InterviewQuestion]:
    result = start_interview(
        resume_text=payload.resume_text,
        target_position=payload.target_position,
        target_job_id=payload.target_job_id,
    )
    resume = _create_resume_snapshot(db, current_user, payload.resume_text)
    session = InterviewSession(
        user_id=current_user.id,
        resume_id=resume.id,
        target_job_id=_resolve_target_job_id(db, payload.target_job_id),
        current_question=result["question"],
        status="running",
    )
    db.add(session)
    db.flush()
    db.add(
        InterviewMessage(
            session_id=session.id,
            role="assistant",
            content=result["question"],
        )
    )
    db.commit()
    db.refresh(session)
    result["session_id"] = str(session.id)
    return success_response(InterviewQuestion.model_validate(result))


@router.post(
    "/{session_id}/answer",
    response_model=ApiResponse[InterviewAnswerResult],
)
def answer(
    session_id: str,
    payload: InterviewAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[InterviewAnswerResult]:
    database_session_id = _coerce_database_job_id(session_id)
    if database_session_id is None:
        raise AppException(404, 40402, "interview session not found")
    interview_session = db.get(InterviewSession, database_session_id)
    if interview_session is None or interview_session.user_id != current_user.id:
        raise AppException(404, 40402, "interview session not found")

    result = evaluate_answer(session_id=session_id, answer=payload.answer)
    db.add(
        InterviewMessage(
            session_id=interview_session.id,
            role="user",
            content=payload.answer,
            score=result["score"],
            feedback=result["feedback"],
        )
    )
    db.add(
        InterviewMessage(
            session_id=interview_session.id,
            role="assistant",
            content=result["next_question"],
        )
    )
    interview_session.current_question = result["next_question"]
    interview_session.score = result["score"]
    interview_session.feedback = result["feedback"]
    interview_session.updated_at = datetime.now(timezone.utc)
    db.commit()
    return success_response(InterviewAnswerResult.model_validate(result))


@router.get("/history", response_model=ApiResponse[list[dict]])
def history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    sessions = db.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
    ).all()
    return success_response([_session_summary(session) for session in sessions])


@router.get("/{session_id}/report", response_model=ApiResponse[dict])
def report(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    session = db.get(InterviewSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise AppException(404, 40402, "interview session not found")
    summary = _session_summary(session)
    summary["messages"] = [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "score": message.score,
            "feedback": message.feedback,
            "created_at": message.created_at,
        }
        for message in session.messages
    ]
    return success_response(summary)
