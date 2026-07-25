from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.vector_store import search_similar_jobs

router = APIRouter()


class MatchRequest(BaseModel):
    resume_text: str
    target_position: str = ""
    top_k: int = 5


@router.post("/run")
def run_matching(payload: MatchRequest):
    if not payload.resume_text.strip():
        raise HTTPException(status_code=400, detail="简历文本不能为空")
    
    results = search_similar_jobs(payload.resume_text, top_k=payload.top_k)
    return {"matches": results}


@router.get("/skill-taxonomy", response_model=List[str])
def skill_taxonomy():
    return ["Python", "FastAPI", "React", "SQL", "LLM", "RAG", "数据清洗", "岗位审核"]
