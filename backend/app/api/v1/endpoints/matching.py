from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.services.matching import match_resume_to_jobs

router = APIRouter()


class MatchRequest(BaseModel):
    resume_text: str
    target_position: str = ""
    top_k: int = 5


@router.post("/run", response_model=ApiResponse[dict])
def run_matching(
    payload: MatchRequest,
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    return success_response(
        {
            "matches": match_resume_to_jobs(
                payload.resume_text,
                payload.target_position,
                payload.top_k,
            )
        }
    )


@router.get("/skill-taxonomy", response_model=ApiResponse[List[str]])
def skill_taxonomy(
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[List[str]]:
    skills = [
        "Python",
        "FastAPI",
        "React",
        "SQL",
        "LLM",
        "RAG",
        "数据清洗",
        "岗位审核",
    ]
    return success_response(skills)
