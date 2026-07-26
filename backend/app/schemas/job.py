from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, HttpUrl


class JobCreate(BaseModel):
    source_id: Optional[str] = None
    title: str
    company: str
    location: str
    publish_time: str
    skills: List[str]
    source_link: HttpUrl
    category: str = ""
    employment_type: str = ""
    workplace_type: str = ""
    salary_range: str = ""
    education: str = ""
    experience: str = ""
    responsibilities: str = ""
    requirements: str = ""
    source_site: str = ""


class JobPostingOut(JobCreate):
    id: int
    status: Literal["pending", "approved", "rejected"] = "pending"
    audit_comment: Optional[str] = ""
    updated_at: datetime
    is_favorite: bool = False
    application_status: str = ""
    application_note: str = ""


class JobAuditRequest(BaseModel):
    status: Literal["approved", "rejected"]
    comment: str = ""


class JobApplicationUpdate(BaseModel):
    is_favorite: Optional[bool] = None
    application_status: Optional[
        Literal["", "interested", "applied", "interviewing", "offer", "rejected", "archived"]
    ] = None
    note: Optional[str] = None
