from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException

from app.schemas.job import (
    JobAuditRequest,
    JobCreate,
    JobPostingOut,
    JobStatusUpdate,
)

router = APIRouter()

JOB_STORE: dict = {}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _next_id() -> str:
    return f"job-{len(JOB_STORE) + 1:03d}"


@router.post("", response_model=JobPostingOut)
def create_job(payload: JobCreate):
    """新增岗位"""
    job_id = _next_id()
    record = {
        **payload.model_dump(),
        "id": job_id,
        "created_at": _now(),
        "updated_at": _now(),
    }
    JOB_STORE[job_id] = record
    return record


@router.get("", response_model=List[JobPostingOut])
def list_jobs(status: str = ""):
    """岗位列表，支持按状态过滤"""
    jobs = list(JOB_STORE.values())
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    return jobs


@router.get("/{job_id}", response_model=JobPostingOut)
def get_job(job_id: str):
    """岗位详情"""
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail="job not found")
    return JOB_STORE[job_id]


@router.put("/{job_id}/status", response_model=JobPostingOut)
def update_job_status(job_id: str, payload: JobStatusUpdate):
    """更新岗位状态（通过 / 驳回 / 重新设为待审核）"""
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail="job not found")
    JOB_STORE[job_id]["status"] = payload.status
    JOB_STORE[job_id]["updated_at"] = _now()
    return JOB_STORE[job_id]


@router.patch("/{job_id}/audit", response_model=JobPostingOut)
def audit_job(job_id: str, payload: JobAuditRequest):
    """审核岗位（保留旧端点兼容）"""
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail="job not found")
    JOB_STORE[job_id]["status"] = payload.status
    JOB_STORE[job_id]["audit_comment"] = payload.comment
    JOB_STORE[job_id]["reviewer"] = payload.reviewer
    JOB_STORE[job_id]["updated_at"] = _now()
    return JOB_STORE[job_id]


@router.post("/batch-import", response_model=List[JobPostingOut])
def batch_import(payload: dict):
    """批量导入岗位"""
    imported = []
    for raw in payload.get("jobs", []):
        job_id = _next_id()
        record = {
            "id": job_id,
            "title": raw.get("title", ""),
            "company": raw.get("company", ""),
            "city": raw.get("city", "北京"),
            "salary_min": raw.get("salary_min", 0),
            "salary_max": raw.get("salary_max", 0),
            "experience": raw.get("experience", ""),
            "education": raw.get("education", "本科"),
            "skills_required": raw.get("skills_required", []),
            "description": raw.get("description", ""),
            "status": raw.get("status", "pending"),
            "created_at": _now(),
            "updated_at": _now(),
        }
        JOB_STORE[job_id] = record
        imported.append(record)
    return imported


@router.get("/approved", response_model=List[JobPostingOut])
def approved_jobs():
    """已发布岗位列表"""
    return [j for j in JOB_STORE.values() if j.get("status") == "published"]
