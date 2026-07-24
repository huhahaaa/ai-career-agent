from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.resume import ResumeAuditRequest, ResumeAuditResult
from app.services.resume_audit import audit_resume_text

router = APIRouter()


@router.post("/audit", response_model=ApiResponse[ResumeAuditResult])
def audit_resume(
    payload: ResumeAuditRequest,
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[ResumeAuditResult]:
    result = audit_resume_text(payload.resume_text, payload.target_position)
    return success_response(ResumeAuditResult.model_validate(result))
