import re
from collections import Counter
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
from app.models.resume import RESUME_SOURCE_INTERVIEW_SNAPSHOT, Resume
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
from app.services.interview_summary import (
    average_score_from_state,
    is_effective_interview_session,
    load_agent_state,
    save_agent_state,
    session_summary,
    visible_messages,
)
from app.services.resume_selection import (
    create_resume_snapshot,
    get_user_formal_resume,
    resume_current_text,
)

router = APIRouter()

def _coerce_database_job_id(value: object) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_interview_resume(
    db: Session,
    user: User,
    payload: InterviewStartRequest,
) -> tuple[str, Resume]:
    if payload.resume_id is not None:
        resume = get_user_formal_resume(db, user, payload.resume_id)
        resume_text = resume_current_text(resume).strip()
        if len(resume_text) < 10:
            raise AppException(422, 42205, "selected resume has no usable text")
        return resume_text, resume

    resume_text = (payload.resume_text or "").strip()
    if len(resume_text) < 10:
        raise AppException(422, 42206, "resume_text or resume_id is required")
    resume = create_resume_snapshot(
        db,
        user,
        title="模拟面试简历快照",
        file_name="interview-input.txt",
        content=resume_text,
        source_type=RESUME_SOURCE_INTERVIEW_SNAPSHOT,
    )
    return resume_text, resume


def _resolve_target_job_id(db: Session, value: object) -> Optional[int]:
    job_id = _coerce_database_job_id(value)
    if job_id is None:
        return None
    return job_id if db.get(JobPosting, job_id) is not None else None


@router.post("/start", response_model=ApiResponse[InterviewQuestion])
def start(
    payload: InterviewStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[InterviewQuestion]:
    resume_text, resume = _resolve_interview_resume(db, current_user, payload)
    with agent_operation_log(
        db,
        user_id=current_user.id,
        operation="interview.start",
        request_summary={
            "target_position": payload.target_position,
            "target_job_id": payload.target_job_id,
            "interview_mode": payload.interview_mode,
            "resume_chars": len(resume_text),
            "resume_id": payload.resume_id,
        },
    ) as log_context:
        result = start_interview(
            resume_text=resume_text,
            target_position=payload.target_position,
            target_job_id=payload.target_job_id,
            interview_mode=payload.interview_mode,
        )
        log_context["response_summary"] = {
            "question": result["question"],
            "interview_mode": result.get("interview_mode"),
            "position_bucket": result.get("position_bucket"),
            "total_questions": result.get("total_questions"),
            "tools_used": result.get("tools_used", []),
        }
    session = InterviewSession(
        user_id=current_user.id,
        resume_id=resume.id,
        target_job_id=_resolve_target_job_id(db, payload.target_job_id),
        current_question=result["question"],
        status="running",
    )
    db.add(session)
    db.flush()
    save_agent_state(db, session, result["agent_state"])
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

    state = load_agent_state(interview_session)
    with agent_operation_log(
        db,
        user_id=current_user.id,
        operation="interview.answer",
        request_summary={
            "session_id": session_id,
            "answer_chars": len(payload.answer),
            "question_index": state.get("current_index", 0),
            "interview_mode": state.get("interview_mode", "技术面"),
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
        interview_session.score = average_score_from_state(state)
        interview_session.feedback = result["feedback"] or ""
    interview_session.updated_at = datetime.now(timezone.utc)
    save_agent_state(db, interview_session, state)
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

    state = load_agent_state(session)
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
    save_agent_state(db, session, state)
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
    return success_response(
        [
            session_summary(session)
            for session in sessions
            if is_effective_interview_session(session)
        ]
    )


def _split_practice_actions(text: str) -> list[str]:
    parts = [
        item.strip(" -•\t\r\n")
        for item in re.split(r"[\n;；]", text or "")
    ]
    return [item for item in parts if item][:6]


def _weak_dimensions(dimension_averages: dict) -> list[dict]:
    rows = []
    for name, value in dimension_averages.items():
        if name == "total" or not isinstance(value, (int, float)):
            continue
        rows.append({"name": name, "score": round(float(value), 1)})
    return sorted(rows, key=lambda item: item["score"])[:3]


@router.get("/training-plan", response_model=ApiResponse[dict])
def training_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    sessions = db.scalars(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == current_user.id,
            InterviewSession.status == "completed",
        )
        .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
    ).all()
    plans = []
    dimension_counter: Counter[str] = Counter()
    scored_sessions = []
    for session in sessions:
        if not is_effective_interview_session(session):
            continue
        state = load_agent_state(session)
        report = state.get("completed_report") if isinstance(state, dict) else None
        if not isinstance(report, dict):
            report = {}
        dimensions = _weak_dimensions(report.get("dimension_averages", {}) or {})
        for item in dimensions:
            dimension_counter[item["name"]] += 1
        actions = _split_practice_actions(report.get("practice_plan", ""))
        if not actions:
            actions = ["补充 STAR 结构、技术细节、个人贡献和量化结果。"]
        summary = session_summary(session)
        scored_sessions.append(summary)
        plans.append(
            {
                "session_id": session.id,
                "job_title": summary["job_title"],
                "company": summary["company"],
                "mode": summary["mode"],
                "score": summary["score"],
                "created_at": session.created_at,
                "weak_dimensions": dimensions,
                "practice_actions": actions,
                "star_suggestions": report.get("star_suggestions", []),
                "summary": report.get("summary") or session.feedback,
            }
        )

    avg_score = (
        round(sum(item["score"] for item in scored_sessions if item["score"] is not None) / len(scored_sessions), 1)
        if scored_sessions
        else None
    )
    return success_response(
        {
            "total_completed": len(plans),
            "average_score": avg_score,
            "latest_score": plans[0]["score"] if plans else None,
            "priority_dimensions": [
                {"name": name, "count": count}
                for name, count in dimension_counter.most_common(5)
            ],
            "plans": plans,
        }
    )


@router.get("/{session_id}/report", response_model=ApiResponse[dict])
def report(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    session = db.get(InterviewSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise AppException(404, 40402, "interview session not found")

    state = load_agent_state(session)
    summary = session_summary(session)
    summary["messages"] = visible_messages(session)
    summary["agent_report"] = state.get("completed_report")
    summary["total_questions"] = len(state.get("questions", []))
    return success_response(summary)
