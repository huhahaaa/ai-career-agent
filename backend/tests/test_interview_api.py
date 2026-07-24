from sqlalchemy import select

from app.models.interview import InterviewMessage, InterviewSession
from app.models.resume import Resume, ResumeVersion


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


def test_interview_session_messages_and_report_are_persisted(
    client,
    session_factory,
):
    headers = register_and_login(client)
    start_response = client.post(
        "/api/v1/interviews/start",
        headers=headers,
        json={
            "resume_text": "Python FastAPI project experience",
            "target_position": "Python Backend Intern",
        },
    )
    session_id = start_response.json()["data"]["session_id"]

    answer_response = client.post(
        "/api/v1/interviews/%s/answer" % session_id,
        headers=headers,
        json={
            "answer": (
                "我在项目中负责 FastAPI 接口、数据库模型和接口测试，"
                "并通过 pytest 覆盖权限校验与异常流程。上线前我会先确认日志、"
                "数据库慢查询、接口响应时间和最近变更，再用复现用例定位问题。"
            )
        },
    )
    history_response = client.get("/api/v1/interviews/history", headers=headers)
    report_response = client.get(
        "/api/v1/interviews/%s/report" % session_id,
        headers=headers,
    )

    assert answer_response.status_code == 200
    assert history_response.status_code == 200
    assert history_response.json()["data"][0]["id"] == int(session_id)
    assert history_response.json()["data"][0]["score"] == 80
    assert report_response.status_code == 200
    assert len(report_response.json()["data"]["messages"]) == 3

    with session_factory() as db:
        assert len(db.scalars(select(Resume)).all()) == 1
        assert len(db.scalars(select(ResumeVersion)).all()) == 1
        sessions = db.scalars(select(InterviewSession)).all()
        messages = db.scalars(select(InterviewMessage)).all()
        assert len(sessions) == 1
        assert sessions[0].score == 80
        assert len(messages) == 3
