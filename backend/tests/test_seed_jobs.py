import json
import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
JOBS_PATH = PROJECT_ROOT / "data" / "processed" / "jobs_clean.jsonl"
SEED_JOBS_PATH = PROJECT_ROOT / "scripts" / "seed_jobs.py"

spec = importlib.util.spec_from_file_location("seed_jobs", SEED_JOBS_PATH)
assert spec and spec.loader
seed_jobs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed_jobs)
load_clean_jobs = seed_jobs.load_clean_jobs
write_seed_jobs = seed_jobs.write_seed_jobs


def test_load_clean_jobs_returns_approved_api_payloads():
    jobs = load_clean_jobs(JOBS_PATH)

    assert len(jobs) == 24
    assert all(job["status"] == "approved" for job in jobs)
    assert all(job["title"] and job["company"] for job in jobs)
    assert all(job["skills"] and job["source_link"] for job in jobs)


def test_write_seed_jobs_creates_json_array(tmp_path):
    target = tmp_path / "sample_jobs.json"

    written = write_seed_jobs(JOBS_PATH, target)

    assert written == target
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload) == 24
    assert payload[0]["source_link"].startswith("https://")
