import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data" / "audit_samples"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_day2_material_counts_and_role_coverage():
    resumes = read_jsonl(AUDIT / "resume_samples.jsonl")
    jobs = read_jsonl(AUDIT / "job_jd_samples.jsonl")
    questions = read_jsonl(AUDIT / "interview_questions.jsonl")
    profiles = json.loads((ROOT / "data" / "processed" / "role_profiles.json").read_text(encoding="utf-8"))

    assert len(resumes) == 10
    assert len(jobs) == 10
    assert len(questions) == 30
    assert len(profiles) >= 5
    assert len({item["role"] for item in profiles}) >= 5
    assert len({item["role"] for item in questions}) >= 5


def test_resume_samples_are_deidentified_and_have_evidence():
    resumes = read_jsonl(AUDIT / "resume_samples.jsonl")

    for resume in resumes:
        assert resume["sensitive_data_removed"] is True
        assert resume["source"] == "synthetic_test_data"
        assert resume["education"]
        assert resume["skills"]
        assert resume["projects"] or resume["experience"]
        assert "phone" not in json.dumps(resume, ensure_ascii=False).lower()
        assert "email" not in json.dumps(resume, ensure_ascii=False).lower()


def test_job_jd_samples_have_traceable_source_fields():
    jobs = read_jsonl(AUDIT / "job_jd_samples.jsonl")
    required = {"source_site", "source_link", "source_checked_at", "title", "company", "location", "skills"}

    for job in jobs:
        assert required <= job.keys()
        assert all(job[field] for field in required)
        assert job["source_link"].startswith("https://")
        assert len(job["skills"]) >= 3


def test_question_bank_and_failure_cases_are_actionable():
    questions = read_jsonl(AUDIT / "interview_questions.jsonl")
    failures = json.loads((AUDIT / "day2_failure_cases.json").read_text(encoding="utf-8"))

    assert all(item["expected_points"] and item["follow_up"] for item in questions)
    assert {item["category"] for item in questions} >= {"技术基础", "项目深挖", "场景题"}
    assert {item["scenario"] for item in failures} >= {
        "resume_too_short",
        "job_without_source",
        "empty_match_result",
        "answer_too_short_follow_up",
    }
