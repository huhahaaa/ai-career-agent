import json
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.core.exceptions import AppException
from app.models.job import JobPosting, JobReviewRecord
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.job import JobAuditRequest, JobCreate, JobPostingOut
from app.services.job_cleaner import normalize_job

router = APIRouter()


def _encode_skills(skills: List[str]) -> str:
    return json.dumps(skills, ensure_ascii=False)


def _decode_skills(value: str) -> List[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(skill) for skill in loaded]


def job_to_response(job: JobPosting) -> JobPostingOut:
    return JobPostingOut.model_validate(
        {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "publish_time": job.publish_time,
            "skills": _decode_skills(job.skills),
            "source_link": job.source_link,
            "status": job.status,
            "audit_comment": job.audit_comment,
            "updated_at": job.updated_at or datetime.now(timezone.utc),
        }
    )


def job_to_vector_payload(job: JobPosting) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "responsibilities": job.responsibilities,
        "requirements": job.requirements,
        "skills": _decode_skills(job.skills),
        "source_link": job.source_link,
        "status": job.status,
    }


@router.post("/import", response_model=ApiResponse[JobPostingOut])
def import_job(
    payload: JobCreate,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[JobPostingOut]:
    normalized = normalize_job(payload.model_dump())
    existing = db.scalar(
        select(JobPosting).where(JobPosting.source_link == normalized["source_link"])
    )
    if existing:
        raise AppException(409, 40904, "job source link already exists")

    job = JobPosting(
        title=normalized["title"],
        company=normalized["company"],
        location=normalized["location"],
        publish_time=normalized["publish_time"],
        skills=_encode_skills(normalized["skills"]),
        source_link=normalized["source_link"],
        status="pending",
        audit_comment="",
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(409, 40904, "job source link already exists") from exc
    db.refresh(job)
    return success_response(job_to_response(job))


@router.get("", response_model=ApiResponse[List[JobPostingOut]])
def list_jobs(
    status: str = "",
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[List[JobPostingOut]]:
    statement = select(JobPosting).order_by(JobPosting.id)
    if status:
        statement = statement.where(JobPosting.status == status)
    jobs = db.scalars(statement).all()
    return success_response([job_to_response(job) for job in jobs])


@router.patch("/{job_id}/audit", response_model=ApiResponse[JobPostingOut])
def audit_job(
    job_id: int,
    payload: JobAuditRequest,
    reviewer: User = Depends(require_roles("reviewer")),
    db: Session = Depends(get_db),
) -> ApiResponse[JobPostingOut]:
    job = db.get(JobPosting, job_id)
    if job is None:
        raise AppException(404, 40401, "job not found")

    job.status = payload.status
    job.audit_comment = payload.comment
    job.updated_at = datetime.now(timezone.utc)
    db.add(
        JobReviewRecord(
            job_id=job.id,
            reviewer_id=reviewer.id,
            decision=payload.status,
            comment=payload.comment,
        )
    )
    db.commit()
    db.refresh(job)
    return success_response(job_to_response(job))


@router.get("/approved", response_model=ApiResponse[List[JobPostingOut]])
def approved_jobs(
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[List[JobPostingOut]]:
    jobs = db.scalars(
        select(JobPosting)
        .where(JobPosting.status == "approved")
        .order_by(JobPosting.id)
    ).all()
    return success_response([job_to_response(job) for job in jobs])
