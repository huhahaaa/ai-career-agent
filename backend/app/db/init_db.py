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


def init_db(bind: Engine = engine) -> None:
    Base.metadata.create_all(bind=bind)
    _ensure_sqlite_schema(bind)
