from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "data"

ROLE_PROFILES_PATH = DATA_ROOT / "processed" / "role_profiles.json"
CLEAN_JOBS_PATH = DATA_ROOT / "processed" / "jobs_clean.jsonl"
CHINESE_JOBS_PATH = DATA_ROOT / "processed" / "jobs_chinese.jsonl"
JD_SAMPLES_PATH = DATA_ROOT / "audit_samples" / "job_jd_samples.jsonl"
RESUME_SAMPLES_PATH = DATA_ROOT / "audit_samples" / "resume_samples.jsonl"
DATA_TEST_CASES_PATH = DATA_ROOT / "audit_samples" / "test_cases.json"
FAILURE_CASES_PATH = DATA_ROOT / "audit_samples" / "day2_failure_cases.json"
JOB_SOURCES_PATH = DATA_ROOT / "raw_jobs" / "job_sources.csv"

ROLE_ALIASES = {
    "前端开发": ["前端", "frontend", "react", "vue", "web"],
    "后端开发": ["后端", "backend", "服务端", "python", "fastapi", "java", "go"],
    "产品经理": ["产品", "product", "pm", "需求"],
    "运营": ["运营", "operation", "growth", "用户运营"],
    "算法/机器学习": ["算法", "机器学习", "machine learning", "深度学习", "模型训练", "nlp算法"],
    "数字媒体/内容": ["数媒", "数字媒体", "内容", "新媒体", "视频", "设计"],
}

AI_APPLICATION_ALIASES = ["ai应用", "ai 应用", "大模型应用", "llm应用", "llm 应用", "rag", "langchain", "智能体开发", "agent开发"]
ENGINEERING_ALIASES = ["开发", "工程师", "研发", "程序", "技术"]


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _read_csv(path: Path) -> List[Dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as source:
            return [dict(row) for row in csv.DictReader(source)]
    except OSError:
        return []


@lru_cache(maxsize=1)
def load_role_profiles() -> List[Dict[str, Any]]:
    data = _read_json(ROLE_PROFILES_PATH, [])
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def load_jd_samples() -> List[Dict[str, Any]]:
    return _read_jsonl(JD_SAMPLES_PATH)


@lru_cache(maxsize=1)
def load_clean_jobs() -> List[Dict[str, Any]]:
    return _read_jsonl(CLEAN_JOBS_PATH)


@lru_cache(maxsize=1)
def load_chinese_jobs() -> List[Dict[str, Any]]:
    return _read_jsonl(CHINESE_JOBS_PATH)


@lru_cache(maxsize=1)
def load_resume_samples() -> List[Dict[str, Any]]:
    return _read_jsonl(RESUME_SAMPLES_PATH)


@lru_cache(maxsize=1)
def load_data_quality_cases() -> List[Dict[str, Any]]:
    data = _read_json(DATA_TEST_CASES_PATH, [])
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def load_failure_cases() -> List[Dict[str, Any]]:
    data = _read_json(FAILURE_CASES_PATH, [])
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def load_job_sources() -> List[Dict[str, str]]:
    return _read_csv(JOB_SOURCES_PATH)


def normalize_role_name(text: str) -> str:
    lowered = (text or "").lower()
    if not lowered:
        return ""
    if (
        any(alias.lower() in lowered for alias in AI_APPLICATION_ALIASES)
        and any(alias in lowered for alias in ENGINEERING_ALIASES)
    ):
        return "后端开发"
    for role, aliases in ROLE_ALIASES.items():
        if role.lower() in lowered or any(alias.lower() in lowered for alias in aliases):
            return role
    for profile in load_role_profiles():
        role = str(profile.get("role") or "")
        aliases = [str(alias) for alias in profile.get("aliases", []) or []]
        if role and (role.lower() in lowered or any(alias.lower() in lowered for alias in aliases)):
            return role
    return ""


def get_role_profile(text: str) -> Optional[Dict[str, Any]]:
    role = normalize_role_name(text)
    if not role:
        return None
    for profile in load_role_profiles():
        if profile.get("role") == role:
            return profile
    return None


def _split_requirement(value: str) -> List[str]:
    value = str(value or "").strip()
    if not value:
        return []
    parts = re.split(r"\s*(?:/|或|、|,|，)\s*", value)
    return [part.strip() for part in parts if part.strip()]


def _contains_requirement(text: str, requirement: str) -> bool:
    lowered = (text or "").lower()
    options = _split_requirement(requirement) or [requirement]
    return any(option.lower() in lowered for option in options)


def role_profile_gap(text: str, target_position: str) -> Dict[str, Any]:
    profile = get_role_profile(target_position)
    if profile is None:
        return {}

    must_have = [str(item) for item in profile.get("must_have", []) or []]
    preferred = [str(item) for item in profile.get("preferred", []) or []]
    matched_must = [item for item in must_have if _contains_requirement(text, item)]
    missing_must = [item for item in must_have if item not in matched_must]
    matched_preferred = [item for item in preferred if _contains_requirement(text, item)]
    missing_preferred = [item for item in preferred if item not in matched_preferred]
    return {
        "role": profile.get("role", ""),
        "profile_id": profile.get("profile_id", ""),
        "profile_version": profile.get("profile_version", ""),
        "data_source": profile.get("data_source", ""),
        "must_have": must_have,
        "preferred": preferred,
        "matched_must_have": matched_must,
        "missing_must_have": missing_must,
        "matched_preferred": matched_preferred,
        "missing_preferred": missing_preferred,
        "evidence_signals": profile.get("evidence_signals", []) or [],
        "linked_jd_ids": profile.get("linked_jd_ids", []) or [],
    }


def role_profile_context(target_position: str) -> str:
    profile = get_role_profile(target_position)
    if profile is None:
        return ""
    return (
        "【岗位能力画像】\n"
        "角色：{role}\n"
        "必备能力：{must_have}\n"
        "加分能力：{preferred}\n"
        "证据信号：{signals}\n"
        "来源：{source}，版本：{version}，关联JD：{jd_ids}"
    ).format(
        role=profile.get("role", ""),
        must_have="、".join(profile.get("must_have", []) or []),
        preferred="、".join(profile.get("preferred", []) or []),
        signals="、".join(profile.get("evidence_signals", []) or []),
        source=profile.get("data_source", ""),
        version=profile.get("profile_version", ""),
        jd_ids="、".join(profile.get("linked_jd_ids", []) or []),
    )


def get_failure_case_by_scenario(scenario: str) -> Optional[Dict[str, Any]]:
    for item in load_failure_cases():
        if item.get("scenario") == scenario:
            return item
    return None


def data_quality_rule_names() -> List[str]:
    return [
        "%s：%s" % (item.get("case_id", ""), item.get("name", ""))
        for item in load_data_quality_cases()
    ]


def knowledge_overview() -> Dict[str, Any]:
    role_profiles = load_role_profiles()
    jd_samples = load_jd_samples()
    clean_jobs = load_clean_jobs()
    chinese_jobs = load_chinese_jobs()
    resume_samples = load_resume_samples()
    quality_cases = load_data_quality_cases()
    failure_cases = load_failure_cases()
    job_sources = load_job_sources()
    return {
        "root": str(DATA_ROOT),
        "role_profiles": {
            "count": len(role_profiles),
            "roles": [item.get("role", "") for item in role_profiles],
            "used_by": ["resume_audit", "matching", "interview_agent"],
        },
        "jd_samples": {
            "count": len(jd_samples),
            "used_by": ["knowledge_overview", "source_traceability"],
        },
        "clean_jobs": {
            "count": len(clean_jobs),
            "statuses": sorted({str(item.get("status", "")) for item in clean_jobs if item.get("status")}),
            "used_by": ["sql_seed", "approved_job_index", "demo_jobs"],
        },
        "chinese_jobs": {
            "count": len(chinese_jobs),
            "unique_source_id_count": len(
                {str(item.get("source_id", "")) for item in chinese_jobs if item.get("source_id")}
            ),
            "unique_source_link_count": len(
                {str(item.get("source_link", "")) for item in chinese_jobs if item.get("source_link")}
            ),
            "statuses": sorted({str(item.get("status", "")) for item in chinese_jobs if item.get("status")}),
            "used_by": ["sql_pending_jobs", "job_review", "source_traceability"],
        },
        "resume_samples": {
            "count": len(resume_samples),
            "used_by": ["tests", "demo_baseline"],
        },
        "data_quality_cases": {
            "count": len(quality_cases),
            "used_by": ["job_audit_hints", "tests"],
        },
        "failure_cases": {
            "count": len(failure_cases),
            "scenarios": [item.get("scenario", "") for item in failure_cases],
            "used_by": ["resume_audit", "interview_agent", "matching_hints"],
        },
        "job_sources": {
            "count": len(job_sources),
            "accessible_count": sum(
                1 for item in job_sources if str(item.get("page_accessible", "")).lower() == "true"
            ),
            "used_by": ["source_traceability"],
        },
    }


def merge_unique(base: Iterable[str], additions: Iterable[str], limit: int = 12) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in [*base, *additions]:
        value = str(item).strip()
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
        if len(result) >= limit:
            break
    return result
