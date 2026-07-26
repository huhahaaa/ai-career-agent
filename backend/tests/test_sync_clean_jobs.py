import json

from sqlalchemy import select

from app.models.job import JobPosting
from scripts.sync_clean_jobs import read_jsonl, sync_clean_jobs


def write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
        encoding="utf-8",
    )


def clean_job(source_link, title, salary_range, source_id=None):
    return {
        "source_id": source_id,
        "title": title,
        "company": "Example Inc",
        "location": "Hangzhou",
        "salary_range": salary_range,
        "education": "Bachelor",
        "experience": "Intern",
        "responsibilities": "Build APIs with FastAPI.",
        "requirements": "Python, FastAPI, SQL.",
        "publish_time": "2026-07-24",
        "skills": ["Python", "FastAPI", "SQL"],
        "source_site": "Example Jobs",
        "source_link": source_link,
        "status": "approved",
        "audit_comment": "source verified",
    }


def test_sync_clean_jobs_upserts_extended_fields(session_factory, tmp_path):
    data_file = tmp_path / "jobs_clean.jsonl"
    write_jsonl(
        data_file,
        [
            clean_job(
                "https://example.com/jobs/existing",
                "Updated Backend Intern",
                "12k-18k",
            ),
            clean_job(
                "https://example.com/jobs/new",
                "New Backend Intern",
                "10k-15k",
            ),
        ],
    )
    with session_factory() as db:
        db.add(
            JobPosting(
                title="Old Backend Intern",
                company="Old Inc",
                location="Shanghai",
                publish_time="2026-07-01",
                skills="[]",
                source_link="https://example.com/jobs/existing",
                status="pending",
            )
        )
        db.commit()

    with session_factory() as db:
        result = sync_clean_jobs(db, read_jsonl(data_file))

    with session_factory() as db:
        jobs = db.scalars(select(JobPosting).order_by(JobPosting.source_link)).all()

    assert result == {
        "inserted_count": 1,
        "updated_count": 1,
        "skipped_count": 0,
    }
    assert len(jobs) == 2
    assert jobs[0].title == "Updated Backend Intern"
    assert jobs[0].salary_range == "12k-18k"
    assert jobs[0].education == "Bachelor"
    assert jobs[0].requirements == "Python, FastAPI, SQL."
    assert json.loads(jobs[0].skills) == ["Python", "FastAPI", "SQL"]
    assert jobs[0].status == "approved"
    assert jobs[1].source_site == "Example Jobs"


def test_sync_clean_jobs_keeps_distinct_source_ids_with_same_link(session_factory, tmp_path):
    data_file = tmp_path / "jobs_chinese.jsonl"
    write_jsonl(
        data_file,
        [
            clean_job(
                "https://join.example.com/",
                "Backend Intern A",
                "12k-18k",
                source_id="CN-BE-001",
            ),
            clean_job(
                "https://join.example.com/",
                "Backend Intern B",
                "15k-20k",
                source_id="CN-BE-002",
            ),
        ],
    )

    with session_factory() as db:
        result = sync_clean_jobs(db, read_jsonl(data_file))

    with session_factory() as db:
        jobs = db.scalars(select(JobPosting).order_by(JobPosting.source_id)).all()

    assert result == {
        "inserted_count": 2,
        "updated_count": 0,
        "skipped_count": 0,
    }
    assert [job.source_id for job in jobs] == ["CN-BE-001", "CN-BE-002"]
    assert len({job.source_link for job in jobs}) == 1
