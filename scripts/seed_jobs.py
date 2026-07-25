import json
from pathlib import Path


SAMPLE_JOBS = [
    {
        "title": "Python 后端开发实习生",
        "company": "示例科技有限公司",
        "location": "杭州",
        "publish_time": "2026-07-24",
        "skills": ["Python", "FastAPI", "SQL"],
        "source_link": "https://example.com/jobs/python-intern",
        "updated_at": "2026-07-24",
        "status": "pending",
    }
]


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "data" / "raw_jobs" / "sample_jobs.json"
    target.write_text(json.dumps(SAMPLE_JOBS, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote %s" % target)


if __name__ == "__main__":
    main()

