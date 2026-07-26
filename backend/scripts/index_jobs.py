import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.vector_store import upsert_job_embedding  # noqa: E402


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


def transform_job(job: Dict) -> Dict:
    return {
        **job,
        "id": job.get("source_id", job.get("id")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index approved jobs from a JSONL file into Chroma.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=PROJECT_DIR / "data" / "processed" / "jobs_clean.jsonl",
    )
    args = parser.parse_args()
    path = args.path.expanduser().resolve()

    if not path.is_file():
        raise SystemExit("job data file not found: %s" % path)

    jobs = list(read_jsonl(path))
    total = len(jobs)
    print(f"📥 准备导入 {total} 条岗位数据")
    print("-" * 60)

    success_count = 0
    fail_count = 0
    failed_jobs = []

    for idx, job in enumerate(jobs, start=1):
        try:
            transformed = transform_job(job)
            result = upsert_job_embedding(transformed)
            success_count += 1
            print(f"[{idx}/{total}] ✅ {job.get('title', '未知岗位')}")
        except Exception as e:
            fail_count += 1
            failed_jobs.append({"id": job.get("source_id"), "title": job.get("title"), "error": str(e)})
            print(f"[{idx}/{total}] ❌ {job.get('title', '未知岗位')} - {e}")

    print("-" * 60)
    print(f"\n📊 导入完成!")
    print(f"   成功: {success_count}")
    print(f"   失败: {fail_count}")

    if failed_jobs:
        print("\n❌ 失败列表:")
        for item in failed_jobs:
            print(f"   - {item['id']}: {item['title']} - {item['error']}")


if __name__ == "__main__":
    main()
