from sqlalchemy.engine import Engine
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

import app.models  # noqa: F401
from app.db.session import Base, engine


def _quote_sqlite_identifier(name: str) -> str:
    return '"%s"' % name.replace('"', '""')


def _add_sqlite_column_if_missing(connection, table_name: str, column_name: str, ddl: str) -> None:
    current_columns = {
        column["name"]
        for column in connection.execute(
            text("PRAGMA table_info(%s)" % _quote_sqlite_identifier(table_name))
        ).mappings().all()
    }
    if column_name in current_columns:
        return
    try:
        connection.execute(text(ddl))
    except OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


def _ensure_job_posting_schema(bind: Engine) -> None:
    inspector = inspect(bind)
    if "job_postings" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("job_postings")}
    with bind.begin() as connection:
        for column_name in ("category", "employment_type", "workplace_type"):
            if column_name not in columns:
                _add_sqlite_column_if_missing(
                    connection,
                    "job_postings",
                    column_name,
                    "ALTER TABLE job_postings "
                    "ADD COLUMN %s VARCHAR(64) NOT NULL DEFAULT ''" % column_name,
                )
        if "source_id" not in columns:
            _add_sqlite_column_if_missing(
                connection,
                "job_postings",
                "source_id",
                "ALTER TABLE job_postings ADD COLUMN source_id VARCHAR(64)",
            )

        indexes = connection.execute(text("PRAGMA index_list('job_postings')")).mappings().all()
        for index in indexes:
            if not index["unique"]:
                continue
            index_name = str(index["name"])
            index_columns = connection.execute(
                text("PRAGMA index_info(%s)" % _quote_sqlite_identifier(index_name))
            ).mappings().all()
            if [column["name"] for column in index_columns] == ["source_link"]:
                connection.execute(
                    text("DROP INDEX %s" % _quote_sqlite_identifier(index_name))
                )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_job_postings_source_link "
                "ON job_postings (source_link)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_job_postings_source_id "
                "ON job_postings (source_id)"
            )
        )


def _ensure_sqlite_schema(bind: Engine) -> None:
    if bind.dialect.name != "sqlite":
        return

    _ensure_job_posting_schema(bind)

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
    if "target_position" not in columns:
        with bind.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE resume_audit_reports "
                    "ADD COLUMN target_position VARCHAR(128) NOT NULL DEFAULT ''"
                )
            )
    if "resume_version_number" not in columns:
        with bind.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE resume_audit_reports "
                    "ADD COLUMN resume_version_number INTEGER"
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
