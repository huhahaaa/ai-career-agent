from sqlalchemy import select

from app.api.v1.endpoints import matching as matching_endpoint
from app.core.security import hash_password
from app.models.job import JobPosting
from app.models.matching import MatchingRecord
from app.models.resume import Resume, ResumeVersion
from app.models.user import User
from app.services.vector_store import VectorStoreUnavailable


def register_and_login(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "matching-user",
            "email": "matching@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "matching-user", "password": "password123"},
    )
    return {"Authorization": "Bearer %s" % response.json()["data"]["access_token"]}


def test_matching_api_preserves_response_contract(client, monkeypatch):
    headers = register_and_login(client)
    monkeypatch.setattr(
        matching_endpoint,
        "match_resume_to_jobs",
        lambda *_args, **_kwargs: [
            {
                "job_id": "JOB-001",
                "title": "Python Engineer",
                "company": "Example Inc",
                "score": 91.5,
                "reason": "semantic similarity",
                "source_link": "https://example.com/jobs/1",
            }
        ],
    )

    response = client.post(
        "/api/v1/matching/run",
        headers=headers,
        json={"resume_text": "Python FastAPI project", "top_k": 3},
    )

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["data"]["matches"][0]["job_id"] == "JOB-001"


def test_matching_api_returns_503_when_vector_service_is_unavailable(
    client,
    monkeypatch,
):
    headers = register_and_login(client)

    def unavailable(*_args, **_kwargs):
        raise VectorStoreUnavailable("model unavailable")

    monkeypatch.setattr(matching_endpoint, "match_resume_to_jobs", unavailable)
    response = client.post(
        "/api/v1/matching/run",
        headers=headers,
        json={"resume_text": "Python FastAPI project"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "code": 50301,
        "message": "model unavailable",
        "data": None,
    }


def test_student_cannot_rebuild_vector_index(client):
    headers = register_and_login(client)

    response = client.post("/api/v1/matching/index/approved", headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == 40301


def test_rebuild_vector_index_clears_stale_vectors_first(
    client,
    session_factory,
    monkeypatch,
):
    with session_factory() as db:
        db.add(
            User(
                username="matching-reviewer",
                email="matching-reviewer@example.com",
                hashed_password=hash_password("password123"),
                role="reviewer",
            )
        )
        db.add(
            JobPosting(
                title="Python Backend Intern",
                company="Example Inc",
                location="Hangzhou",
                publish_time="2026-07-24",
                skills='["Python", "FastAPI", "SQL"]',
                source_link="https://example.com/jobs/reindex",
                status="approved",
            )
        )
        db.commit()
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "matching-reviewer", "password": "password123"},
    )
    headers = {
        "Authorization": "Bearer %s"
        % login_response.json()["data"]["access_token"]
    }
    calls = []

    monkeypatch.setattr(
        matching_endpoint,
        "clear_job_embeddings",
        lambda: calls.append("clear") or {"deleted_count": 3},
    )
    monkeypatch.setattr(
        matching_endpoint,
        "index_approved_jobs",
        lambda jobs: calls.append(("index", list(jobs)))
        or {"indexed_count": 1, "skipped_count": 0, "job_ids": ["1"]},
    )

    response = client.post("/api/v1/matching/index/approved", headers=headers)

    assert response.status_code == 200
    assert calls[0] == "clear"
    assert calls[1][0] == "index"
    assert response.json()["data"]["deleted_count"] == 3
    assert response.json()["data"]["indexed_count"] == 1


def test_matching_run_persists_history_for_database_jobs(
    client,
    session_factory,
    monkeypatch,
):
    headers = register_and_login(client)
    with session_factory() as db:
        job = JobPosting(
            title="Python Backend Intern",
            company="Example Inc",
            location="Hangzhou",
            publish_time="2026-07-24",
            skills='["Python", "FastAPI", "SQL"]',
            source_link="https://example.com/jobs/matching-history",
            status="approved",
            audit_comment="verified",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    monkeypatch.setattr(
        matching_endpoint,
        "match_resume_to_jobs",
        lambda *_args, **_kwargs: [
            {
                "job_id": str(job_id),
                "title": "Python Backend Intern",
                "company": "Example Inc",
                "score": 88.4,
                "reason": "FastAPI and SQL overlap",
                "source_link": "https://example.com/jobs/matching-history",
            }
        ],
    )

    response = client.post(
        "/api/v1/matching/run",
        headers=headers,
        json={
            "resume_text": "Python FastAPI SQL project",
            "target_position": "Python 后端实习生",
            "top_k": 3,
        },
    )
    history = client.get("/api/v1/matching/history", headers=headers)

    assert response.status_code == 200
    assert history.status_code == 200
    assert history.json()["data"][0]["job_id"] == job_id
    assert history.json()["data"][0]["total_score"] == 88

    with session_factory() as db:
        assert len(db.scalars(select(Resume)).all()) == 1
        assert len(db.scalars(select(ResumeVersion)).all()) == 1
        records = db.scalars(select(MatchingRecord)).all()
        assert len(records) == 1
        assert records[0].job_id == job_id
