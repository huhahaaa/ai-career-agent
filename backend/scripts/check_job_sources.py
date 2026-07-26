from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_SOURCES_PATH = PROJECT_DIR / "data" / "raw_jobs" / "job_sources.csv"
CHINESE_JOBS_PATH = PROJECT_DIR / "data" / "processed" / "jobs_chinese.jsonl"
REPORT_PATH = PROJECT_DIR / "backend" / "outputs" / "source_check_report.md"


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _read_sources(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as source:
        return {
            row.get("source_link", ""): row
            for row in csv.DictReader(source)
            if row.get("source_link")
        }


def _probe_url(url: str, timeout: int = 5) -> tuple[str, str]:
    if not url:
        return "来源缺失", "无链接"
    try:
        request = Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 0)
        if 200 <= status_code < 400:
            return "可用", f"HTTP {status_code}"
        return "待检查", f"HTTP {status_code}"
    except URLError as exc:
        return "待检查", str(exc.reason)[:80]
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        return "待检查", str(exc)[:80]


def build_report(probe: bool = False, limit: int | None = None) -> list[dict]:
    source_rows = _read_sources(RAW_SOURCES_PATH)
    jobs = _read_jsonl(CHINESE_JOBS_PATH)
    if limit:
        jobs = jobs[:limit]

    results = []
    for job in jobs:
        source_link = str(job.get("source_link") or "")
        source_record = source_rows.get(source_link, {})
        if probe:
            status, detail = _probe_url(source_link)
        elif source_record:
            accessible = str(source_record.get("page_accessible", "")).lower() == "true"
            status = "可用" if accessible else "待检查"
            detail = source_record.get("note") or source_record.get("source_update_note") or "来自 job_sources.csv"
        else:
            status = "来源缺失" if not source_link else "待检查"
            detail = "未在 job_sources.csv 中找到记录"

        results.append(
            {
                "source_id": job.get("source_id", ""),
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "source_link": source_link,
                "status": status,
                "detail": detail,
            }
        )
    return results


def write_markdown(results: list[dict], path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stats: dict[str, int] = {}
    for item in results:
        stats[item["status"]] = stats.get(item["status"], 0) + 1

    lines = [
        "# 岗位来源检查报告",
        "",
        "## 汇总",
        "",
        "| 状态 | 数量 |",
        "| --- | ---: |",
    ]
    for status, count in sorted(stats.items()):
        lines.append(f"| {status} | {count} |")
    lines.extend([
        "",
        "## 明细",
        "",
        "| source_id | 公司 | 岗位 | 状态 | 说明 |",
        "| --- | --- | --- | --- | --- |",
    ])
    for item in results:
        lines.append(
            "| {source_id} | {company} | {title} | {status} | {detail} |".format(
                **{key: str(value).replace("|", "/") for key, value in item.items()}
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check job source traceability.")
    parser.add_argument("--probe", action="store_true", help="Probe source links over network.")
    parser.add_argument("--limit", type=int, default=None, help="Limit checked jobs.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown path.")
    args = parser.parse_args()

    results = build_report(probe=args.probe, limit=args.limit)
    write_markdown(results)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"checked={len(results)} report={REPORT_PATH}")


if __name__ == "__main__":
    main()
