from typing import Dict, Iterable, List

from app.services.vector_store import (
    search_similar_jobs,
    upsert_approved_job_embeddings,
    upsert_job_embedding,
)


def build_matching_query(resume_text: str, target_position: str = "") -> str:
    sections = [target_position.strip(), resume_text.strip()]
    return "\n".join(section for section in sections if section)


def match_resume_to_jobs(
    resume_text: str,
    target_position: str = "",
    top_k: int = 5,
) -> List[Dict]:
    query = build_matching_query(resume_text, target_position)
    return search_similar_jobs(query=query, top_k=top_k)


def index_approved_job(job: Dict) -> Dict:
    return upsert_job_embedding(job)


def index_approved_jobs(jobs: Iterable[Dict]) -> Dict:
    return upsert_approved_job_embeddings(jobs)
