from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResumeAuditRequest(BaseModel):
    resume_text: str = Field(..., min_length=10)
    target_position: str = ""
    resume_id: Optional[int] = None


class ResumeAuditResult(BaseModel):
    score: int
    dimension_scores: Dict[str, Any] = {}
    risk_flags: List[str]
    suggestions: List[str]
    missing_keywords: List[str]
    risk_level: str = "低"
    rule_score: Optional[int] = None
    llm_score: Optional[int] = None
    detected_fields: Dict[str, bool] = {}
    position_bucket: str = ""
