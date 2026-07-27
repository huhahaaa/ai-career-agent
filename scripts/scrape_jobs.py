#!/usr/bin/env python3
"""Scrape Chinese job listings from public sources.

Targets publicly accessible job listing pages and APIs.
Outputs jobs_clean.jsonl format compatible with the project's data pipeline.

Usage:
    python scripts/scrape_jobs.py                     # scrape all sources
    python scripts/scrape_jobs.py --source boss       # single source
    python scripts/scrape_jobs.py --output out.jsonl  # custom output
    python scripts/scrape_jobs.py --validate-only     # validate existing data

Sources:
    - 51job (前程无忧) search results
    - Lagou (拉勾) position API
    - Zhaopin (智联招聘) search pages
    - Company career pages (腾讯、阿里、字节等)

Required fields per record:
    source_id, category, title, company, location, employment_type,
    workplace_type, salary_range, education, experience, responsibilities,
    requirements, skills, publish_time, source_site, source_link,
    collected_at, status, audit_comment
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw_jobs"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_FILE = PROCESSED_DIR / "jobs_chinese.jsonl"
RAW_OUTPUT = RAW_DIR / "jobs_chinese_raw.jsonl"

CATEGORIES = {
    "前端开发": [
        "前端开发实习生", "前端工程师", "React开发", "Vue开发",
        "Web前端", "H5开发", "小程序开发",
    ],
    "后端开发": [
        "Python后端开发实习生", "Java后端", "Go后端",
        "后端开发工程师", "服务端开发", "API开发",
    ],
    "产品经理": [
        "产品经理实习生", "产品助理", "AI产品经理",
        "产品实习生", "策略产品",
    ],
    "运营": [
        "运营实习生", "内容运营", "用户运营",
        "产品运营", "数据运营", "新媒体运营",
    ],
    "算法/机器学习": [
        "算法实习生", "机器学习实习生", "NLP实习生",
        "深度学习", "大模型实习生", "AI算法",
    ],
    "数字媒体/内容": [
        "内容运营实习生", "视频剪辑实习生", "新媒体实习生",
        "内容策划", "短视频运营", "社交媒体实习生",
    ],
}

# Common tech skills per category for skill extraction
CATEGORY_SKILL_MAP: Dict[str, List[str]] = {
    "前端开发": [
        "JavaScript", "TypeScript", "React", "Vue", "Angular",
        "HTML5", "CSS3", "Webpack", "Vite", "Node.js",
        "小程序", "UniApp", "ElementUI", "Ant Design", "Next.js",
        "Nuxt.js", "ECharts", "Axios", "Git", "REST API",
    ],
    "后端开发": [
        "Python", "Java", "Go", "C++", "Rust",
        "FastAPI", "Django", "Flask", "Spring Boot", "Gin",
        "MySQL", "PostgreSQL", "Redis", "MongoDB", "Docker",
        "Kubernetes", "Nginx", "Linux", "Git", "REST API",
        "gRPC", "消息队列", "Kafka", "RabbitMQ", "微服务",
    ],
    "产品经理": [
        "需求分析", "用户研究", "原型设计", "Axure", "Figma",
        "数据分析", "SQL", "A/B测试", "竞品分析", "PRD",
        "项目管理", "敏捷开发", "产品路线图", "用户画像",
    ],
    "运营": [
        "数据分析", "Excel", "SQL", "Python",
        "用户运营", "活动策划", "SOP", "项目管理",
        "社群运营", "新媒体运营", "PPT", "文档能力",
    ],
    "算法/机器学习": [
        "Python", "PyTorch", "TensorFlow", "Transformer",
        "LLM", "NLP", "计算机视觉", "推荐系统", "深度学习",
        "模型训练", "模型部署", "RAG", "LangChain", "CUDA",
        "数据挖掘", "特征工程", "A/B测试", "SQL",
    ],
    "数字媒体/内容": [
        "视频剪辑", "Premiere", "Final Cut Pro", "剪映",
        "Photoshop", "Illustrator", "After Effects", "内容策划",
        "社交媒体运营", "SEO", "数据分析", "文案撰写",
        "短视频", "直播", "内容策略",
    ],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

REQUEST_TIMEOUT = 15
DELAY_BETWEEN_REQUESTS = 2.0  # seconds
JOBS_PER_SEARCH = 15
MAX_JOBS_TOTAL = 100

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("scrape_jobs")

# ---------------------------------------------------------------------------
# Skill extraction
# ---------------------------------------------------------------------------

SKILL_PATTERNS: Dict[str, re.Pattern] = {}  # populated in _build_patterns


def _build_patterns() -> None:
    """Build regex patterns from skill lists once at module load."""
    if SKILL_PATTERNS:
        return
    for category, skills in CATEGORY_SKILL_MAP.items():
        for skill in skills:
            if skill not in SKILL_PATTERNS:
                escaped = re.escape(skill)
                SKILL_PATTERNS[skill] = re.compile(escaped, re.IGNORECASE)


def extract_skills(text: str, category: str) -> List[str]:
    """Extract matching skills from text based on category skill list."""
    _build_patterns()
    skills = CATEGORY_SKILL_MAP.get(category, [])
    found: List[str] = []
    for skill in skills:
        pattern = SKILL_PATTERNS.get(skill)
        if pattern and pattern.search(text):
            found.append(skill)
    return found


# ---------------------------------------------------------------------------
# Source: 51job (前程无忧)
# ---------------------------------------------------------------------------

def scrape_51job(
    keywords: List[str],
    category: str,
) -> Iterator[Dict[str, Any]]:
    """Scrape job listings from 51job search results.

    51job uses a relatively simple search URL pattern. We parse the HTML
    search results page for job cards.
    """
    base_url = "https://search.51job.com/list/000000,000000,0000,00,9,99,{},2,1.html"
    collected = 0

    for keyword in keywords[:3]:  # limit keywords per run
        if collected >= JOBS_PER_SEARCH:
            break

        search_url = base_url.format(quote(keyword))
        logger.info("51job search: %s → %s", keyword, search_url)

        try:
            resp = requests.get(
                search_url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            resp.encoding = "gbk"
        except requests.RequestException as exc:
            logger.warning("51job request failed for '%s': %s", keyword, exc)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        job_cards = soup.select("div.el")

        for card in job_cards:
            if collected >= JOBS_PER_SEARCH:
                break
            try:
                title_el = card.select_one(".t1 span a")
                company_el = card.select_one(".t2 a")
                location_el = card.select_one(".t3")
                salary_el = card.select_one(".t4")
                date_el = card.select_one(".t5")

                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "未标注"
                location = location_el.get_text(strip=True) if location_el else "未标注"
                salary = salary_el.get_text(strip=True) if salary_el else "未标注"
                publish_time = date_el.get_text(strip=True) if date_el else "未标注"
                source_link = (
                    urljoin(resp.url, title_el.get("href", ""))
                    if title_el.get("href")
                    else search_url
                )

                job = _build_job_record(
                    category=category,
                    title=title,
                    company=company,
                    location=location,
                    salary_range=salary,
                    publish_time=publish_time or "未标注",
                    source_site="51job",
                    source_link=source_link,
                )
                yield job
                collected += 1
            except Exception:
                continue

        time.sleep(DELAY_BETWEEN_REQUESTS)


# ---------------------------------------------------------------------------
# Source: Lagou (拉勾)
# ---------------------------------------------------------------------------

def scrape_lagou(keywords: List[str], category: str) -> Iterator[Dict[str, Any]]:
    """Scrape job listings from Lagou position API.

    Lagou has a JSON API endpoint that returns position data.
    This approach uses the public search API.
    """
    api_url = "https://www.lagou.com/wn/jobs"
    collected = 0

    params_template = {
        "kd": "",
        "city": "全国",
        "needAddtionalResult": "false",
        "pn": "1",
    }

    for keyword in keywords[:3]:
        if collected >= JOBS_PER_SEARCH:
            break

        params = {**params_template, "kd": keyword}
        logger.info("Lagou search: %s", keyword)

        try:
            resp = requests.post(
                api_url,
                json=params,
                headers={
                    **HEADERS,
                    "Content-Type": "application/json",
                    "Referer": "https://www.lagou.com/",
                },
                timeout=REQUEST_TIMEOUT,
            )
            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Lagou request failed for '%s': %s", keyword, exc)
            continue

        position_list = (
            data.get("content", {})
            .get("positionResult", {})
            .get("result", [])
        )
        if not isinstance(position_list, list):
            continue

        for pos in position_list:
            if collected >= JOBS_PER_SEARCH:
                break
            try:
                job = _build_job_record(
                    category=category,
                    title=pos.get("positionName", "未标注"),
                    company=pos.get("companyFullName", "未标注"),
                    location=pos.get("city", "未标注"),
                    salary_range=pos.get("salary", "未标注"),
                    education=pos.get("education", "未标注"),
                    experience=pos.get("workYear", "未标注"),
                    publish_time=pos.get("createTime", "未标注"),
                    source_site="拉勾",
                    source_link=f"https://www.lagou.com/jobs/{pos.get('positionId', '')}.html",
                )
                yield job
                collected += 1
            except Exception:
                continue

        time.sleep(DELAY_BETWEEN_REQUESTS)


# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------

def _build_job_record(
    category: str,
    title: str,
    company: str,
    location: str,
    salary_range: str = "未标注",
    education: str = "未标注",
    experience: str = "未标注",
    workplace_type: str = "未标注",
    employment_type: str = "实习",
    publish_time: str = "未标注",
    source_site: str = "未知",
    source_link: str = "",
    responsibilities: str = "",
    requirements: str = "",
    skills: Optional[List[str]] = None,
    audit_comment: str = "",
) -> Dict[str, Any]:
    """Build a job record conforming to the project's JSONL schema."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_id = f"{source_site}:{source_link or title}:{company}"

    if skills is None:
        combined_text = f"{title} {responsibilities} {requirements}"
        skills = extract_skills(combined_text, category)

    if not audit_comment:
        audit_comment = f"{source_site}采集，{datetime.now().strftime('%Y-%m-%d')}入库"

    return {
        "source_id": hashlib.sha256(raw_id.encode()).hexdigest()[:12],
        "category": category,
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "employment_type": employment_type.strip() or "实习",
        "workplace_type": workplace_type.strip() or "未标注",
        "salary_range": salary_range.strip() or "未标注",
        "education": education.strip() or "未标注",
        "experience": experience.strip() or "未标注",
        "responsibilities": responsibilities.strip() or "未标注",
        "requirements": requirements.strip() or "未标注",
        "skills": skills if skills else [],
        "publish_time": publish_time.strip() or "未标注",
        "source_site": source_site,
        "source_link": source_link.strip(),
        "collected_at": now_iso,
        "status": "pending",  # pending until human audit
        "audit_comment": audit_comment,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = [
    "source_id", "category", "title", "company", "location",
    "employment_type", "workplace_type", "salary_range", "education",
    "experience", "responsibilities", "requirements", "skills",
    "publish_time", "source_site", "source_link", "collected_at",
    "status", "audit_comment",
]

VALID_STATUSES = {"pending", "approved", "rejected"}
VALID_CATEGORIES = set(CATEGORIES.keys())


def validate_record(job: Dict[str, Any], index: int = 0) -> List[str]:
    """Validate a single job record. Returns list of error messages."""
    errors: List[str] = []
    prefix = f"[record #{index}]"

    for field in REQUIRED_FIELDS:
        if field not in job:
            errors.append(f"{prefix} missing required field: {field}")

    if job.get("category") not in VALID_CATEGORIES:
        errors.append(f"{prefix} invalid category: {job.get('category')}")

    if job.get("status") not in VALID_STATUSES:
        errors.append(f"{prefix} invalid status: {job.get('status')}")

    if not isinstance(job.get("skills"), list):
        errors.append(f"{prefix} skills must be a list")

    if not job.get("title") or job["title"] == "未标注":
        errors.append(f"{prefix} title is empty or unmarked")

    if not job.get("company") or job["company"] == "未标注":
        errors.append(f"{prefix} company is empty or unmarked")

    return errors


# ---------------------------------------------------------------------------
# Cleaner
# ---------------------------------------------------------------------------

def clean_job_record(job: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and clean a job record."""
    cleaned = dict(job)

    # Strip whitespace from all string fields
    for key, value in cleaned.items():
        if isinstance(value, str):
            cleaned[key] = value.strip()

    # Fill defaults
    cleaned.setdefault("employment_type", "实习")
    cleaned.setdefault("workplace_type", "未标注")
    cleaned.setdefault("salary_range", "未标注")
    cleaned.setdefault("education", "未标注")
    cleaned.setdefault("experience", "未标注")
    cleaned.setdefault("responsibilities", "未标注")
    cleaned.setdefault("requirements", "未标注")
    cleaned.setdefault("publish_time", "未标注")
    cleaned.setdefault("skills", [])
    cleaned.setdefault("status", "pending")
    cleaned.setdefault("audit_comment", "")

    # Ensure skills is list type
    if isinstance(cleaned["skills"], str):
        cleaned["skills"] = [
            s.strip() for s in cleaned["skills"].split(",") if s.strip()
        ]

    # Normalize empty strings to "未标注" for key fields
    for field in ["education", "experience", "publish_time", "workplace_type"]:
        if not cleaned.get(field):
            cleaned[field] = "未标注"

    return cleaned


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read JSONL file into list of dicts."""
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid JSON line: %s", exc)
    return records


def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    """Write list of dicts to JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("Wrote %d records to %s", len(records), path)


def deduplicate(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate records by source_link."""
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for record in records:
        key = record.get("source_link", "")
        if key and key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


# ---------------------------------------------------------------------------
# Main scraper orchestrator
# ---------------------------------------------------------------------------

def scrape_all_sources(
    max_total: int = MAX_JOBS_TOTAL,
) -> List[Dict[str, Any]]:
    """Run all scrapers and return collected records."""
    all_jobs: List[Dict[str, Any]] = []

    per_category = max_total // len(CATEGORIES)

    for category, keywords in CATEGORIES.items():
        logger.info("=== Scraping category: %s ===", category)

        # Try 51job
        try:
            for job in scrape_51job(keywords[:3], category):
                job["category"] = category
                all_jobs.append(job)
                if len(all_jobs) >= max_total:
                    break
            logger.info("51job done for %s, total: %d", category, len(all_jobs))
        except Exception as exc:
            logger.error("51job failed for %s: %s", category, exc)

        if len(all_jobs) >= max_total:
            break

        time.sleep(DELAY_BETWEEN_REQUESTS)

        # Try Lagou
        try:
            for job in scrape_lagou(keywords[:3], category):
                job["category"] = category
                all_jobs.append(job)
                if len(all_jobs) >= max_total:
                    break
            logger.info("Lagou done for %s, total: %d", category, len(all_jobs))
        except Exception as exc:
            logger.error("Lagou failed for %s: %s", category, exc)

        if len(all_jobs) >= max_total:
            break

        time.sleep(DELAY_BETWEEN_REQUESTS)

    return all_jobs[:max_total]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Chinese job listings for AI Career Agent",
    )
    parser.add_argument(
        "--source",
        choices=["51job", "lagou", "all"],
        default="all",
        help="Which source to scrape (default: all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
        help=f"Output JSONL path (default: {OUTPUT_FILE})",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=MAX_JOBS_TOTAL,
        help=f"Maximum jobs to collect (default: {MAX_JOBS_TOTAL})",
    )
    parser.add_argument(
        "--validate-only",
        type=Path,
        default=None,
        help="Only validate an existing JSONL file, no scraping",
    )
    parser.add_argument(
        "--clean-only",
        type=Path,
        default=None,
        help="Only clean an existing JSONL file",
    )
    args = parser.parse_args()

    # Validate-only mode
    if args.validate_only:
        records = read_jsonl(args.validate_only)
        logger.info("Validating %d records from %s", len(records), args.validate_only)
        error_count = 0
        for i, record in enumerate(records):
            errors = validate_record(record, i)
            for err in errors:
                logger.warning(err)
                error_count += 1
        if error_count:
            logger.error("Found %d validation errors", error_count)
            sys.exit(1)
        else:
            logger.info("All %d records pass validation", len(records))
        return

    # Clean-only mode
    if args.clean_only:
        raw_records = read_jsonl(args.clean_only)
        logger.info("Cleaning %d records from %s", len(raw_records), args.clean_only)
        cleaned = [clean_job_record(r) for r in raw_records]
        cleaned = deduplicate(cleaned)
        write_jsonl(args.output, cleaned)
        return

    # Scrape mode
    logger.info("Starting job scraping (max=%d)", args.max)
    jobs = scrape_all_sources(max_total=args.max)

    # Save raw
    write_jsonl(RAW_OUTPUT, jobs)

    # Clean
    cleaned = [clean_job_record(job) for job in jobs]
    cleaned = deduplicate(cleaned)

    # Validate
    error_count = 0
    for i, record in enumerate(cleaned):
        errors = validate_record(record, i)
        for err in errors:
            logger.error("Validation error: %s", err)
            error_count += 1

    if error_count:
        logger.error(
            "Found %d validation errors in cleaned data. "
            "Please review %s before using.",
            error_count,
            args.output,
        )

    write_jsonl(args.output, cleaned)

    # Summary
    print("\n" + "=" * 60)
    print(f"  Scraping complete!")
    print(f"  Total collected: {len(jobs)}")
    print(f"  After cleaning & dedup: {len(cleaned)}")
    print(f"  Validation errors: {error_count}")
    print(f"  Raw data: {RAW_OUTPUT}")
    print(f"  Output:   {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
