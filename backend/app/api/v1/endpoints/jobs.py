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
from app.models.job import JobApplication, JobPosting, JobReviewRecord
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.job import JobApplicationUpdate, JobAuditRequest, JobCreate, JobPostingOut
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


def _application_for_job(
    db: Session,
    user_id: int,
    job_id: int,
) -> JobApplication | None:
    return db.scalar(
        select(JobApplication).where(
            JobApplication.user_id == user_id,
            JobApplication.job_id == job_id,
        )
    )


def _application_map(
    db: Session,
    user_id: int,
    jobs: List[JobPosting],
) -> dict[int, JobApplication]:
    if not jobs:
        return {}
    rows = db.scalars(
        select(JobApplication).where(
            JobApplication.user_id == user_id,
            JobApplication.job_id.in_([job.id for job in jobs]),
        )
    ).all()
    return {row.job_id: row for row in rows}


def job_to_response(
    job: JobPosting,
    application: JobApplication | None = None,
) -> JobPostingOut:
    return JobPostingOut.model_validate(
        {
            "id": job.id,
            "source_id": job.source_id,
            "category": job.category,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "employment_type": job.employment_type,
            "workplace_type": job.workplace_type,
            "salary_range": job.salary_range,
            "education": job.education,
            "experience": job.experience,
            "responsibilities": job.responsibilities,
            "requirements": job.requirements,
            "publish_time": job.publish_time,
            "skills": _decode_skills(job.skills),
            "source_site": job.source_site,
            "source_link": job.source_link,
            "status": job.status,
            "audit_comment": job.audit_comment,
            "updated_at": job.updated_at or datetime.now(timezone.utc),
            "is_favorite": bool(application.is_favorite) if application else False,
            "application_status": application.application_status if application else "",
            "application_note": application.note if application else "",
        }
    )


def job_to_vector_payload(job: JobPosting) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "category": job.category,
        "employment_type": job.employment_type,
        "workplace_type": job.workplace_type,
        "responsibilities": job.responsibilities,
        "requirements": job.requirements,
        "skills": _decode_skills(job.skills),
        "source_id": job.source_id,
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
    if normalized["source_id"]:
        existing = db.scalar(
            select(JobPosting).where(JobPosting.source_id == normalized["source_id"])
        )
    else:
        existing = db.scalar(
            select(JobPosting).where(JobPosting.source_link == normalized["source_link"])
        )
    if existing:
        raise AppException(409, 40904, "job source already exists")

    job = JobPosting(
        source_id=normalized["source_id"],
        category=normalized["category"],
        title=normalized["title"],
        company=normalized["company"],
        location=normalized["location"],
        employment_type=normalized["employment_type"],
        workplace_type=normalized["workplace_type"],
        salary_range=normalized["salary_range"],
        education=normalized["education"],
        experience=normalized["experience"],
        responsibilities=normalized["responsibilities"],
        requirements=normalized["requirements"],
        publish_time=normalized["publish_time"],
        skills=_encode_skills(normalized["skills"]),
        source_site=normalized["source_site"],
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[List[JobPostingOut]]:
    statement = select(JobPosting).order_by(JobPosting.id)
    if status:
        statement = statement.where(JobPosting.status == status)
    jobs = db.scalars(statement).all()
    applications = _application_map(db, current_user.id, jobs)
    return success_response([job_to_response(job, applications.get(job.id)) for job in jobs])


@router.get("/applications", response_model=ApiResponse[List[dict]])
def list_job_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[List[dict]]:
    applications = db.scalars(
        select(JobApplication)
        .where(JobApplication.user_id == current_user.id)
        .order_by(JobApplication.updated_at.desc(), JobApplication.id.desc())
    ).all()
    return success_response(
        [
            {
                "id": application.id,
                "job": job_to_response(application.job, application).model_dump(mode="json"),
                "job_id": application.job_id,
                "is_favorite": bool(application.is_favorite),
                "application_status": application.application_status,
                "note": application.note,
                "updated_at": application.updated_at,
            }
            for application in applications
            if application.job is not None
        ]
    )


@router.patch("/{job_id}/application", response_model=ApiResponse[JobPostingOut])
def update_job_application(
    job_id: int,
    payload: JobApplicationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[JobPostingOut]:
    job = db.get(JobPosting, job_id)
    if job is None:
        raise AppException(404, 40401, "job not found")

    application = _application_for_job(db, current_user.id, job_id)
    if application is None:
        application = JobApplication(
            user_id=current_user.id,
            job_id=job_id,
            is_favorite=False,
            application_status="interested",
            note="",
        )
        db.add(application)
        db.flush()
    if payload.is_favorite is not None:
        application.is_favorite = payload.is_favorite
    if payload.application_status is not None:
        application.application_status = payload.application_status
    if payload.note is not None:
        application.note = payload.note.strip()
    application.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(application)
    db.refresh(job)
    return success_response(job_to_response(job, application), message="job application updated")


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[List[JobPostingOut]]:
    jobs = db.scalars(
        select(JobPosting)
        .where(JobPosting.status == "approved")
        .order_by(JobPosting.id)
    ).all()
    applications = _application_map(db, current_user.id, jobs)
    return success_response([job_to_response(job, applications.get(job.id)) for job in jobs])
