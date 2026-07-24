from fastapi import APIRouter

from app.schemas.resume import ResumeAuditRequest, ResumeAuditResult
from app.services.resume_audit import audit_resume_text

router = APIRouter()


@router.post("/audit", response_model=ResumeAuditResult)
def audit_resume(payload: ResumeAuditRequest):
    return audit_resume_text(payload.resume_text, payload.target_position)

