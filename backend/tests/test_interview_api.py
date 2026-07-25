from sqlalchemy import select

from app.models.interview import InterviewMessage, InterviewSession
from app.models.resume import RESUME_SOURCE_FORMAL, RESUME_SOURCE_INTERVIEW_SNAPSHOT, Resume, ResumeVersion
from app.models.user import User


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
    assert response.json()["data"]["total_questions"] == 8


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
                "我在项目中负责 3 个 FastAPI 接口、数据库模型和接口测试，"
                "并通过 pytest 覆盖权限校验与异常流程，接口缺陷减少 30%。"
                "上线前我会先确认日志、数据库慢查询、接口响应时间和最近变更，"
                "再用复现用例定位问题。"
            )
        },
    )
    finish_response = client.post(
        "/api/v1/interviews/%s/finish" % session_id,
        headers=headers,
    )
    history_response = client.get("/api/v1/interviews/history", headers=headers)
    report_response = client.get(
        "/api/v1/interviews/%s/report" % session_id,
        headers=headers,
    )

    assert answer_response.status_code == 200
    assert answer_response.json()["data"]["score"] >= 70
    assert answer_response.json()["data"]["dimension_scores"]["total"] >= 70
    assert finish_response.status_code == 200
    assert finish_response.json()["data"]["overall_score"] >= 70
    assert finish_response.json()["data"]["star_suggestions"]
    assert finish_response.json()["data"]["practice_plan"]
    assert history_response.status_code == 200
    assert history_response.json()["data"][0]["id"] == int(session_id)
    assert history_response.json()["data"][0]["score"] >= 70
    assert report_response.status_code == 200
    assert report_response.json()["data"]["agent_report"]["overall_score"] >= 70
    assert len(report_response.json()["data"]["messages"]) == 3

    with session_factory() as db:
        resumes = db.scalars(select(Resume)).all()
        assert len(resumes) == 1
        assert resumes[0].source_type == RESUME_SOURCE_INTERVIEW_SNAPSHOT
        assert len(db.scalars(select(ResumeVersion)).all()) == 1
        sessions = db.scalars(select(InterviewSession)).all()
        messages = db.scalars(select(InterviewMessage)).all()
        assert len(sessions) == 1
        assert sessions[0].score >= 70
        assert sessions[0].status == "completed"
        assert len(messages) == 4


def test_interview_can_use_existing_formal_resume_without_creating_snapshot(
    client,
    session_factory,
):
    headers = register_and_login(client)
    with session_factory() as db:
        user = db.scalar(select(User).where(User.username == "interview-user"))
        resume = Resume(
            user_id=user.id,
            title="formal resume",
            current_version_number=1,
            source_type=RESUME_SOURCE_FORMAL,
            is_default=True,
        )
        db.add(resume)
        db.flush()
        db.add(
            ResumeVersion(
                resume_id=resume.id,
                version_number=1,
                file_name="formal.txt",
                file_path="",
                content="Python FastAPI SQL selected interview resume",
            )
        )
        db.commit()
        resume_id = resume.id

    start_response = client.post(
        "/api/v1/interviews/start",
        headers=headers,
        json={
            "resume_id": resume_id,
            "resume_text": "Manual text should be ignored",
            "target_position": "Python Backend Intern",
        },
    )

    assert start_response.status_code == 200
    with session_factory() as db:
        resumes = db.scalars(select(Resume)).all()
        sessions = db.scalars(select(InterviewSession)).all()
        assert len(resumes) == 1
        assert resumes[0].source_type == RESUME_SOURCE_FORMAL
        assert sessions[0].resume_id == resume_id


def test_interview_agent_can_follow_up_before_scoring(client):
    headers = register_and_login(client)
    start_response = client.post(
        "/api/v1/interviews/start",
        headers=headers,
        json={
            "resume_text": "Python FastAPI SQL 项目经验，负责后端接口开发和数据库设计。",
            "target_position": "Python 后端实习生",
        },
    )
    session_id = start_response.json()["data"]["session_id"]

    followup_response = client.post(
        "/api/v1/interviews/%s/answer" % session_id,
        headers=headers,
        json={"answer": "我参与过一个项目。"},
    )

    assert followup_response.status_code == 200
    assert followup_response.json()["data"]["is_followup"] is True
    assert followup_response.json()["data"]["score"] is None
    assert followup_response.json()["data"]["followup_question"]

    score_response = client.post(
        "/api/v1/interviews/%s/answer" % session_id,
        headers=headers,
        json={
            "answer": (
                "我主要用 Python、FastAPI 和 SQLAlchemy 完成 4 个核心接口，"
                "补充 pytest 用例后把回归问题减少 20%。"
            )
        },
    )

    assert score_response.status_code == 200
    assert score_response.json()["data"]["is_followup"] is False
    assert score_response.json()["data"]["score"] >= 70
