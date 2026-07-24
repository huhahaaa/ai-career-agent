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
