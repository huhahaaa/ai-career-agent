from sqlalchemy import select

from app.models.resume import ResumeAuditReport


def register_and_login(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "resume-user",
            "email": "resume@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "resume-user", "password": "password123"},
    )
    return {"Authorization": "Bearer %s" % response.json()["data"]["access_token"]}


def test_resume_upload_list_detail_and_delete(client):
    headers = register_and_login(client)

    empty_list = client.get("/api/v1/resumes", headers=headers)
    upload = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("resume.txt", b"Python FastAPI SQL project", "text/plain")},
    )
    resume_id = upload.json()["data"]["id"]
    list_response = client.get("/api/v1/resumes", headers=headers)
    detail_response = client.get("/api/v1/resumes/%s" % resume_id, headers=headers)
    delete_response = client.delete("/api/v1/resumes/%s" % resume_id, headers=headers)
    final_list = client.get("/api/v1/resumes", headers=headers)

    assert empty_list.status_code == 200
    assert empty_list.json()["data"] == []
    assert upload.status_code == 200
    assert upload.json()["data"]["filename"] == "resume.txt"
    assert list_response.json()["data"][0]["id"] == resume_id
    assert detail_response.json()["data"]["versions"][0]["content"] == (
        "Python FastAPI SQL project"
    )
    assert delete_response.status_code == 200
    assert final_list.json()["data"] == []


def test_resume_upload_rejects_unsupported_file_type(client):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("resume.exe", b"bad", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert response.json()["code"] == 42202


def test_resume_text_audit_is_persisted(client, session_factory):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/resumes/audit",
        headers=headers,
        json={
            "resume_text": "我熟悉 Python，了解数据库，参与过后端接口开发。",
            "target_position": "Python 后端实习生",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["score"] >= 60
    assert response.json()["data"]["risk_level"] in {"低", "中", "高"}
    assert response.json()["data"]["risk_flags"]
    with session_factory() as db:
        reports = db.scalars(select(ResumeAuditReport)).all()
        assert len(reports) == 1
        assert reports[0].resume_id is None


def test_resume_audit_can_attach_to_uploaded_resume(client, session_factory):
    headers = register_and_login(client)
    upload = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("resume.txt", b"Python FastAPI SQL project", "text/plain")},
    )
    resume_id = upload.json()["data"]["id"]

    audit = client.post(
        "/api/v1/resumes/audit",
        headers=headers,
        json={
            "resume_id": resume_id,
            "resume_text": "我熟悉 Python，了解 FastAPI，具有一定的数据库经验。",
            "target_position": "Python 后端实习生",
        },
    )
    list_response = client.get("/api/v1/resumes", headers=headers)

    assert audit.status_code == 200
    assert list_response.json()["data"][0]["status"] == "approved"
    with session_factory() as db:
        reports = db.scalars(select(ResumeAuditReport)).all()
        assert len(reports) == 1
        assert reports[0].resume_id == resume_id
