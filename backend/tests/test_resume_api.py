from sqlalchemy import select

from app.api.v1.endpoints import resumes as resumes_endpoint
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


def test_resume_default_can_be_changed(client):
    headers = register_and_login(client)
    first = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("backend.txt", b"Python FastAPI SQL project", "text/plain")},
    ).json()["data"]
    second = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("frontend.txt", b"React TypeScript UI project", "text/plain")},
    ).json()["data"]

    initial_list = client.get("/api/v1/resumes", headers=headers)
    set_default = client.patch(
        "/api/v1/resumes/%s/default" % second["id"],
        headers=headers,
    )
    updated_list = client.get("/api/v1/resumes", headers=headers)

    assert first["is_default"] is True
    assert second["is_default"] is False
    assert initial_list.json()["data"][1]["is_default"] is True
    assert set_default.status_code == 200
    defaults = [
        item["id"]
        for item in updated_list.json()["data"]
        if item["is_default"]
    ]
    assert defaults == [second["id"]]


def test_resume_upload_rejects_unsupported_file_type(client):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("resume.exe", b"bad", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert response.json()["code"] == 42202


def test_non_text_resume_upload_does_not_create_fake_auditable_content(client):
    headers = register_and_login(client)

    upload = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("resume.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    resume_id = upload.json()["data"]["id"]
    detail_response = client.get("/api/v1/resumes/%s" % resume_id, headers=headers)

    assert upload.status_code == 200
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["versions"][0]["content"] == ""


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
    assert "pytest" in response.json()["data"]["missing_keywords"]
    assert "JWT" in response.json()["data"]["missing_keywords"]
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
    detail_response = client.get("/api/v1/resumes/%s" % resume_id, headers=headers)

    assert audit.status_code == 200
    assert list_response.json()["data"][0]["status"] == "approved"
    assert detail_response.status_code == 200
    latest_report = detail_response.json()["data"]["latest_report"]
    assert latest_report["score"] == audit.json()["data"]["score"]
    assert latest_report["risk_level"] in {"低", "中", "高"}
    assert detail_response.json()["data"]["audit_reports"][0]["id"] == latest_report["id"]
    with session_factory() as db:
        reports = db.scalars(select(ResumeAuditReport)).all()
        assert len(reports) == 1
        assert reports[0].resume_id == resume_id


def test_resume_missing_keywords_are_persisted(client, monkeypatch):
    headers = register_and_login(client)
    upload = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("resume.txt", b"Python FastAPI SQL project", "text/plain")},
    )
    resume_id = upload.json()["data"]["id"]

    monkeypatch.setattr(
        resumes_endpoint,
        "audit_resume_text",
        lambda *_args, **_kwargs: {
            "score": 82,
            "risk_flags": [],
            "suggestions": ["补充缓存和部署实践。"],
            "missing_keywords": ["Redis", "Docker", "接口性能优化"],
            "risk_level": "低",
        },
    )

    audit = client.post(
        "/api/v1/resumes/audit",
        headers=headers,
        json={
            "resume_id": resume_id,
            "resume_text": "Python FastAPI SQL project with backend API design.",
            "target_position": "Python 后端工程师",
        },
    )
    detail = client.get("/api/v1/resumes/%s" % resume_id, headers=headers)

    assert audit.status_code == 200
    assert audit.json()["data"]["missing_keywords"] == [
        "Redis",
        "Docker",
        "接口性能优化",
    ]
    assert detail.json()["data"]["latest_report"]["missing_keywords"] == [
        "Redis",
        "Docker",
        "接口性能优化",
    ]
