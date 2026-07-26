import json
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.api.v1.endpoints.jobs import job_to_vector_payload
from app.core.exceptions import AppException
from app.db.session import get_db
from app.models.job import JobPosting
from app.models.matching import MatchingRecord
from app.models.resume import RESUME_SOURCE_MATCHING_SNAPSHOT, Resume
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.matching import (
    BatchIndexResult,
    JobIndexResult,
    MatchRequest,
    MatchResponse,
)
from app.services.matching import (
    enrich_match_results,
    index_approved_job,
    index_approved_jobs,
    match_resume_to_jobs,
)
from app.services.vector_store import VectorStoreUnavailable
from app.services.vector_store import clear_job_embeddings
from app.services.resume_selection import (
    create_resume_snapshot,
    get_user_formal_resume,
    resume_current_text,
)

router = APIRouter()

SKILL_GAP_DETAIL_KEYS = (
    "matched_skills",
    "missing_skills",
    "gap_analysis",
    "suggestion",
    "semantic_score",
    "skill_coverage_score",
    "ability_breakdown",
)


def _vector_service_error(exc: Exception) -> AppException:
    return AppException(
        status_code=503,
        code=50301,
        message=str(exc),
    )


def _coerce_database_job_id(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_json_list(value: str) -> List[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _matching_resume_text(record: MatchingRecord) -> str:
    if not record.resume or not record.resume.versions:
        return ""

    current_version = next(
        (
            version
            for version in record.resume.versions
            if version.version_number == record.resume.current_version_number
        ),
        None,
    )
    version = current_version or record.resume.versions[-1]
    return version.content or ""


def _resolve_matching_resume(
    db: Session,
    user: User,
    payload: MatchRequest,
) -> tuple[str, Resume | None]:
    if payload.resume_id is not None:
        resume = get_user_formal_resume(db, user, payload.resume_id)
        resume_text = resume_current_text(resume).strip()
        if len(resume_text) < 10:
            raise AppException(422, 42205, "selected resume has no usable text")
        return resume_text, resume

    resume_text = (payload.resume_text or "").strip()
    if not resume_text:
        raise AppException(422, 42206, "resume_text or resume_id is required")
    return resume_text, None


def _matching_record_details(record: MatchingRecord) -> dict:
    try:
        details = json.loads(record.details or "{}")
    except json.JSONDecodeError:
        details = {}
    if all(key in details for key in SKILL_GAP_DETAIL_KEYS):
        return details
    if record.job is None:
        return details

    resume_text = _matching_resume_text(record)
    if not resume_text:
        return details

    enriched = enrich_match_results(
        resume_text,
        [
            {
                "job_id": str(record.job_id),
                "title": record.job.title,
                "company": record.job.company,
                "score": details.get("score", record.total_score),
                "reason": details.get("reason", ""),
                "source_id": details.get("source_id", record.job.source_id or ""),
                "source_link": details.get("source_link", record.job.source_link),
                "skills": _load_json_list(record.job.skills),
            }
        ],
        str(details.get("target_position", "")),
    )[0]
    for key in SKILL_GAP_DETAIL_KEYS:
        details[key] = enriched.get(key, [] if key.endswith("_skills") else "")
    details["score"] = enriched.get("score", details.get("score", record.total_score))
    details["reason"] = enriched.get("reason", details.get("reason", ""))
    return details


def _save_matching_records(
    db: Session,
    user: User,
    payload: MatchRequest,
    matches: List[dict],
    resume_text: str,
    selected_resume: Resume | None = None,
) -> None:
    persisted_matches = []
    for match in matches:
        job_id = _coerce_database_job_id(match.get("job_id", ""))
        if job_id is None:
            continue
        job = db.get(JobPosting, job_id)
        if job is None:
            continue
        persisted_matches.append((job, match))

    if not persisted_matches:
        return

    resume = selected_resume or create_resume_snapshot(
        db,
        user,
        title="岗位匹配简历快照",
        file_name="matching-input.txt",
        content=resume_text,
        source_type=RESUME_SOURCE_MATCHING_SNAPSHOT,
    )
    for job, match in persisted_matches:
        db.add(
            MatchingRecord(
                user_id=user.id,
                resume_id=resume.id,
                job_id=job.id,
                total_score=round(float(match.get("score", 0))),
                details=json.dumps(
                    {
                        "target_position": payload.target_position,
                        "score": match.get("score", 0),
                        "semantic_score": match.get("semantic_score"),
                        "skill_coverage_score": match.get("skill_coverage_score"),
                        "ability_breakdown": match.get("ability_breakdown", {}),
                        "reason": match.get("reason", ""),
                        "source_id": match.get("source_id", ""),
                        "source_link": match.get("source_link", ""),
                        "matched_skills": match.get("matched_skills", []),
                        "missing_skills": match.get("missing_skills", []),
                        "gap_analysis": match.get("gap_analysis", ""),
                        "suggestion": match.get("suggestion", ""),
                    },
                    ensure_ascii=False,
                ),
            )
        )
    db.commit()


@router.post("/run", response_model=ApiResponse[MatchResponse])
def run_matching(
    payload: MatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[MatchResponse]:
    resume_text, selected_resume = _resolve_matching_resume(db, current_user, payload)
    try:
        matches = match_resume_to_jobs(
            resume_text,
            payload.target_position,
            payload.top_k,
        )
    except VectorStoreUnavailable as exc:
        raise _vector_service_error(exc) from exc
    _save_matching_records(
        db,
        current_user,
        payload,
        matches,
        resume_text,
        selected_resume,
    )
    return success_response(MatchResponse(matches=matches))


@router.get("/history", response_model=ApiResponse[List[dict]])
def matching_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[List[dict]]:
    records = db.scalars(
        select(MatchingRecord)
        .where(MatchingRecord.user_id == current_user.id)
        .order_by(MatchingRecord.created_at.desc(), MatchingRecord.id.desc())
    ).all()
    payload = []
    for record in records:
        details = _matching_record_details(record)
        score = details.get("score", record.total_score)
        payload.append(
            {
                "id": record.id,
                "resume_id": record.resume_id,
                "job_id": record.job_id,
                "job_title": record.job.title if record.job else "",
                "company": record.job.company if record.job else "",
                "total_score": round(float(score or 0)),
                "details": details,
                "created_at": record.created_at,
            }
        )
    return success_response(payload)


@router.post(
    "/index/jobs/{job_id}",
    response_model=ApiResponse[JobIndexResult],
)
def index_job(
    job_id: int,
    _reviewer: User = Depends(require_roles("reviewer")),
    db: Session = Depends(get_db),
) -> ApiResponse[JobIndexResult]:
    job = db.get(JobPosting, job_id)
    if job is None:
        raise AppException(404, 40401, "job not found")
    if job.status != "approved":
        raise AppException(409, 40903, "only approved jobs can be indexed")
    try:
        result = index_approved_job(job_to_vector_payload(job))
    except VectorStoreUnavailable as exc:
        raise _vector_service_error(exc) from exc
    return success_response(JobIndexResult.model_validate(result))


@router.post(
    "/index/approved",
    response_model=ApiResponse[BatchIndexResult],
)
def index_all_approved_jobs(
    _reviewer: User = Depends(require_roles("reviewer")),
    db: Session = Depends(get_db),
) -> ApiResponse[BatchIndexResult]:
    jobs = db.scalars(
        select(JobPosting)
        .where(JobPosting.status == "approved")
        .order_by(JobPosting.id)
    ).all()
    try:
        clear_result = clear_job_embeddings()
        result = index_approved_jobs(job_to_vector_payload(job) for job in jobs)
        result["deleted_count"] = clear_result["deleted_count"]
    except VectorStoreUnavailable as exc:
        raise _vector_service_error(exc) from exc
    return success_response(BatchIndexResult.model_validate(result))


@router.get("/skill-taxonomy", response_model=ApiResponse[List[str]])
def skill_taxonomy(
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[List[str]]:
    return success_response(
        [
            "Python",
            "FastAPI",
            "React",
            "SQL",
            "LLM",
            "RAG",
            "数据清洗",
            "岗位审核",
        ]
    )
