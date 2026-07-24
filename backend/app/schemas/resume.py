from typing import List, Optional

from pydantic import BaseModel


class ResumeAuditRequest(BaseModel):
    resume_text: str
    target_position: str = ""
    resume_id: Optional[int] = None


class ResumeAuditResult(BaseModel):
    score: int
    risk_flags: List[str]
    suggestions: List[str]
    missing_keywords: List[str]
