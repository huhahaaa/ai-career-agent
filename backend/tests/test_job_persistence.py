from sqlalchemy import select

from app.core.security import hash_password
from app.models.job import JobPosting, JobReviewRecord
from app.models.user import User


def auth_header(token):
    return {"Authorization": "Bearer %s" % token}


def register_and_login(client, username="job-user", email="job@example.com"):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    return auth_header(response.json()["data"]["access_token"])


def create_and_login_reviewer(client, session_factory):
    with session_factory() as db:
        db.add(
            User(
                username="job-reviewer",
                email="job-reviewer@example.com",
                hashed_password=hash_password("password123"),
                role="reviewer",
            )
        )
        db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "job-reviewer", "password": "password123"},
    )
    return auth_header(response.json()["data"]["access_token"])


def job_payload(source_link="https://example.com/jobs/persisted-python", source_id=None):
    return {
        "source_id": source_id,
        "title": "Python Backend Intern",
        "company": "Example Inc",
        "location": "Hangzhou",
        "salary_range": "12k-18k",
        "education": "本科",
        "experience": "应届",
        "responsibilities": "负责 FastAPI 后端接口开发和数据库设计。",
        "requirements": "熟悉 Python、SQL 和 Git。",
        "publish_time": "2026-07-24",
        "skills": ["Python", "FastAPI", "SQL"],
        "source_site": "Example Jobs",
        "source_link": source_link,
    }


def test_imported_job_is_persisted_and_listed(client, session_factory):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/jobs/import",
        headers=headers,
        json=job_payload(),
    )
    list_response = client.get("/api/v1/jobs", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "pending"
    assert response.json()["data"]["salary_range"] == "12k-18k"
    assert response.json()["data"]["education"] == "本科"
    assert response.json()["data"]["experience"] == "应届"
    assert response.json()["data"]["source_site"] == "Example Jobs"
    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["skills"] == ["Python", "FastAPI", "SQL"]
    assert list_response.json()["data"][0]["requirements"] == "熟悉 Python、SQL 和 Git。"

    with session_factory() as db:
        jobs = db.scalars(select(JobPosting)).all()
        assert len(jobs) == 1
        assert jobs[0].title == "Python Backend Intern"
        assert jobs[0].status == "pending"
        assert jobs[0].salary_range == "12k-18k"


def test_duplicate_job_source_link_is_rejected(client):
    headers = register_and_login(client)
    payload = job_payload("https://example.com/jobs/duplicate")

    first = client.post("/api/v1/jobs/import", headers=headers, json=payload)
    duplicate = client.post("/api/v1/jobs/import", headers=headers, json=payload)

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == 40904


def test_jobs_with_distinct_source_ids_can_share_source_link(client):
    headers = register_and_login(client)

    first_payload = job_payload(
        "https://join.example.com/",
        source_id="CN-BE-001",
    )
    second_payload = job_payload(
        "https://join.example.com/",
        source_id="CN-BE-002",
    )
    second_payload["title"] = "Python Backend Intern B"

    first = client.post("/api/v1/jobs/import", headers=headers, json=first_payload)
    second = client.post("/api/v1/jobs/import", headers=headers, json=second_payload)
    list_response = client.get("/api/v1/jobs", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(list_response.json()["data"]) == 2
    assert {item["source_id"] for item in list_response.json()["data"]} == {
        "CN-BE-001",
        "CN-BE-002",
    }


def test_job_audit_persists_status_and_review_record(client, session_factory):
    student_headers = register_and_login(
        client,
        username="audit-job-user",
        email="audit-job@example.com",
    )
    imported = client.post(
        "/api/v1/jobs/import",
        headers=student_headers,
        json=job_payload("https://example.com/jobs/audit-persistence"),
    )
    job_id = imported.json()["data"]["id"]
    reviewer_headers = create_and_login_reviewer(client, session_factory)

    audit = client.patch(
        "/api/v1/jobs/%s/audit" % job_id,
        headers=reviewer_headers,
        json={"status": "approved", "comment": "source verified"},
    )
    approved = client.get("/api/v1/jobs/approved", headers=student_headers)

    assert audit.status_code == 200
    assert audit.json()["data"]["status"] == "approved"
    assert approved.status_code == 200
    assert approved.json()["data"][0]["id"] == job_id

    with session_factory() as db:
        job = db.get(JobPosting, job_id)
        records = db.scalars(select(JobReviewRecord)).all()
        assert job.status == "approved"
        assert job.audit_comment == "source verified"
        assert len(records) == 1
        assert records[0].decision == "approved"


def test_user_can_favorite_job_and_track_application_status(client):
    headers = register_and_login(client, username="application-user", email="application@example.com")
    imported = client.post(
        "/api/v1/jobs/import",
        headers=headers,
        json=job_payload("https://example.com/jobs/application-tracking"),
    )
    job_id = imported.json()["data"]["id"]

    update = client.patch(
        "/api/v1/jobs/%s/application" % job_id,
        headers=headers,
        json={
            "is_favorite": True,
            "application_status": "applied",
            "note": "已投递，等待面试通知",
        },
    )
    list_response = client.get("/api/v1/jobs", headers=headers)
    applications = client.get("/api/v1/jobs/applications", headers=headers)

    assert update.status_code == 200
    assert update.json()["data"]["is_favorite"] is True
    assert update.json()["data"]["application_status"] == "applied"
    assert list_response.json()["data"][0]["is_favorite"] is True
    assert list_response.json()["data"][0]["application_note"] == "已投递，等待面试通知"
    assert applications.status_code == 200
    assert applications.json()["data"][0]["job_id"] == job_id
    assert applications.json()["data"][0]["application_status"] == "applied"

    cleared = client.patch(
        "/api/v1/jobs/%s/application" % job_id,
        headers=headers,
        json={"application_status": ""},
    )

    assert cleared.status_code == 200
    assert cleared.json()["data"]["application_status"] == ""
