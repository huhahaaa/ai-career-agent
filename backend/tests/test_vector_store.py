import pytest

from app.services.vector_store import VectorStore


class FakeCollection:
    def __init__(self):
        self.upserts = []

    def upsert(self, **payload):
        self.upserts.append(payload)

    def count(self):
        return 1

    def query(self, **_payload):
        return {
            "ids": [["JOB-001"]],
            "metadatas": [[{
                "title": "Python Engineer",
                "company": "Example Inc",
                "source_link": "https://example.com/jobs/1",
            }]],
            "distances": [[0.18]],
            "documents": [["Python FastAPI SQL"]],
        }


def approved_job():
    return {
        "source_id": "JOB-001",
        "title": "Python Engineer",
        "company": "Example Inc",
        "location": "Shanghai",
        "requirements": "Build APIs with FastAPI and SQL.",
        "skills": ["Python", "FastAPI", "SQL"],
        "source_link": "https://example.com/jobs/1",
        "status": "approved",
    }


def test_collection_and_model_are_loaded_lazily():
    collection = FakeCollection()
    factory_calls = []
    store = VectorStore(
        collection_factory=lambda: factory_calls.append(True) or collection,
    )

    assert factory_calls == []
    store.upsert_job(approved_job())
    matches = store.search("Python FastAPI", top_k=5)

    assert len(factory_calls) == 1
    assert collection.upserts[0]["ids"] == ["JOB-001"]
    assert matches[0]["score"] == 82.0
    assert matches[0]["title"] == "Python Engineer"


def test_unapproved_job_is_rejected_before_vector_store_loads():
    factory_calls = []
    store = VectorStore(collection_factory=lambda: factory_calls.append(True))
    job = {**approved_job(), "status": "pending"}

    with pytest.raises(ValueError, match="only approved jobs"):
        store.upsert_job(job)

    assert factory_calls == []


def test_batch_index_skips_unapproved_jobs():
    collection = FakeCollection()
    store = VectorStore(collection_factory=lambda: collection)

    result = store.upsert_approved_jobs(
        [approved_job(), {**approved_job(), "source_id": "JOB-002", "status": "rejected"}]
    )

    assert result == {
        "indexed_count": 1,
        "skipped_count": 1,
        "job_ids": ["JOB-001"],
    }
