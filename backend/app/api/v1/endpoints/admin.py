from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.session import get_db
from app.models.interview import InterviewSession
from app.models.job import JobPosting
from app.models.resume import ResumeAuditReport
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
router = APIRouter()


@router.get("/metrics", response_model=ApiResponse[dict])
def metrics(
    _reviewer: User = Depends(require_roles("reviewer")),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    def count_jobs(status: str) -> int:
        return db.scalar(
            select(func.count()).select_from(JobPosting).where(JobPosting.status == status)
        ) or 0

    return success_response(
        {
            "jobs_pending": count_jobs("pending"),
            "jobs_approved": count_jobs("approved"),
            "jobs_rejected": count_jobs("rejected"),
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
