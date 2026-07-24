"""简历模块所有请求/响应 Pydantic 模型。"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ResumeAuditRequest(BaseModel):
    resume_text: str = Field(..., min_length=10, description="简历文本")
    target_position: str = ""


class ResumeAuditResult(BaseModel):
    score: int
    risk_flags: List[str] = []
    suggestions: List[str] = []
    missing_keywords: List[str] = []
    risk_level: str = "低"  # 低 / 中 / 高
