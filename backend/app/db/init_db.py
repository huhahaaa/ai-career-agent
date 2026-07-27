from sqlalchemy.engine import Engine
from sqlalchemy import inspect, text

import app.models  # noqa: F401
from app.db.session import Base, engine


def _ensure_sqlite_schema(bind: Engine) -> None:
    if bind.dialect.name != "sqlite":
        return

    inspector = inspect(bind)
    if "resume_audit_reports" not in inspector.get_table_names():
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("resume_audit_reports")
    }
    if "missing_keywords" not in columns:
        with bind.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE resume_audit_reports "
                    "ADD COLUMN missing_keywords TEXT NOT NULL DEFAULT '[]'"
                )
            )

    resume_columns = {
        column["name"]
        for column in inspector.get_columns("resumes")
    } if "resumes" in inspector.get_table_names() else set()
    with bind.begin() as connection:
        if "source_type" not in resume_columns:
            connection.execute(
                text(
                    "ALTER TABLE resumes "
                    "ADD COLUMN source_type VARCHAR(32) NOT NULL DEFAULT 'formal'"
                )
            )
        if "is_default" not in resume_columns:
            connection.execute(
                text(
                    "ALTER TABLE resumes "
                    "ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT 0"
                )
            )
        connection.execute(
            text(
                "UPDATE resumes "
                "SET source_type = 'matching_snapshot' "
                "WHERE title = '岗位匹配简历快照'"
            )
        )
        connection.execute(
            text(
                "UPDATE resumes "
                "SET source_type = 'matching_snapshot', is_default = 0 "
                "WHERE EXISTS ("
                "  SELECT 1 FROM resume_versions v "
                "  WHERE v.resume_id = resumes.id "
                "  AND v.file_name = 'matching-input.txt'"
                ")"
            )
        )
        connection.execute(
            text(
                "UPDATE resumes "
                "SET source_type = 'interview_snapshot' "
                "WHERE title = '模拟面试简历快照'"
            )
        )
        connection.execute(
            text(
                "UPDATE resumes "
                "SET source_type = 'interview_snapshot', is_default = 0 "
                "WHERE EXISTS ("
                "  SELECT 1 FROM resume_versions v "
                "  WHERE v.resume_id = resumes.id "
                "  AND v.file_name = 'interview-input.txt'"
                ")"
            )
        )
        connection.execute(
            text(
                "UPDATE resumes "
                "SET is_default = 1 "
                "WHERE source_type = 'formal' "
                "AND id IN ("
                "  SELECT MIN(r.id) FROM resumes r "
                "  WHERE r.source_type = 'formal' "
                "  AND NOT EXISTS ("
                "    SELECT 1 FROM resumes d "
                "    WHERE d.user_id = r.user_id "
                "    AND d.source_type = 'formal' "
                "    AND d.is_default = 1"
                "  ) "
                "  GROUP BY r.user_id"
                ")"
            )
        )


def init_db(bind: Engine = engine) -> None:
    Base.metadata.create_all(bind=bind)
    _ensure_sqlite_schema(bind)
