from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.matching import match_resume_to_jobs

router = APIRouter()


class MatchRequest(BaseModel):
    resume_text: str
    target_position: str = ""
    top_k: int = 5


@router.post("/run")
def run_matching(payload: MatchRequest):
    return {
        "matches": match_resume_to_jobs(
            payload.resume_text,
            payload.target_position,
            payload.top_k,
        )
    }


@router.get("/skill-taxonomy", response_model=List[str])
def skill_taxonomy():
    return ["Python", "FastAPI", "React", "SQL", "LLM", "RAG", "数据清洗", "岗位审核"]

