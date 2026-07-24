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
    id: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    audit_comment: Optional[str] = ""
    updated_at: str


class JobAuditRequest(BaseModel):
    status: Literal["approved", "rejected"]
    reviewer: str
    comment: str

