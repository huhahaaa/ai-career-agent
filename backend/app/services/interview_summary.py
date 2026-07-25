import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.interview import InterviewMessage, InterviewSession

AGENT_STATE_TYPE = "interview_agent_state"


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


def load_agent_state(session: InterviewSession) -> dict[str, Any]:
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
        "interview_mode": "技术面",
    }


def save_agent_state(
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


def average_score_from_state(state: dict[str, Any]) -> int | None:
    totals = []
    for answer in state.get("answers", []):
        scores = answer.get("scores") if isinstance(answer, dict) else None
        if isinstance(scores, dict) and isinstance(scores.get("total"), (int, float)):
            totals.append(scores["total"])
    if not totals:
        return None
    return round(sum(totals) / len(totals))


def user_answer_count(session: InterviewSession) -> int:
    return len([message for message in session.messages if message.role == "user"])


def scored_answer_count(state: dict[str, Any]) -> int:
    return len(
        [
            answer
            for answer in state.get("answers", [])
            if isinstance(answer, dict) and answer.get("scores")
        ]
    )


def is_effective_interview_session(session: InterviewSession) -> bool:
    return (
        session.status == "completed"
        and session.score is not None
        and user_answer_count(session) > 0
    )


def session_duration_minutes(
    session: InterviewSession,
    status: str | None = None,
) -> int | None:
    if status != "completed":
        return None
    if not session.created_at or not session.updated_at:
        return None
    try:
        return max(
            0,
            round((session.updated_at - session.created_at).total_seconds() / 60),
        )
    except TypeError:
        return None


def session_summary(session: InterviewSession) -> dict:
    state = load_agent_state(session)
    user_messages_count = user_answer_count(session)
    answered_count = scored_answer_count(state)
    status = state.get("status", session.status)
    has_effective_answer = status == "completed" and user_messages_count > 0
    score = session.score if has_effective_answer else None
    if score is None and has_effective_answer:
        score = average_score_from_state(state)

    completed_report = state.get("completed_report")
    report_summary = ""
    if isinstance(completed_report, dict):
        report_summary = completed_report.get("summary", "")

    return {
        "id": session.id,
        "company": session.target_job.company if session.target_job else "目标岗位",
        "job_title": (
            session.target_job.title
            if session.target_job
            else state.get("target_position") or "综合面试"
        ),
        "mode": state.get("interview_mode", "Agent 模拟面试"),
        "score": score,
        "duration_minutes": session_duration_minutes(
            session,
            status if has_effective_answer else None,
        ),
        "questions_count": answered_count or user_messages_count,
        "status": status,
        "created_at": session.created_at,
        "feedback": {
            "overall": report_summary or session.feedback or "暂无总体评价",
            "strengths": ["已完成结构化评分"] if score else [],
            "weaknesses": ["建议补充 STAR 结构、技术细节和量化结果"] if score else [],
        },
    }


def dashboard_interview_summary(session: InterviewSession) -> dict:
    is_effective = is_effective_interview_session(session)
    return {
        "id": session.id,
        "company": session.target_job.company if session.target_job else "目标岗位",
        "job_title": session.target_job.title if session.target_job else "综合面试",
        "mode": "Agent 模拟面试",
        "score": session.score if is_effective else None,
        "duration_minutes": session_duration_minutes(
            session,
            session.status if is_effective else None,
        ),
        "status": session.status,
        "created_at": session.created_at,
    }


def visible_messages(session: InterviewSession) -> list[dict]:
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
