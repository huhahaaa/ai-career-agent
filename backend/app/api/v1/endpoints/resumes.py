"""
简历 API 端点
"""
import logging

from fastapi import APIRouter, HTTPException

from app.schemas.resume import ResumeAuditRequest, ResumeAuditResult
from app.services.resume_audit import audit_resume_text

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/audit", response_model=ResumeAuditResult)
async def audit_resume(payload: ResumeAuditRequest):
    """审核简历（传入文本）"""
    try:
        result = audit_resume_text(
            resume_text=payload.resume_text,
            target_position=payload.target_position,
        )
        return result
    except Exception as e:
        logger.error("Resume audit failed: %s", e)
        raise HTTPException(status_code=500, detail=f"简历审核失败: {str(e)}")
