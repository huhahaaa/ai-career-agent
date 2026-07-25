from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, HttpUrl


class JobCreate(BaseModel):
    title: str
    company: str
    location: str
    publish_time: str
    skills: List[str]
    source_link: HttpUrl


class JobPostingOut(JobCreate):
    id: int
    status: Literal["pending", "approved", "rejected"] = "pending"
    audit_comment: Optional[str] = ""
    updated_at: datetime


class JobDetailOut(JobPostingOut):
    salary_range: str = ""
    education: str = ""
    experience: str = ""
    responsibilities: str = ""
    requirements: str = ""
    source_site: str = ""
    collected_at: Optional[datetime] = None


class JobAuditRequest(BaseModel):
    status: Literal["approved", "rejected"]
    comment: str = ""
