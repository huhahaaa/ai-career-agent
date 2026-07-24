def register_and_login(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "interview-user",
            "email": "interview@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "interview-user", "password": "password123"},
    )
    return {"Authorization": "Bearer %s" % response.json()["data"]["access_token"]}


def test_interview_accepts_vector_job_identifier(client):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/interviews/start",
        headers=headers,
        json={
            "resume_text": "Python and machine learning project experience",
            "target_position": "Machine Learning Intern",
            "target_job_id": "JOB-024",
        },
    )

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["data"]["session_id"]
    assert "Machine Learning Intern" in response.json()["data"]["question"]
