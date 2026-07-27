import json
import threading
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from app.core.config import settings


class VectorStoreUnavailable(RuntimeError):
    pass


def _job_identifier(job: Dict) -> str:
    identifier = job.get("id") or job.get("source_id")
    if identifier is None:
        raise ValueError("job requires id or source_id before indexing")
    return str(identifier)


def _job_document(job: Dict) -> str:
    skills = job.get("skills") or []
    if isinstance(skills, str):
        skills = [skills]
    sections = [
        job.get("category", ""),
        job.get("title", ""),
        job.get("company", ""),
        job.get("location", ""),
        job.get("employment_type", ""),
        job.get("workplace_type", ""),
        job.get("responsibilities", ""),
        job.get("requirements", ""),
        " ".join(str(skill) for skill in skills),
    ]
    return "\n".join(str(section).strip() for section in sections if section)


def _job_metadata(job: Dict) -> Dict:
    skills = job.get("skills") or []
    if isinstance(skills, str):
        skills = [skills]
    return {
        "doc_type": "job",
        "title": str(job.get("title", "")),
        "company": str(job.get("company", "")),
        "location": str(job.get("location", "")),
        "category": str(job.get("category", "")),
        "employment_type": str(job.get("employment_type", "")),
        "workplace_type": str(job.get("workplace_type", "")),
        "source_id": str(job.get("source_id", "")),
        "source_link": str(job.get("source_link", "")),
        "skills_json": json.dumps(skills, ensure_ascii=False),
        "status": str(job.get("status", "")),
    }


def _clean_metadata(metadata: Dict) -> Dict:
    cleaned = {}
    for key, value in (metadata or {}).items():
        if value is None:
            cleaned[str(key)] = ""
        elif isinstance(value, (str, int, float, bool)):
            cleaned[str(key)] = value
        else:
            cleaned[str(key)] = json.dumps(value, ensure_ascii=False)
    return cleaned


class VectorStore:
    def __init__(
        self,
        collection_factory: Optional[Callable[[], object]] = None,
        collection_name: Optional[str] = None,
    ) -> None:
        self._collection_factory = collection_factory or self._create_collection
        self._collection_name = collection_name or settings.vector_collection_name
        self._collection: Optional[object] = None
        self._lock = threading.Lock()

    def _create_collection(self):
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            from chromadb.utils.embedding_functions import (
                SentenceTransformerEmbeddingFunction,
            )
        except ImportError as exc:
            raise VectorStoreUnavailable(
                "vector dependencies are not installed; run "
                "pip install -r requirements-vector.txt"
            ) from exc

        try:
            store_path = Path(settings.vector_store_path).expanduser().resolve()
            store_path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(
                path=str(store_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            embedding_function = SentenceTransformerEmbeddingFunction(
                model_name=settings.vector_model_name,
            )
            return client.get_or_create_collection(
                name=self._collection_name,
                embedding_function=embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise VectorStoreUnavailable(
                "vector model or store could not be initialized: %s" % exc
            ) from exc

    def _get_collection(self):
        if self._collection is None:
            with self._lock:
                if self._collection is None:
                    self._collection = self._collection_factory()
        return self._collection

    def upsert_job(self, job: Dict) -> Dict:
        if job.get("status") != "approved":
            raise ValueError("only approved jobs can be indexed")

        job_id = _job_identifier(job)
        document = _job_document(job)
        if not document.strip():
            raise ValueError("job content is empty")

        collection = self._get_collection()
        try:
            collection.upsert(
                ids=[job_id],
                documents=[document],
                metadatas=[_clean_metadata(_job_metadata(job))],
            )
        except Exception as exc:
            raise VectorStoreUnavailable("job indexing failed: %s" % exc) from exc
        return {"job_id": job_id, "status": "indexed"}

    def upsert_approved_jobs(self, jobs: Iterable[Dict]) -> Dict:
        indexed = []
        skipped = 0
        for job in jobs:
            if job.get("status") != "approved":
                skipped += 1
                continue
            indexed.append(self.upsert_job(job)["job_id"])
        return {
            "indexed_count": len(indexed),
            "skipped_count": skipped,
            "job_ids": indexed,
        }

    def clear(self) -> Dict:
        collection = self._get_collection()
        try:
            if collection.count() == 0:
                return {"deleted_count": 0}
            result = collection.get()
            ids = result.get("ids") or []
            if ids:
                collection.delete(ids=ids)
        except Exception as exc:
            raise VectorStoreUnavailable("vector store clearing failed: %s" % exc) from exc
        return {"deleted_count": len(ids)}

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if not query.strip():
            raise ValueError("matching query cannot be empty")

        collection = self._get_collection()
        try:
            count = collection.count()
            if count == 0:
                return []
            result = collection.query(
                query_texts=[query],
                n_results=min(top_k, count),
                include=["metadatas", "distances", "documents"],
            )
        except Exception as exc:
            raise VectorStoreUnavailable("vector search failed: %s" % exc) from exc

        ids = (result.get("ids") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        matches = []
        for index, job_id in enumerate(ids):
            metadata = metadatas[index] or {}
            if metadata.get("doc_type") not in {"", None, "job"}:
                continue
            try:
                skills = json.loads(metadata.get("skills_json", "[]") or "[]")
            except json.JSONDecodeError:
                skills = []
            if not isinstance(skills, list):
                skills = []
            distance = float(distances[index]) if index < len(distances) else 1.0
            score = round(max(0.0, min(1.0, 1.0 - distance)) * 100, 2)
            matches.append(
                {
                    "job_id": str(job_id),
                    "title": metadata.get("title", ""),
                    "company": metadata.get("company", ""),
                    "category": metadata.get("category", ""),
                    "employment_type": metadata.get("employment_type", ""),
                    "workplace_type": metadata.get("workplace_type", ""),
                    "score": score,
                    "reason": "简历与岗位描述的语义相似度为 %.1f%%" % score,
                    "source_id": metadata.get("source_id", ""),
                    "source_link": metadata.get("source_link", ""),
                    "skills": [str(skill) for skill in skills],
                }
            )
        return matches

    def upsert_document(self, document: Dict) -> Dict:
        doc_id = str(document.get("doc_id") or "").strip()
        content = str(document.get("content") or "").strip()
        if not doc_id:
            raise ValueError("knowledge document requires doc_id")
        if not content:
            raise ValueError("knowledge document content is empty")

        metadata = _clean_metadata(document.get("metadata") or {})
        metadata.setdefault("doc_type", "knowledge")
        collection = self._get_collection()
        try:
            collection.upsert(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata],
            )
        except Exception as exc:
            raise VectorStoreUnavailable("knowledge indexing failed: %s" % exc) from exc
        return {"doc_id": doc_id, "status": "indexed"}

    def upsert_documents(self, documents: Iterable[Dict]) -> Dict:
        indexed = []
        skipped = 0
        for document in documents:
            try:
                indexed.append(self.upsert_document(document)["doc_id"])
            except ValueError:
                skipped += 1
        return {
            "indexed_count": len(indexed),
            "skipped_count": skipped,
            "doc_ids": indexed,
        }

    def search_documents(self, query: str, top_k: int = 5) -> List[Dict]:
        if not query.strip():
            raise ValueError("knowledge query cannot be empty")

        collection = self._get_collection()
        try:
            count = collection.count()
            if count == 0:
                return []
            result = collection.query(
                query_texts=[query],
                n_results=min(top_k, count),
                include=["metadatas", "distances", "documents"],
            )
        except Exception as exc:
            raise VectorStoreUnavailable("knowledge search failed: %s" % exc) from exc

        ids = (result.get("ids") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        matches = []
        for index, doc_id in enumerate(ids):
            metadata = metadatas[index] or {}
            distance = float(distances[index]) if index < len(distances) else 1.0
            score = round(max(0.0, min(1.0, 1.0 - distance)) * 100, 2)
            matches.append(
                {
                    "doc_id": str(doc_id),
                    "doc_type": metadata.get("doc_type", ""),
                    "title": metadata.get("title", ""),
                    "score": score,
                    "content": documents[index] if index < len(documents) else "",
                    "metadata": metadata,
                }
            )
        return matches


vector_store = VectorStore()
knowledge_vector_store = VectorStore(collection_name=settings.knowledge_collection_name)


def upsert_job_embedding(job: Dict) -> Dict:
    return vector_store.upsert_job(job)


def upsert_approved_job_embeddings(jobs: Iterable[Dict]) -> Dict:
    return vector_store.upsert_approved_jobs(jobs)


def clear_job_embeddings() -> Dict:
    return vector_store.clear()


def search_similar_jobs(query: str, top_k: int = 5) -> List[Dict]:
    return vector_store.search(query=query, top_k=top_k)


def upsert_knowledge_documents(documents: Iterable[Dict]) -> Dict:
    return knowledge_vector_store.upsert_documents(documents)


def search_knowledge_documents(query: str, top_k: int = 5) -> List[Dict]:
    return knowledge_vector_store.search_documents(query=query, top_k=top_k)
