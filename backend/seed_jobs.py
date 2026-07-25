"""Batch import jobs from data/processed/jobs_clean.jsonl into the database."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.session import SessionLocal, engine, Base
import app.models  # noqa: F401 - register all models
from app.models.job import JobPosting
from sqlalchemy import select

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "processed" / "jobs_clean.jsonl"


def import_jobs() -> None:
    if not DATA_FILE.exists():
        print(f"[ERROR] Data file not found: {DATA_FILE}")
        sys.exit(1)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Check existing
        existing_links = {
            row[0]
            for row in db.execute(select(JobPosting.source_link)).all()
        }

        imported = 0
        skipped = 0

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[WARN] Line {line_num}: invalid JSON, skipping")
                    continue

                source_link = data.get("source_link", "")
                if not source_link:
                    print(f"[WARN] Line {line_num}: no source_link, skipping")
                    continue

                if source_link in existing_links:
                    print(f"[SKIP] Already exists: {data.get('title', '?')} @ {data.get('company', '?')}")
                    skipped += 1
                    continue

                skills = data.get("skills", [])
                if isinstance(skills, str):
                    skills = json.loads(skills)
                skills_str = json.dumps(skills, ensure_ascii=False)

                job = JobPosting(
                    title=data.get("title", "")[:128],
                    company=data.get("company", "")[:128],
                    location=data.get("location", "Unknown")[:128],
                    salary_range=data.get("salary_range", "")[:64],
                    education=data.get("education", "")[:64],
                    experience=data.get("experience", "")[:64],
                    responsibilities=data.get("responsibilities", ""),
                    requirements=data.get("requirements", ""),
                    publish_time=data.get("publish_time", "Unknown")[:64],
                    skills=skills_str,
                    source_site=data.get("source_site", "")[:128],
                    source_link=source_link[:512],
                    status="approved",
                    audit_comment=data.get("audit_comment", ""),
                    collected_at=datetime.now(timezone.utc),
                )
                db.add(job)
                db.flush()
                existing_links.add(source_link)

                cat = data.get("category", "?")
                print(f"[OK] #{line_num:02d} [{cat}] {job.title[:40]} @ {job.company}")
                imported += 1

        db.commit()
        print(f"\nDone: {imported} imported, {skipped} skipped, {imported + skipped} total")

    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import_jobs()
