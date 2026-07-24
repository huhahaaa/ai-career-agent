from typing import List

from fastapi import APIRouter, HTTPException

from app.schemas.job import JobAuditRequest, JobCreate, JobPostingOut
from app.services.job_audit import apply_job_audit
from app.services.job_cleaner import normalize_job

router = APIRouter()

JOB_STORE = {}


@router.post("/import", response_model=JobPostingOut)
def import_job(payload: JobCreate):
    normalized = normalize_job(payload.model_dump())
    job_id = "job-%03d" % (len(JOB_STORE) + 1)
    record = {
        **normalized,
        "id": job_id,
        "status": "pending",
        "audit_comment": "",
        "updated_at": "2026-07-24",
    }
    JOB_STORE[job_id] = record
    return record


@router.get("", response_model=List[JobPostingOut])
def list_jobs(status: str = ""):
    jobs = list(JOB_STORE.values())
    if status:
        jobs = [job for job in jobs if job["status"] == status]
    return jobs


@router.patch("/{job_id}/audit", response_model=JobPostingOut)
def audit_job(job_id: str, payload: JobAuditRequest):
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail="job not found")
    JOB_STORE[job_id] = apply_job_audit(JOB_STORE[job_id], payload.model_dump())
    return JOB_STORE[job_id]


@router.get("/approved", response_model=List[JobPostingOut])
def approved_jobs():
    return [job for job in JOB_STORE.values() if job["status"] == "approved"]

