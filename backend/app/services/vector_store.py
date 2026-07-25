import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from sentence_transformers import SentenceTransformer
import chromadb
from typing import Dict, List

persist_directory = "./chroma_db"
client = chromadb.PersistentClient(path=persist_directory)
collection = client.get_or_create_collection(
    name="job_knowledge",
    metadata={"hnsw:space": "cosine"}
)
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

print("✅ ChromaDB 核心模块加载成功")


def upsert_job_embedding(job: Dict) -> Dict:
    job_id = job.get("id")
    title = job.get("title", "")
    company = job.get("company", "")
    description = job.get("description", "")
    requirements = job.get("requirements", "")
    source_link = job.get("source_link", "")
    
    text_to_embed = f"{title}\n{description}\n{requirements}"
    embedding = model.encode(text_to_embed).tolist()
    
    collection.upsert(
        ids=[str(job_id)],
        embeddings=[embedding],
        metadatas=[{
            "title": title,
            "company": company,
            "source_link": source_link,
            "requirements": requirements[:100]
        }],
        documents=[text_to_embed]
    )
    return {"job_id": job_id, "vector_status": "success"}


def search_similar_jobs(query: str, top_k: int = 5) -> List[Dict]:
    query_embedding = model.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["metadatas", "documents", "distances"]
    )
    matched = []
    if results['ids'] and len(results['ids'][0]) > 0:
        for i in range(len(results['ids'][0])):
            matched.append({
                "job_id": results['ids'][0][i],
                "title": results['metadatas'][0][i].get('title', '未知'),
                "company": results['metadatas'][0][i].get('company', '未知'),
                "source_link": results['metadatas'][0][i].get('source_link', ''),
                "score": round(1 - results['distances'][0][i], 3),
                "reason": results['documents'][0][i][:150] + "..."
            })
    return matched
