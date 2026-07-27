import json
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "data" / "processed" / "jobs_clean.jsonl"
DEFAULT_TARGET = PROJECT_ROOT / "data" / "raw_jobs" / "sample_jobs.json"


def load_clean_jobs(source: Path = DEFAULT_SOURCE) -> List[Dict]:
    """Load only approved, normalized jobs for local application seeding."""
    jobs: List[Dict] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        job = json.loads(line)
        if job.get("status") == "approved":
            jobs.append(job)
    return jobs


def write_seed_jobs(source: Path = DEFAULT_SOURCE, target: Path = DEFAULT_TARGET) -> Path:
    """Materialize the approved JSONL dataset as a JSON array for local demos."""
    jobs = load_clean_jobs(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(jobs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def main() -> None:
    target = write_seed_jobs()
    print("Wrote %s" % target)


if __name__ == "__main__":
    main()
