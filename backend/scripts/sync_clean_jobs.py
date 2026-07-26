import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.init_db import init_db  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.job import JobPosting  # noqa: E402
from app.services.job_cleaner import normalize_job  # noqa: E402
from app.services.matching import index_approved_jobs  # noqa: E402
from app.services.vector_store import clear_job_embeddings  # noqa: E402


VALID_STATUSES = {"pending", "approved", "rejected"}


def read_jsonl(path: Path) -> Iterable[Dict]:
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "invalid JSON at %s:%s" % (path, line_number)
                ) from exc


def _encode_skills(skills: List[str]) -> str:
    return json.dumps(skills, ensure_ascii=False)


def _decode_skills(value: str) -> List[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(skill) for skill in loaded]


def _coerce_status(raw_job: Dict, fallback: str = "pending") -> str:
    status = str(raw_job.get("status") or fallback).strip()
    if status not in VALID_STATUSES:
        return fallback
    return status


def _job_values(raw_job: Dict) -> Dict:
    normalized = normalize_job(raw_job)
    return {
        "source_id": normalized["source_id"],
        "category": normalized["category"],
        "title": normalized["title"],
        "company": normalized["company"],
        "location": normalized["location"],
        "employment_type": normalized["employment_type"],
        "workplace_type": normalized["workplace_type"],
        "salary_range": normalized["salary_range"],
        "education": normalized["education"],
        "experience": normalized["experience"],
        "responsibilities": normalized["responsibilities"],
        "requirements": normalized["requirements"],
        "publish_time": normalized["publish_time"],
        "skills": _encode_skills(normalized["skills"]),
        "source_site": normalized["source_site"],
        "source_link": normalized["source_link"],
    }


def sync_clean_jobs(
    db: Session,
    jobs: Iterable[Dict],
    sync_status: bool = True,
) -> Dict:
    stats = {
        "inserted_count": 0,
        "updated_count": 0,
        "skipped_count": 0,
    }
    for raw_job in jobs:
        values = _job_values(raw_job)
        if not values["source_link"] or not values["title"]:
            stats["skipped_count"] += 1
            continue

        if values["source_id"]:
            existing = db.scalar(
                select(JobPosting).where(JobPosting.source_id == values["source_id"])
            )
            if existing is None:
                existing = db.scalar(
                    select(JobPosting).where(
                        JobPosting.source_link == values["source_link"],
                        JobPosting.source_id.is_(None),
                    )
                )
        else:
            existing = db.scalar(
                select(JobPosting).where(JobPosting.source_link == values["source_link"])
            )
        audit_comment = str(raw_job.get("audit_comment") or "").strip()
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            if sync_status:
                existing.status = _coerce_status(raw_job, existing.status)
            if audit_comment:
                existing.audit_comment = audit_comment
            stats["updated_count"] += 1
            continue

        db.add(
            JobPosting(
                **values,
                status=_coerce_status(raw_job) if sync_status else "pending",
                audit_comment=audit_comment,
            )
        )
        stats["inserted_count"] += 1

    db.commit()
    return stats


def _job_to_vector_payload(job: JobPosting) -> Dict:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "category": job.category,
        "employment_type": job.employment_type,
        "workplace_type": job.workplace_type,
        "responsibilities": job.responsibilities,
        "requirements": job.requirements,
        "skills": _decode_skills(job.skills),
        "source_id": job.source_id,
        "source_link": job.source_link,
        "status": job.status,
    }


def rebuild_approved_job_index(db: Session) -> Dict:
    jobs = db.scalars(
        select(JobPosting)
        .where(JobPosting.status == "approved")
        .order_by(JobPosting.id)
    ).all()
    clear_result = clear_job_embeddings()
    index_result = index_approved_jobs(_job_to_vector_payload(job) for job in jobs)
    return {
        "deleted_count": clear_result["deleted_count"],
        **index_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync cleaned job data into SQL and optionally rebuild Chroma.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=PROJECT_DIR / "data" / "processed" / "jobs_clean.jsonl",
    )
    parser.add_argument(
        "--preserve-status",
        action="store_true",
        help="keep existing database audit statuses instead of syncing JSONL status",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="clear and rebuild the approved job vector index from database rows",
    )
    args = parser.parse_args()

    path = args.path.expanduser().resolve()
    if not path.is_file():
        raise SystemExit("job data file not found: %s" % path)

    init_db()
    with SessionLocal() as db:
        result = sync_clean_jobs(
            db,
            read_jsonl(path),
            sync_status=not args.preserve_status,
        )
        if args.rebuild_index:
            result["index"] = rebuild_approved_job_index(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
