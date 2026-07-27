from sqlalchemy import select

from app.core.security import verify_password
from app.models.user import User


REGISTER_PAYLOAD = {
    "username": "student1",
    "email": "student1@example.com",
    "password": "password123",
}


def register_user(client, payload=None):
    return client.post(
        "/api/v1/auth/register",
        json=payload or REGISTER_PAYLOAD,
    )


def login_user(client, password="password123"):
    return client.post(
        "/api/v1/auth/login",
        json={"username": "student1", "password": password},
    )


def test_register_persists_user_with_hashed_password(client, session_factory):
    response = register_user(client)

    assert response.status_code == 201
    assert response.json()["code"] == 0
    assert response.json()["data"]["role"] == "student"

    with session_factory() as db:
        user = db.scalar(select(User).where(User.username == "student1"))
        assert user is not None
        assert user.hashed_password != REGISTER_PAYLOAD["password"]
        assert verify_password(REGISTER_PAYLOAD["password"], user.hashed_password)


def test_register_rejects_duplicate_username(client):
    register_user(client)

    response = register_user(
        client,
        {
            "username": "student1",
            "email": "another@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": 40901,
        "message": "username already exists",
        "data": None,
    }


def test_login_and_read_current_user(client):
    register_user(client)

    login_response = login_user(client)
    assert login_response.status_code == 200
    token_data = login_response.json()["data"]
    assert token_data["token_type"] == "bearer"
    assert token_data["access_token"] != "mock-token"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer %s" % token_data["access_token"]},
    )
    assert me_response.status_code == 200
    assert me_response.json()["data"]["username"] == "student1"


def test_login_rejects_incorrect_password(client):
    register_user(client)

    response = login_user(client, password="incorrect-password")

    assert response.status_code == 401
    assert response.json()["code"] == 40101


def test_current_user_requires_token(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "code": 40102,
        "message": "authentication required",
        "data": None,
    }


def test_invalid_registration_uses_validation_envelope(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "x", "email": "invalid", "password": "short"},
    )

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == 42200
    assert body["message"] == "request validation failed"
    assert len(body["data"]["errors"]) == 3


def test_openapi_uses_bearer_token_authorization(client):
    response = client.get("/openapi.json")

    security_scheme = response.json()["components"]["securitySchemes"]["BearerAuth"]
    assert security_scheme["type"] == "http"
    assert security_scheme["scheme"] == "bearer"
