"""Dashboard schemas - 数据看板 Schema 定义."""

from typing import List, Optional
from pydantic import BaseModel


class SkillDistribution(BaseModel):
    name: str
    level: float


class JobSkillRequirement(BaseModel):
    skill: str
    count: int


class CapabilityGap(BaseModel):
    subject: str
    personal: float
    required: float


class MultiJobScore(BaseModel):
    job: str
    score: float
    color: str


class InterviewTrendItem(BaseModel):
    date: str
    score: float


class JobCityDistribution(BaseModel):
    name: str
    value: int


class RecentInterviewItem(BaseModel):
    id: int
    company: str
    job_title: str
    mode: str
    score: Optional[float] = None
    duration_minutes: Optional[int] = 0
    status: str
    created_at: str


class DashboardOverview(BaseModel):
    total_resumes: int = 0
    total_jobs: int = 0
    total_interviews: int = 0
    avg_score: float = 0.0
    skill_distribution: List[SkillDistribution] = []
    job_skill_requirements: List[JobSkillRequirement] = []
    capability_gap: List[CapabilityGap] = []
    multi_job_scores: List[MultiJobScore] = []
    interview_trend: List[InterviewTrendItem] = []
    job_city_distribution: List[JobCityDistribution] = []
    recent_interviews: List[RecentInterviewItem] = []
