from typing import List, Optional

from pydantic import BaseModel, Field


class ResumeAuditRequest(BaseModel):
    resume_text: str = Field(..., min_length=10)
    target_position: str = ""
    resume_id: Optional[int] = None
    resume_version: Optional[int] = None


class ResumeAuditResult(BaseModel):
    score: int
    risk_flags: List[str]
    suggestions: List[str]
    missing_keywords: List[str]
    risk_level: str = "低"


class ResumeVersionCreateRequest(BaseModel):
    content: str = Field(..., min_length=10)
    file_name: str = "edited-resume.txt"
