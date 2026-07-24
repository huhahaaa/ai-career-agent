from fastapi import APIRouter, Depends

from app.api.dependencies import require_roles
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
router = APIRouter()


@router.get("/metrics", response_model=ApiResponse[dict])
def metrics(
    _reviewer: User = Depends(require_roles("reviewer")),
) -> ApiResponse[dict]:
    return success_response(
        {
            "jobs_pending": 0,
            "jobs_approved": 0,
            "resume_audits": 0,
            "interview_sessions": 0,
        }
    )
