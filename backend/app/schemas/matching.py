from typing import Dict, List

from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    resume_text: str = Field(min_length=1)
    target_position: str = ""
    top_k: int = Field(default=5, ge=1, le=20)


class MatchResult(BaseModel):
    job_id: str
    title: str
    company: str
    score: float = Field(ge=0, le=100)
    semantic_score: float | None = Field(default=None, ge=0, le=100)
    skill_coverage_score: float | None = Field(default=None, ge=0, le=100)
    ability_breakdown: Dict[str, object] = Field(default_factory=dict)
    reason: str
    source_link: str = ""
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    gap_analysis: str = ""
    suggestion: str = ""


class MatchResponse(BaseModel):
    matches: List[MatchResult]


class JobIndexResult(BaseModel):
    job_id: str
    status: str


class BatchIndexResult(BaseModel):
    deleted_count: int = 0
    indexed_count: int
    skipped_count: int
    job_ids: List[str]
