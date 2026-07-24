# backend/app/services/matching.py
from typing import List, Dict, Any
from services.vector_store import search_jobs


def match_resume_to_jobs(
    resume_text: str,
    target_position: str = "",
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    根据简历文本匹配岗位
    """
    # 如果传入了目标岗位，可以作为过滤条件（暂时忽略，后续可扩展）
    results = search_jobs(resume_text, top_k=top_k)
    return results