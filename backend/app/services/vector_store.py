from typing import Dict, List


def upsert_job_embedding(job: Dict) -> Dict:
    return {
        "job_id": job.get("id"),
        "vector_status": "queued",
        "message": "vector store integration scaffolded",
    }


def search_similar_jobs(query: str, top_k: int = 5) -> List[Dict]:
    return [
        {
            "job_id": "demo-job",
            "score": 0.75,
            "reason": "placeholder vector search result for: %s" % query[:30],
        }
    ][:top_k]

