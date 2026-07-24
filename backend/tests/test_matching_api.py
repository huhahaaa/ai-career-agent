from app.api.v1.endpoints import matching as matching_endpoint
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
