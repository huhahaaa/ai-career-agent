import json
from datetime import datetime, timezone
from typing import Any, Optional

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
    InterviewFinishResult,
    InterviewQuestion,
    InterviewStartRequest,
)
from app.services.agent_logging import agent_operation_log
from app.services.interview_agent import evaluate_answer, finish_interview, start_interview

router = APIRouter()

AGENT_STATE_TYPE = "interview_agent_state"


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


def _state_to_content(state: dict[str, Any]) -> str:
    return json.dumps(
        {
            "type": AGENT_STATE_TYPE,
            "state": state,
        },
        ensure_ascii=False,
    )


def _state_message(session: InterviewSession) -> InterviewMessage | None:
    for message in sorted(session.messages, key=lambda item: item.id or 0):
        if message.role != "system":
            continue
        try:
            payload = json.loads(message.content)
        except json.JSONDecodeError:
            continue
        if payload.get("type") == AGENT_STATE_TYPE:
            return message
    return None


def _load_agent_state(session: InterviewSession) -> dict[str, Any]:
    message = _state_message(session)
    if message is not None:
        try:
            payload = json.loads(message.content)
        except json.JSONDecodeError:
            payload = {}
        state = payload.get("state")
        if isinstance(state, dict):
            return state

    fallback_question = session.current_question or "请做一个简短的自我介绍。"
    return {
        "version": 1,
        "target_position": session.target_job.title if session.target_job else "",
        "target_job_id": str(session.target_job_id or ""),
        "questions": [fallback_question],
        "current_index": 0,
        "answers": [{}],
        "status": "in_progress",
    }


def _save_agent_state(
    db: Session,
    session: InterviewSession,
    state: dict[str, Any],
) -> None:
    message = _state_message(session)
    if message is None:
        db.add(
            InterviewMessage(
                session_id=session.id,
                role="system",
                content=_state_to_content(state),
            )
        )
        return
    message.content = _state_to_content(state)


def _average_score_from_state(state: dict[str, Any]) -> int | None:
    totals = []
    for answer in state.get("answers", []):
        scores = answer.get("scores") if isinstance(answer, dict) else None
        if isinstance(scores, dict) and isinstance(scores.get("total"), (int, float)):
            totals.append(scores["total"])
    if not totals:
        return None
    return round(sum(totals) / len(totals))


def _session_summary(session: InterviewSession) -> dict:
    state = _load_agent_state(session)
    user_messages = [message for message in session.messages if message.role == "user"]
    answered_count = len(
        [
            answer
            for answer in state.get("answers", [])
            if isinstance(answer, dict) and answer.get("scores")
        ]
    )
    score = session.score
    if score is None:
        score = _average_score_from_state(state) or 0

    company = session.target_job.company if session.target_job else "目标岗位"
    job_title = (
        session.target_job.title
        if session.target_job
        else state.get("target_position") or "综合面试"
    )
    duration = 0
    if session.created_at and session.updated_at:
        try:
            duration = max(
                0,
                round((session.updated_at - session.created_at).total_seconds() / 60),
            )
        except TypeError:
            duration = 0

    completed_report = state.get("completed_report")
    report_summary = ""
    if isinstance(completed_report, dict):
        report_summary = completed_report.get("summary", "")

    return {
        "id": session.id,
        "company": company,
        "job_title": job_title,
        "mode": "Agent 模拟面试",
        "score": score,
        "duration_minutes": duration,
        "questions_count": answered_count or len(user_messages),
        "status": state.get("status", session.status),
        "created_at": session.created_at,
        "feedback": {
            "overall": report_summary or session.feedback or "暂无总体评价",
            "strengths": ["已完成结构化评分"] if score else [],
            "weaknesses": ["建议补充 STAR 结构、技术细节和量化结果"] if score else [],
        },
    }


def _visible_messages(session: InterviewSession) -> list[dict]:
    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "score": message.score,
            "feedback": message.feedback,
            "created_at": message.created_at,
        }
        for message in sorted(session.messages, key=lambda item: item.id or 0)
        if message.role != "system"
    ]


@router.post("/start", response_model=ApiResponse[InterviewQuestion])
def start(
    payload: InterviewStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[InterviewQuestion]:
    with agent_operation_log(
        db,
        user_id=current_user.id,
        operation="interview.start",
        request_summary={
            "target_position": payload.target_position,
            "target_job_id": payload.target_job_id,
            "resume_chars": len(payload.resume_text),
        },
    ) as log_context:
        result = start_interview(
            resume_text=payload.resume_text,
            target_position=payload.target_position,
            target_job_id=payload.target_job_id,
        )
        log_context["response_summary"] = {
            "question": result["question"],
            "total_questions": result.get("total_questions"),
            "tools_used": result.get("tools_used", []),
        }
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
    _save_agent_state(db, session, result["agent_state"])
    db.add(
        InterviewMessage(
            session_id=session.id,
            role="assistant",
            content=result["question"],
        )
    )
    db.commit()
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

    state = _load_agent_state(interview_session)
    with agent_operation_log(
        db,
        user_id=current_user.id,
        operation="interview.answer",
        request_summary={
            "session_id": session_id,
            "answer_chars": len(payload.answer),
            "question_index": state.get("current_index", 0),
        },
    ) as log_context:
        result = evaluate_answer(session_state=state, answer=payload.answer)
        log_context["response_summary"] = {
            "is_followup": result.get("is_followup"),
            "score": result.get("score"),
            "session_status": result.get("session_status"),
            "current_index": result.get("current_index"),
        }
    state = result["agent_state"]

    db.add(
        InterviewMessage(
            session_id=interview_session.id,
            role="user",
            content=payload.answer,
            score=result["score"],
            feedback=result["feedback"] or "",
        )
    )

    assistant_message = (
        result["followup_question"] if result["is_followup"] else result["next_question"]
    )
    if assistant_message:
        db.add(
            InterviewMessage(
                session_id=interview_session.id,
                role="assistant",
                content=assistant_message,
            )
        )

    interview_session.current_question = assistant_message or ""
    if result["score"] is not None:
        interview_session.score = _average_score_from_state(state)
        interview_session.feedback = result["feedback"] or ""
    interview_session.updated_at = datetime.now(timezone.utc)
    _save_agent_state(db, interview_session, state)
    db.commit()

    public_result = {key: value for key, value in result.items() if key != "agent_state"}
    return success_response(InterviewAnswerResult.model_validate(public_result))


@router.post(
    "/{session_id}/finish",
    response_model=ApiResponse[InterviewFinishResult],
)
def finish(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[InterviewFinishResult]:
    session = db.get(InterviewSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise AppException(404, 40402, "interview session not found")

    state = _load_agent_state(session)
    with agent_operation_log(
        db,
        user_id=current_user.id,
        operation="interview.finish",
        request_summary={"session_id": session_id},
    ) as log_context:
        report = finish_interview(session_state=state, session_id=session.id)
        log_context["response_summary"] = {
            "overall_score": report.get("overall_score"),
            "total_questions_answered": report.get("total_questions_answered"),
        }
    session.status = "completed"
    session.score = int(round(report["overall_score"]))
    session.feedback = report["summary"]
    session.current_question = ""
    session.updated_at = datetime.now(timezone.utc)
    _save_agent_state(db, session, state)
    db.commit()
    return success_response(InterviewFinishResult.model_validate(report))


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

    state = _load_agent_state(session)
    summary = _session_summary(session)
    summary["messages"] = _visible_messages(session)
    summary["agent_report"] = state.get("completed_report")
    summary["total_questions"] = len(state.get("questions", []))
    return success_response(summary)
