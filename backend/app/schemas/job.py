from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str
    company: str
    city: str = ""
    salary_min: int = 0
    salary_max: int = 0
    experience: str = ""
    education: str = "本科"
    skills_required: List[str] = Field(default_factory=list)
    description: str = ""
    status: Literal["pending", "published", "rejected"] = "pending"


class JobStatusUpdate(BaseModel):
    status: Literal["pending", "published", "rejected"]


class JobPostingOut(BaseModel):
    id: str
    title: str
    company: str
    city: str = ""
    salary_min: int = 0
    salary_max: int = 0
    experience: str = ""
    education: str = ""
    skills_required: List[str] = Field(default_factory=list)
    description: str = ""
    status: Literal["pending", "published", "rejected"] = "pending"
    created_at: str = ""
    updated_at: str = ""


class JobAuditRequest(BaseModel):
    status: Literal["published", "rejected"]
    reviewer: str = ""
    comment: str = ""
