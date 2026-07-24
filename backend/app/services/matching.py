from typing import Dict, List

from app.services.vector_store import search_similar_jobs


def match_resume_to_jobs(
    resume_text: str,
    target_position: str = "",
    top_k: int = 5,
) -> List[Dict]:
    query = "%s\n%s" % (target_position, resume_text)
    return search_similar_jobs(query=query, top_k=top_k)

