from app.core.security import hash_password
from app.models.user import User


def register_and_login_student(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "student1",
            "email": "student1@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "student1", "password": "password123"},
    )
    return response.json()["data"]["access_token"]


def create_and_login_reviewer(client, session_factory):
    with session_factory() as db:
        db.add(
            User(
                username="reviewer1",
                email="reviewer1@example.com",
                hashed_password=hash_password("password123"),
                role="reviewer",
            )
        )
        db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "reviewer1", "password": "password123"},
    )
    return response.json()["data"]["access_token"]


def authorization_header(token):
    return {"Authorization": "Bearer %s" % token}


def test_student_cannot_audit_job(client):
    student_token = register_and_login_student(client)
    headers = authorization_header(student_token)
    imported = client.post(
        "/api/v1/jobs/import",
        headers=headers,
        json={
            "title": "Python Engineer",
            "company": "Example Inc",
            "location": "Hangzhou",
            "publish_time": "2026-07-24",
            "skills": ["Python", "SQL"],
            "source_link": "https://example.com/jobs/python-engineer",
        },
    )
    job_id = imported.json()["data"]["id"]

    response = client.patch(
        "/api/v1/jobs/%s/audit" % job_id,
        headers=headers,
        json={"status": "approved", "comment": "fields are complete"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == 40301


def test_reviewer_can_audit_job_and_read_admin_metrics(client, session_factory):
    student_token = register_and_login_student(client)
    imported = client.post(
        "/api/v1/jobs/import",
        headers=authorization_header(student_token),
        json={
            "title": "Backend Engineer",
            "company": "Example Inc",
            "location": "Shanghai",
            "publish_time": "2026-07-24",
            "skills": ["Python", "FastAPI"],
            "source_link": "https://example.com/jobs/backend-engineer",
        },
    )
    job_id = imported.json()["data"]["id"]
    reviewer_token = create_and_login_reviewer(client, session_factory)
    reviewer_headers = authorization_header(reviewer_token)

    audit_response = client.patch(
        "/api/v1/jobs/%s/audit" % job_id,
        headers=reviewer_headers,
        json={"status": "approved", "comment": "source verified"},
    )
    metrics_response = client.get(
        "/api/v1/admin/metrics",
        headers=reviewer_headers,
    )

    assert audit_response.status_code == 200
    assert audit_response.json()["data"]["status"] == "approved"
    assert metrics_response.status_code == 200
    assert metrics_response.json()["code"] == 0
