import json

from sqlalchemy import select

from app.api.v1.endpoints import matching as matching_endpoint
from app.core.security import hash_password
from app.models.job import JobPosting
from app.models.matching import MatchingRecord
from app.models.resume import (
    RESUME_SOURCE_FORMAL,
    RESUME_SOURCE_MATCHING_SNAPSHOT,
    Resume,
    ResumeVersion,
)
from app.models.user import User
from app.services.matching import enrich_match_results
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
    assert response.json()["data"]["matches"][0]["matched_skills"] == []


def test_match_result_skill_gap_analysis_is_added():
    matches = enrich_match_results(
        "Python FastAPI SQL project with backend API design.",
        [
            {
                "job_id": "1",
                "title": "Python Backend Intern",
                "company": "Example Inc",
                "score": 88.0,
                "reason": "semantic similarity",
                "source_link": "https://example.com/jobs/1",
                "skills": ["Python", "FastAPI", "SQL", "Docker"],
            }
        ],
    )

    assert matches[0]["matched_skills"] == ["Python", "FastAPI", "SQL"]
    assert matches[0]["missing_skills"] == ["Docker"]
    assert matches[0]["semantic_score"] == 94.0
    assert matches[0]["skill_coverage_score"] == 88.89
    assert matches[0]["score"] == 91.96
    assert matches[0]["ability_breakdown"]["direction_score"] == 100.0
    assert matches[0]["ability_breakdown"]["language_score"] == 100.0
    assert matches[0]["ability_breakdown"]["framework_tool_score"] == 50.0
    assert "缺少：Docker" in matches[0]["gap_analysis"]
    assert "Docker" in matches[0]["suggestion"]
    assert "94.0" in matches[0]["reason"]
    assert "88.9" in matches[0]["reason"]


def test_match_results_are_sorted_by_weighted_score():
    matches = enrich_match_results(
        "Python FastAPI SQL Docker",
        [
            {
                "job_id": "semantic-only",
                "title": "General Backend Intern",
                "company": "Example Inc",
                "score": 90.0,
                "reason": "semantic similarity",
                "source_link": "https://example.com/jobs/semantic-only",
                "skills": ["Rust", "C++", "Zig"],
            },
            {
                "job_id": "skill-covered",
                "title": "Python Backend Intern",
                "company": "Example Inc",
                "score": 80.0,
                "reason": "semantic similarity",
                "source_link": "https://example.com/jobs/skill-covered",
                "skills": ["Python", "FastAPI", "SQL", "Docker"],
            },
        ],
    )

    assert matches[0]["job_id"] == "skill-covered"
    assert matches[0]["score"] == 94.0
    assert matches[1]["score"] == 59.0
    assert matches[1]["ability_breakdown"]["language_score"] == 0.0


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
                "score": 84.4,
                "semantic_score": 88.4,
                "skill_coverage_score": 75.0,
                "reason": "FastAPI and SQL overlap",
                "source_link": "https://example.com/jobs/matching-history",
                "matched_skills": ["Python", "FastAPI", "SQL"],
                "missing_skills": ["Docker"],
                "gap_analysis": "已命中 3/4 项技能，缺少：Docker。",
                "suggestion": "建议补充：Docker。",
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
    assert history.json()["data"][0]["total_score"] == 84
    assert history.json()["data"][0]["details"]["semantic_score"] == 88.4
    assert history.json()["data"][0]["details"]["skill_coverage_score"] == 75.0
    assert history.json()["data"][0]["details"]["matched_skills"] == [
        "Python",
        "FastAPI",
        "SQL",
    ]
    assert history.json()["data"][0]["details"]["missing_skills"] == ["Docker"]

    with session_factory() as db:
        resumes = db.scalars(select(Resume)).all()
        assert len(resumes) == 1
        assert resumes[0].source_type == RESUME_SOURCE_MATCHING_SNAPSHOT
        assert len(db.scalars(select(ResumeVersion)).all()) == 1
        records = db.scalars(select(MatchingRecord)).all()
        assert len(records) == 1
        assert records[0].job_id == job_id


def test_matching_can_use_existing_formal_resume_without_creating_snapshot(
    client,
    session_factory,
    monkeypatch,
):
    headers = register_and_login(client)
    with session_factory() as db:
        user = db.scalar(select(User).where(User.username == "matching-user"))
        resume = Resume(
            user_id=user.id,
            title="formal resume",
            current_version_number=1,
            source_type=RESUME_SOURCE_FORMAL,
            is_default=True,
        )
        job = JobPosting(
            title="Python Backend Intern",
            company="Example Inc",
            location="Hangzhou",
            publish_time="2026-07-24",
            skills='["Python", "FastAPI"]',
            source_link="https://example.com/jobs/formal-resume-match",
            status="approved",
            audit_comment="verified",
        )
        db.add_all([resume, job])
        db.flush()
        db.add(
            ResumeVersion(
                resume_id=resume.id,
                version_number=1,
                file_name="formal.txt",
                file_path="",
                content="Python FastAPI selected resume",
            )
        )
        db.commit()
        resume_id = resume.id
        job_id = job.id

    calls = []
    monkeypatch.setattr(
        matching_endpoint,
        "match_resume_to_jobs",
        lambda resume_text, *_args, **_kwargs: calls.append(resume_text)
        or [
            {
                "job_id": str(job_id),
                "title": "Python Backend Intern",
                "company": "Example Inc",
                "score": 90,
                "reason": "selected resume",
                "source_link": "https://example.com/jobs/formal-resume-match",
            }
        ],
    )

    response = client.post(
        "/api/v1/matching/run",
        headers=headers,
        json={
            "resume_id": resume_id,
            "resume_text": "Manual text should be ignored",
            "target_position": "Python 后端实习生",
        },
    )

    assert response.status_code == 200
    assert calls == ["Python FastAPI selected resume"]
    with session_factory() as db:
        resumes = db.scalars(select(Resume)).all()
        records = db.scalars(select(MatchingRecord)).all()
        assert len(resumes) == 1
        assert resumes[0].source_type == RESUME_SOURCE_FORMAL
        assert records[0].resume_id == resume_id


def test_matching_history_backfills_skill_gap_for_legacy_records(
    client,
    session_factory,
):
    headers = register_and_login(client)
    with session_factory() as db:
        user = db.scalar(select(User).where(User.username == "matching-user"))
        job = JobPosting(
            title="Python Backend Intern",
            company="Example Inc",
            location="Hangzhou",
            publish_time="2026-07-24",
            skills='["Python", "FastAPI", "Docker"]',
            source_link="https://example.com/jobs/legacy-matching-history",
            status="approved",
            audit_comment="verified",
        )
        resume = Resume(
            user_id=user.id,
            title="Legacy matching resume",
            current_version_number=1,
        )
        db.add_all([job, resume])
        db.flush()
        db.add(
            ResumeVersion(
                resume_id=resume.id,
                version_number=1,
                file_name="legacy.txt",
                file_path="",
                content="Python FastAPI project",
            )
        )
        db.add(
            MatchingRecord(
                user_id=user.id,
                resume_id=resume.id,
                job_id=job.id,
                total_score=70,
                details=json.dumps(
                    {
                        "score": 70,
                        "reason": "legacy semantic match",
                        "source_link": job.source_link,
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

    response = client.get("/api/v1/matching/history", headers=headers)

    assert response.status_code == 200
    details = response.json()["data"][0]["details"]
    assert details["matched_skills"] == ["Python", "FastAPI"]
    assert details["missing_skills"] == ["Docker"]
    assert details["semantic_score"] == 85.0
    assert details["skill_coverage_score"] == 88.89
    assert details["score"] == 86.56
    assert response.json()["data"][0]["total_score"] == 87
    assert details["ability_breakdown"]["language_score"] == 100.0
    assert "Docker" in details["gap_analysis"]
