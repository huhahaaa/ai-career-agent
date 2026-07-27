from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.db.init_db import init_db


EXPECTED_TABLES = {
    "agent_logs",
    "interview_messages",
    "interview_sessions",
    "job_applications",
    "job_postings",
    "job_review_records",
    "matching_records",
    "resume_audit_reports",
    "resume_versions",
    "resumes",
    "users",
}


def test_init_db_creates_core_tables_and_relationships():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    init_db(engine)
    database = inspect(engine)

    assert EXPECTED_TABLES == set(database.get_table_names())

    matching_foreign_keys = {
        foreign_key["referred_table"]
        for foreign_key in database.get_foreign_keys("matching_records")
    }
    assert matching_foreign_keys == {"users", "resumes", "job_postings"}

    job_unique_indexes = {
        tuple(index["column_names"])
        for index in database.get_indexes("job_postings")
        if index["unique"]
    }
    assert ("source_id",) in job_unique_indexes
    assert ("source_link",) not in job_unique_indexes
