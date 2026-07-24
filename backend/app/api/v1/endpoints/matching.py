from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.api.v1.endpoints.jobs import job_to_vector_payload
from app.core.exceptions import AppException
from app.db.session import get_db
from app.models.job import JobPosting
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.matching import (
    BatchIndexResult,
    JobIndexResult,
    MatchRequest,
    MatchResponse,
)
from app.services.matching import (
    index_approved_job,
    index_approved_jobs,
    match_resume_to_jobs,
)
from app.services.vector_store import VectorStoreUnavailable

router = APIRouter()


def _vector_service_error(exc: Exception) -> AppException:
    return AppException(
        status_code=503,
        code=50301,
        message=str(exc),
    )


@router.post("/run", response_model=ApiResponse[MatchResponse])
def run_matching(
    payload: MatchRequest,
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[MatchResponse]:
    try:
        matches = match_resume_to_jobs(
            payload.resume_text,
            payload.target_position,
            payload.top_k,
        )
    except VectorStoreUnavailable as exc:
        raise _vector_service_error(exc) from exc
    return success_response(MatchResponse(matches=matches))


@router.post(
    "/index/jobs/{job_id}",
    response_model=ApiResponse[JobIndexResult],
)
def index_job(
    job_id: int,
    _reviewer: User = Depends(require_roles("reviewer")),
    db: Session = Depends(get_db),
) -> ApiResponse[JobIndexResult]:
    job = db.get(JobPosting, job_id)
    if job is None:
        raise AppException(404, 40401, "job not found")
    if job.status != "approved":
        raise AppException(409, 40903, "only approved jobs can be indexed")
    try:
        result = index_approved_job(job_to_vector_payload(job))
    except VectorStoreUnavailable as exc:
        raise _vector_service_error(exc) from exc
    return success_response(JobIndexResult.model_validate(result))


@router.post(
    "/index/approved",
    response_model=ApiResponse[BatchIndexResult],
)
def index_all_approved_jobs(
    _reviewer: User = Depends(require_roles("reviewer")),
    db: Session = Depends(get_db),
) -> ApiResponse[BatchIndexResult]:
    jobs = db.scalars(
        select(JobPosting)
        .where(JobPosting.status == "approved")
        .order_by(JobPosting.id)
    ).all()
    try:
        result = index_approved_jobs(job_to_vector_payload(job) for job in jobs)
    except VectorStoreUnavailable as exc:
        raise _vector_service_error(exc) from exc
    return success_response(BatchIndexResult.model_validate(result))


@router.get("/skill-taxonomy", response_model=ApiResponse[List[str]])
def skill_taxonomy(
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[List[str]]:
    return success_response(
        [
            "Python",
            "FastAPI",
            "React",
            "SQL",
            "LLM",
            "RAG",
            "数据清洗",
            "岗位审核",
        ]
    )
