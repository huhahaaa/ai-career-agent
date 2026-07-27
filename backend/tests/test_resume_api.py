from io import BytesIO
import zipfile

from docx import Document
from pypdf import PdfWriter
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


def build_docx_bytes(text: str) -> bytes:
    buffer = BytesIO()
    document = Document()
    document.add_paragraph(text)
    document.save(buffer)
    return buffer.getvalue()


def build_blank_pdf_bytes() -> bytes:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buffer)
    return buffer.getvalue()


def build_broken_docx_bytes() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/theme/theme/themeManager.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.themeManager+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        )
        archive.writestr("theme/theme/themeManager.xml", "<themeManager />")
    return buffer.getvalue()


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


def test_docx_upload_extracts_text_and_resume_versions_can_be_compared(client):
    headers = register_and_login(client)
    upload = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={
            "file": (
                "backend.docx",
                build_docx_bytes("Python FastAPI SQL project improved API response by 30%"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    resume_id = upload.json()["data"]["id"]

    detail = client.get("/api/v1/resumes/%s" % resume_id, headers=headers)
    new_version = client.post(
        "/api/v1/resumes/%s/versions" % resume_id,
        headers=headers,
        json={
            "file_name": "backend-v2.md",
            "content": (
                "Python FastAPI SQL SQLAlchemy Redis Docker pytest JWT project "
                "improved API response by 30%"
            ),
        },
    )
    compare = client.get(
        "/api/v1/resumes/%s/compare?from_version=1&to_version=2&target_position=Python%%20Backend"
        % resume_id,
        headers=headers,
    )

    assert upload.status_code == 200
    assert upload.json()["data"]["parsed_text_length"] > 0
    assert "FastAPI" in detail.json()["data"]["versions"][0]["content"]
    assert new_version.status_code == 200
    assert new_version.json()["data"]["version"] == 2
    assert len(new_version.json()["data"]["versions"]) == 2
    assert compare.status_code == 200
    assert "Docker" in compare.json()["data"]["added_skills"]
    assert compare.json()["data"]["score_delta"] > 0


def test_broken_docx_upload_is_rejected(client):
    headers = register_and_login(client)
    upload = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={
            "file": (
                "broken.docx",
                build_broken_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert upload.status_code == 422
    assert "简历解析异常" in upload.json()["message"]


def test_resume_compare_without_target_does_not_assume_backend_role(client):
    headers = register_and_login(client)
    upload = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("resume.txt", b"Design portfolio video project 30%", "text/plain")},
    )
    resume_id = upload.json()["data"]["id"]
    client.post(
        "/api/v1/resumes/%s/versions" % resume_id,
        headers=headers,
        json={
            "file_name": "resume-v2.md",
            "content": "Design portfolio video project 30% with teamwork and data analysis.",
        },
    )

    compare = client.get(
        "/api/v1/resumes/%s/compare?from_version=1&to_version=2" % resume_id,
        headers=headers,
    )

    assert compare.status_code == 200
    assert compare.json()["data"]["after"]["target_bucket"] == ""
    assert compare.json()["data"]["after"]["missing_keywords"] == []


def test_resume_upload_rejects_unsupported_file_type(client):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("resume.exe", b"bad", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert response.json()["code"] == 42202


def test_non_text_resume_upload_is_rejected_with_clear_error(client):
    headers = register_and_login(client)

    upload = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("resume.pdf", build_blank_pdf_bytes(), "application/pdf")},
    )

    assert upload.status_code == 422
    assert upload.json()["code"] == 42208

    # 无法提取文本的文件不应留下空简历记录
    listing = client.get("/api/v1/resumes", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["data"] == []


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
    assert "异常处理" in response.json()["data"]["missing_keywords"]
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
            "resume_version": 1,
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
    assert latest_report["resume_version"] == 1
    assert latest_report["target_position"] == "Python 后端实习生"
    assert detail_response.json()["data"]["audit_reports"][0]["id"] == latest_report["id"]
    with session_factory() as db:
        reports = db.scalars(select(ResumeAuditReport)).all()
        assert len(reports) == 1
        assert reports[0].resume_id == resume_id
        assert reports[0].resume_version_number == 1
        assert reports[0].target_position == "Python 后端实习生"


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
