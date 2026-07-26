import pytest

from app.services.vector_store import VectorStore


class FakeCollection:
    def __init__(self):
        self.upserts = []
        self.ids = []
        self.deleted_ids = []

    def upsert(self, **payload):
        self.upserts.append(payload)
        self.ids = payload["ids"]

    def count(self):
        return len(self.ids)

    def get(self):
        return {"ids": self.ids}

    def delete(self, **payload):
        self.deleted_ids.extend(payload["ids"])
        self.ids = [job_id for job_id in self.ids if job_id not in payload["ids"]]

    def query(self, **_payload):
        return {
            "ids": [["JOB-001"]],
            "metadatas": [[{
                "title": "Python Engineer",
                "company": "Example Inc",
                "category": "后端开发",
                "employment_type": "实习",
                "workplace_type": "远程",
                "source_link": "https://example.com/jobs/1",
                "skills_json": '["Python", "FastAPI", "SQL"]',
            }]],
            "distances": [[0.18]],
            "documents": [["Python FastAPI SQL"]],
        }


class FakeKnowledgeCollection(FakeCollection):
    def query(self, **_payload):
        return {
            "ids": [["role_backend"]],
            "metadatas": [[{
                "doc_type": "role_profile",
                "title": "后端开发岗位能力画像",
                "role": "后端开发",
                "source_file": "role_profiles.json",
            }]],
            "distances": [[0.12]],
            "documents": [["后端开发必备能力包括 Python、SQL、接口开发。"]],
        }


def approved_job():
    return {
        "source_id": "JOB-001",
        "category": "后端开发",
        "title": "Python Engineer",
        "company": "Example Inc",
        "location": "Shanghai",
        "employment_type": "实习",
        "workplace_type": "远程",
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
    assert matches[0]["category"] == "后端开发"
    assert matches[0]["skills"] == ["Python", "FastAPI", "SQL"]


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


def test_clear_deletes_existing_vectors():
    collection = FakeCollection()
    store = VectorStore(collection_factory=lambda: collection)

    store.upsert_job(approved_job())
    result = store.clear()

    assert result == {"deleted_count": 1}
    assert collection.deleted_ids == ["JOB-001"]
    assert collection.count() == 0


def test_job_search_skips_non_job_documents_if_collection_is_polluted():
    class MixedCollection(FakeCollection):
        def count(self):
            return 2

        def query(self, **_payload):
            return {
                "ids": [["skill_Python", "JOB-001"]],
                "metadatas": [[
                    {
                        "doc_type": "skill_definition",
                        "title": "Python技能定义",
                    },
                    {
                        "doc_type": "job",
                        "title": "Python Engineer",
                        "company": "Example Inc",
                        "category": "后端开发",
                        "employment_type": "实习",
                        "workplace_type": "远程",
                        "source_id": "JOB-001",
                        "source_link": "https://example.com/jobs/1",
                        "skills_json": '["Python"]',
                    },
                ]],
                "distances": [[0.05, 0.2]],
                "documents": [["标准技能：Python", "Python Engineer"]],
            }

    store = VectorStore(collection_factory=lambda: MixedCollection())

    matches = store.search("Python", top_k=2)

    assert len(matches) == 1
    assert matches[0]["job_id"] == "JOB-001"


def test_knowledge_documents_can_be_indexed_and_searched():
    collection = FakeKnowledgeCollection()
    store = VectorStore(collection_factory=lambda: collection, collection_name="knowledge_base")

    result = store.upsert_document(
        {
            "doc_id": "role_backend",
            "content": "后端开发必备能力包括 Python、SQL、接口开发。",
            "metadata": {"doc_type": "role_profile", "title": "后端开发岗位能力画像", "role": "后端开发"},
        }
    )
    matches = store.search_documents("后端开发", top_k=3)

    assert result == {"doc_id": "role_backend", "status": "indexed"}
    assert collection.upserts[0]["ids"] == ["role_backend"]
    assert collection.upserts[0]["metadatas"][0]["doc_type"] == "role_profile"
    assert matches[0]["doc_type"] == "role_profile"
    assert matches[0]["score"] == 88.0
