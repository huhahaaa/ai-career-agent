from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy.orm import Session

from app.models.agent_log import AgentLog

MAX_SUMMARY_CHARS = 500


def _summarize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:MAX_SUMMARY_CHARS]
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    return text[:MAX_SUMMARY_CHARS]


def add_agent_log(
    db: Session,
    *,
    user_id: int | None,
    operation: str,
    status: str,
    duration_ms: int | None = None,
    request_summary: Any = "",
    response_summary: Any = "",
    error_message: str = "",
) -> None:
    db.add(
        AgentLog(
            user_id=user_id,
            operation=operation,
            status=status,
            duration_ms=duration_ms,
            request_summary=_summarize(request_summary),
            response_summary=_summarize(response_summary),
            error_message=error_message[:MAX_SUMMARY_CHARS],
        )
    )


@contextmanager
def agent_operation_log(
    db: Session,
    *,
    user_id: int | None,
    operation: str,
    request_summary: Any = "",
) -> Iterator[dict[str, Any]]:
    started_at = time.perf_counter()
    context: dict[str, Any] = {"response_summary": ""}
    try:
        yield context
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000)
        add_agent_log(
            db,
            user_id=user_id,
            operation=operation,
            status="failed",
            duration_ms=duration_ms,
            request_summary=request_summary,
            error_message=str(exc),
        )
        raise
    else:
        duration_ms = round((time.perf_counter() - started_at) * 1000)
        add_agent_log(
            db,
            user_id=user_id,
            operation=operation,
            status="success",
            duration_ms=duration_ms,
            request_summary=request_summary,
            response_summary=context.get("response_summary", ""),
        )
