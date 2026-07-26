import json
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.dependencies import require_roles
from app.db.session import get_db
from app.models.agent_log import AgentLog
from app.models.interview import InterviewSession
from app.models.job import JobPosting
from app.models.matching import MatchingRecord
from app.models.resume import RESUME_SOURCE_FORMAL, Resume, ResumeAuditReport
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.services.interview_summary import (
    dashboard_interview_summary,
    is_effective_interview_session,
)
from app.services.knowledge_base import knowledge_overview
from app.services.resume_selection import (
    current_resume_version,
    get_default_resume,
)
router = APIRouter()

SKILL_KEYWORDS = [
    "Python",
    "FastAPI",
    "SQL",
    "SQLite",
    "MySQL",
    "React",
    "Vue",
    "JavaScript",
    "TypeScript",
    "Git",
    "Docker",
    "Redis",
    "MongoDB",
    "LLM",
    "RAG",
    "Agent",
    "Embedding",
    "Chroma",
    "pytest",
    "数据清洗",
    "岗位审核",
]


def _count_jobs(db: Session, status: str) -> int:
    return db.scalar(
        select(func.count()).select_from(JobPosting).where(JobPosting.status == status)
    ) or 0


def _parse_job_skills(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        parsed = []
    if isinstance(parsed, str):
        return [parsed]
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def _top_job_skills(jobs: list[JobPosting], limit: int = 8) -> list[dict]:
    counter: Counter[str] = Counter()
    for job in jobs:
        for skill in _parse_job_skills(job.skills):
            counter[skill] += 1
    return [
        {"skill": skill, "count": count}
        for skill, count in counter.most_common(limit)
    ]


def _resume_profile(resume: Resume | None) -> dict | None:
    if resume is None:
        return None
    version = current_resume_version(resume)
    return {
        "id": resume.id,
        "filename": version.file_name if version else resume.title,
        "version": resume.current_version_number,
        "is_default": bool(resume.is_default),
    }


def _user_skill_distribution(resume: Resume | None) -> list[dict]:
    version = current_resume_version(resume) if resume is not None else None
    text = version.content or "" if version is not None else ""
    lowered = text.lower()
    skills = []
    for keyword in SKILL_KEYWORDS:
        count = lowered.count(keyword.lower())
        if count:
            skills.append({"name": keyword, "level": min(100, 55 + count * 15)})
    return skills[:8]


def _capability_gap(
    personal_skills: list[dict],
    required_skills: list[dict],
) -> list[dict]:
    personal_map = {item["name"].lower(): item["level"] for item in personal_skills}
    if not required_skills:
        return []
    max_count = max(item["count"] for item in required_skills) or 1
    rows = []
    for item in required_skills[:6]:
        skill = item["skill"]
        rows.append(
            {
                "subject": skill,
                "personal": personal_map.get(skill.lower(), 20),
                "required": max(50, round(item["count"] / max_count * 100)),
            }
        )
    return rows


def _job_city_distribution(jobs: list[JobPosting]) -> list[dict]:
    counter: Counter[str] = Counter()
    for job in jobs:
        city = (job.location or "未知").split("-")[0].split("/")[0].strip() or "未知"
        counter[city] += 1
    return [
        {"name": city, "value": count}
        for city, count in counter.most_common(8)
    ]


def _recent_interviews(sessions: list[InterviewSession]) -> list[dict]:
    return [dashboard_interview_summary(session) for session in sessions[:5]]


def _interview_trend(sessions: list[InterviewSession]) -> list[dict]:
    rows = []
    for index, session in enumerate(reversed(sessions[-10:]), start=1):
        if session.score is None or not is_effective_interview_session(session):
            continue
        label = session.created_at.strftime("%m-%d") if session.created_at else str(index)
        rows.append({"date": label, "score": session.score, "index": index})
    return rows


def _multi_job_scores(records: list[MatchingRecord]) -> list[dict]:
    colors = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2"]
    rows = []
    for index, record in enumerate(records[:8]):
        job_label = "岗位 %s" % record.job_id
        if record.job:
            job_label = "%s(%s)" % (record.job.company, record.job.title)
        rows.append(
            {
                "job": job_label,
                "score": record.total_score,
                "color": colors[index % len(colors)],
            }
        )
    return rows


@router.get("/metrics", response_model=ApiResponse[dict])
def metrics(
    _reviewer: User = Depends(require_roles("reviewer")),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    return success_response(
        {
            "jobs_pending": _count_jobs(db, "pending"),
            "jobs_approved": _count_jobs(db, "approved"),
            "jobs_rejected": _count_jobs(db, "rejected"),
            "resume_audits": db.scalar(
                select(func.count()).select_from(ResumeAuditReport)
            )
            or 0,
            "interview_sessions": db.scalar(
                select(func.count()).select_from(InterviewSession)
            )
            or 0,
        }
    )


@router.get("/knowledge", response_model=ApiResponse[dict])
def knowledge(
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    return success_response(knowledge_overview())


@router.get("/dashboard", response_model=ApiResponse[dict])
def dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    jobs = db.scalars(select(JobPosting).order_by(JobPosting.id)).all()
    current_user_resumes_count = db.scalar(
        select(func.count())
        .select_from(Resume)
        .where(Resume.user_id == current_user.id)
        .where(Resume.source_type == RESUME_SOURCE_FORMAL)
    ) or 0
    current_user_sessions = db.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc())
    ).all()
    effective_sessions = [
        session
        for session in current_user_sessions
        if is_effective_interview_session(session)
    ]
    scored_sessions = [
        session for session in effective_sessions if session.score is not None
    ]
    avg_score = (
        round(sum(session.score for session in scored_sessions) / len(scored_sessions), 1)
        if scored_sessions
        else None
    )
    matching_records = db.scalars(
        select(MatchingRecord)
        .where(MatchingRecord.user_id == current_user.id)
        .order_by(MatchingRecord.created_at.desc(), MatchingRecord.id.desc())
    ).all()
    required_skills = _top_job_skills(jobs)
    default_resume = get_default_resume(db, current_user)
    personal_skills = _user_skill_distribution(default_resume)

    return success_response(
        {
            "total_resumes": current_user_resumes_count,
            "active_resume": _resume_profile(default_resume),
            "total_jobs": len(jobs),
            "total_interviews": len(effective_sessions),
            "avg_score": avg_score,
            "recent_interviews": _recent_interviews(effective_sessions),
            "skill_distribution": personal_skills,
            "job_skill_requirements": required_skills,
            "capability_gap": _capability_gap(personal_skills, required_skills),
            "multi_job_scores": _multi_job_scores(matching_records),
            "interview_trend": _interview_trend(effective_sessions),
            "job_city_distribution": _job_city_distribution(jobs),
            "agent_call_count": db.scalar(
                select(func.count())
                .select_from(AgentLog)
                .where(AgentLog.user_id == current_user.id)
            )
            or 0,
        }
    )
