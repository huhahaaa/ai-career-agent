from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, require_roles
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.job import JobAuditRequest, JobCreate, JobPostingOut
from app.services.job_audit import apply_job_audit
from app.services.job_cleaner import normalize_job

router = APIRouter()

JOB_STORE: Dict[int, Dict] = {}


@router.post("/import", response_model=ApiResponse[JobPostingOut])
def import_job(
    payload: JobCreate,
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[JobPostingOut]:
    normalized = normalize_job(payload.model_dump())
    job_id = len(JOB_STORE) + 1
    record = {
        **normalized,
        "id": job_id,
        "status": "pending",
        "audit_comment": "",
        "updated_at": datetime.now(timezone.utc),
    }
    JOB_STORE[job_id] = record
    return success_response(JobPostingOut.model_validate(record))


@router.get("", response_model=ApiResponse[List[JobPostingOut]])
def list_jobs(
    status: str = "",
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[List[JobPostingOut]]:
    jobs = list(JOB_STORE.values())
    if status:
        jobs = [job for job in jobs if job["status"] == status]
    return success_response(
        [JobPostingOut.model_validate(job) for job in jobs]
    )


@router.patch("/{job_id}/audit", response_model=ApiResponse[JobPostingOut])
def audit_job(
    job_id: int,
    payload: JobAuditRequest,
    reviewer: User = Depends(require_roles("reviewer")),
) -> ApiResponse[JobPostingOut]:
    if job_id not in JOB_STORE:
        raise AppException(404, 40401, "job not found")
    audit_data = payload.model_dump()
    audit_data["reviewer"] = reviewer.username
    JOB_STORE[job_id] = apply_job_audit(JOB_STORE[job_id], audit_data)
    JOB_STORE[job_id]["updated_at"] = datetime.now(timezone.utc)
    return success_response(JobPostingOut.model_validate(JOB_STORE[job_id]))


@router.get("/approved", response_model=ApiResponse[List[JobPostingOut]])
def approved_jobs(
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[List[JobPostingOut]]:
    jobs = [job for job in JOB_STORE.values() if job["status"] == "approved"]
    return success_response(
        [JobPostingOut.model_validate(job) for job in jobs]
    )
