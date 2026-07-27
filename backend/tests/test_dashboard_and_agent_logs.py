from sqlalchemy import select

from app.models.agent_log import AgentLog
from app.models.interview import InterviewMessage, InterviewSession
from app.models.job import JobPosting
from app.models.matching import MatchingRecord
from app.models.resume import (
    RESUME_SOURCE_FORMAL,
    RESUME_SOURCE_INTERVIEW_SNAPSHOT,
    RESUME_SOURCE_MATCHING_SNAPSHOT,
    Resume,
    ResumeVersion,
)
from app.models.user import User


def register_and_login(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "dashboard-user",
            "email": "dashboard@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "dashboard-user", "password": "password123"},
    )
    return {"Authorization": "Bearer %s" % response.json()["data"]["access_token"]}


def _current_user_id(session_factory):
    with session_factory() as db:
        return db.scalar(select(User.id).where(User.username == "dashboard-user"))


def test_dashboard_returns_real_user_and_job_statistics(client, session_factory):
    headers = register_and_login(client)
    user_id = _current_user_id(session_factory)
    with session_factory() as db:
        resume = Resume(
            user_id=user_id,
            title="dashboard-resume",
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
                file_name="resume.txt",
                file_path="",
                content="Python FastAPI SQL pytest project",
            )
        )
        job = JobPosting(
            title="Python Backend Intern",
            company="Example Inc",
            location="杭州",
            publish_time="2026-07-25",
            skills='["Python", "FastAPI", "SQL"]',
            source_link="https://example.com/jobs/dashboard-python",
            status="approved",
        )
        db.add(job)
        db.flush()
        interview = InterviewSession(
            user_id=user_id,
            resume_id=resume.id,
            target_job_id=job.id,
            status="completed",
            score=82,
            feedback="good",
        )
        db.add(interview)
        db.flush()
        db.add(
            InterviewMessage(
                session_id=interview.id,
                role="user",
                content="I completed the dashboard interview.",
                score=82,
                feedback="good",
            )
        )
        db.add(
            MatchingRecord(
                user_id=user_id,
                resume_id=resume.id,
                job_id=job.id,
                total_score=88,
                details="{}",
            )
        )
        db.commit()

    response = client.get("/api/v1/admin/dashboard", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_resumes"] == 1
    assert data["total_jobs"] == 1
    assert data["total_interviews"] == 1
    assert data["avg_score"] == 82
    assert data["recent_interviews"][0]["score"] == 82
    assert data["job_city_distribution"][0] == {"name": "杭州", "value": 1}
    assert data["job_skill_requirements"][0] == {"skill": "Python", "count": 1}
    assert data["multi_job_scores"][0]["score"] == 88
    assert data["skill_distribution"]
    assert data["active_resume"]["id"] == resume.id


def test_dashboard_uses_default_formal_resume_and_ignores_snapshots(
    client,
    session_factory,
):
    headers = register_and_login(client)
    user_id = _current_user_id(session_factory)
    with session_factory() as db:
        old_resume = Resume(
            user_id=user_id,
            title="old",
            current_version_number=1,
            source_type=RESUME_SOURCE_FORMAL,
            is_default=False,
        )
        default_resume = Resume(
            user_id=user_id,
            title="default",
            current_version_number=1,
            source_type=RESUME_SOURCE_FORMAL,
            is_default=True,
        )
        matching_snapshot = Resume(
            user_id=user_id,
            title="岗位匹配简历快照",
            current_version_number=1,
            source_type=RESUME_SOURCE_MATCHING_SNAPSHOT,
        )
        interview_snapshot = Resume(
            user_id=user_id,
            title="模拟面试简历快照",
            current_version_number=1,
            source_type=RESUME_SOURCE_INTERVIEW_SNAPSHOT,
        )
        db.add_all([old_resume, default_resume, matching_snapshot, interview_snapshot])
        db.flush()
        db.add_all(
            [
                ResumeVersion(
                    resume_id=old_resume.id,
                    version_number=1,
                    file_name="old.txt",
                    file_path="",
                    content="React TypeScript frontend",
                ),
                ResumeVersion(
                    resume_id=default_resume.id,
                    version_number=1,
                    file_name="default.txt",
                    file_path="",
                    content="Python FastAPI SQL backend",
                ),
                ResumeVersion(
                    resume_id=matching_snapshot.id,
                    version_number=1,
                    file_name="matching-input.txt",
                    file_path="",
                    content="Docker Redis snapshot only",
                ),
                ResumeVersion(
                    resume_id=interview_snapshot.id,
                    version_number=1,
                    file_name="interview-input.txt",
                    file_path="",
                    content="MongoDB Agent snapshot only",
                ),
            ]
        )
        db.commit()
        default_id = default_resume.id

    response = client.get("/api/v1/admin/dashboard", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    skill_names = [item["name"] for item in data["skill_distribution"]]
    assert data["total_resumes"] == 2
    assert data["active_resume"]["id"] == default_id
    assert "Python" in skill_names
    assert "FastAPI" in skill_names
    assert "Docker" not in skill_names
    assert "MongoDB" not in skill_names


def test_dashboard_ignores_unfinished_interviews_in_average_score(client, session_factory):
    headers = register_and_login(client)
    user_id = _current_user_id(session_factory)
    with session_factory() as db:
        db.add(
            InterviewSession(
                user_id=user_id,
                status="running",
                score=None,
                feedback="",
            )
        )
        completed = InterviewSession(
            user_id=user_id,
            status="completed",
            score=90,
            feedback="done",
        )
        db.add(completed)
        db.flush()
        db.add(
            InterviewMessage(
                session_id=completed.id,
                role="user",
                content="Completed answer with enough detail.",
                score=90,
                feedback="done",
            )
        )
        db.commit()

    response = client.get("/api/v1/admin/dashboard", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_interviews"] == 1
    assert data["avg_score"] == 90
    assert all(item["status"] == "completed" for item in data["recent_interviews"])


def test_interview_and_resume_agent_calls_are_logged(client, session_factory):
    headers = register_and_login(client)
    start = client.post(
        "/api/v1/interviews/start",
        headers=headers,
        json={
            "resume_text": "Python FastAPI SQL 项目经验，负责后端接口和数据库设计。",
            "target_position": "Python 后端实习生",
        },
    )
    session_id = start.json()["data"]["session_id"]
    answer = client.post(
        "/api/v1/interviews/%s/answer" % session_id,
        headers=headers,
        json={
            "answer": (
                "我用 Python、FastAPI 和 SQLAlchemy 完成 4 个接口，"
                "通过 pytest 覆盖主要流程并减少 20% 回归问题。"
            )
        },
    )
    finish = client.post(
        "/api/v1/interviews/%s/finish" % session_id,
        headers=headers,
    )
    audit = client.post(
        "/api/v1/resumes/audit",
        headers=headers,
        json={
            "resume_text": "我熟悉 Python，了解数据库，参与过后端接口开发。",
            "target_position": "Python 后端实习生",
        },
    )

    assert start.status_code == 200
    assert answer.status_code == 200
    assert finish.status_code == 200
    assert audit.status_code == 200
    with session_factory() as db:
        logs = db.scalars(select(AgentLog).order_by(AgentLog.id)).all()
        operations = [log.operation for log in logs]
        assert operations == [
            "interview.start",
            "interview.answer",
            "interview.finish",
            "resume.audit",
        ]
        assert all(log.status == "success" for log in logs)
        assert all(log.duration_ms is not None for log in logs)
