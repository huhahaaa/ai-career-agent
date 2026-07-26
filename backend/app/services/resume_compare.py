from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILL_DICTIONARY_PATH = PROJECT_ROOT / "data" / "processed" / "skill_dictionary.json"

EXTRA_SKILLS = {
    "Docker": ["docker", "容器", "镜像"],
    "Redis": ["redis", "缓存"],
    "pytest": ["pytest", "单元测试", "自动化测试"],
    "JWT": ["jwt", "token", "鉴权", "认证"],
    "SQLAlchemy": ["sqlalchemy", "orm"],
    "Chroma": ["chroma", "chromadb", "向量库"],
    "MediaPipe": ["mediapipe", "姿态", "视线"],
    "OpenCV": ["opencv", "cv2", "图像处理"],
}

TARGET_KEYWORDS = {
    "backend": ["Python", "FastAPI", "REST API", "SQL", "SQLAlchemy", "Redis", "Docker", "pytest", "JWT"],
    "frontend": ["JavaScript", "TypeScript", "React", "Vue", "REST API"],
    "algorithm": ["Python", "机器学习", "模型评测", "LLM", "RAG"],
    "product": ["用户研究", "产品分析", "数据分析"],
    "operations": ["数据分析", "SOP"],
    "media": ["视频剪辑", "内容策略", "SEO", "GEO"],
}


def _load_skill_rules() -> Dict[str, List[str]]:
    rules: Dict[str, List[str]] = {}
    try:
        payload = json.loads(SKILL_DICTIONARY_PATH.read_text(encoding="utf-8"))
        for skill, aliases in payload.get("normalization_rules", {}).items():
            rules[skill] = [skill, *aliases]
    except (OSError, json.JSONDecodeError):
        rules = {}
    for skill, aliases in EXTRA_SKILLS.items():
        rules.setdefault(skill, [skill])
        for alias in aliases:
            if alias not in rules[skill]:
                rules[skill].append(alias)
    return rules


def extract_resume_skills(text: str) -> List[str]:
    lowered = (text or "").lower()
    skills = []
    for skill, aliases in _load_skill_rules().items():
        if any(str(alias).lower() in lowered for alias in aliases):
            skills.append(skill)
    return sorted(skills)


def _target_bucket(target_position: str) -> str:
    text = (target_position or "").lower()
    if not text.strip():
        return ""
    if any(term in text for term in ["后端", "backend", "python", "fastapi"]):
        return "backend"
    if any(term in text for term in ["前端", "frontend", "react", "vue"]):
        return "frontend"
    if any(term in text for term in ["算法", "机器学习", "machine learning", "llm", "rag"]):
        return "algorithm"
    if any(term in text for term in ["产品", "product", "pm"]):
        return "product"
    if any(term in text for term in ["运营", "operation", "ops"]):
        return "operations"
    if any(term in text for term in ["数媒", "媒体", "content", "video"]):
        return "media"
    return ""


def _quantified_signal_score(text: str) -> int:
    matches = re.findall(r"\d+%|\d+\s*(?:个|次|人|天|周|月|秒|分钟|ms|k|w)", text or "", re.I)
    return min(20, len(matches) * 5)


def _project_signal_score(text: str) -> int:
    score = 0
    for keyword in ["项目", "负责", "实现", "优化", "上线", "测试", "接口", "数据"]:
        if keyword in (text or ""):
            score += 3
    return min(15, score)


def version_profile(text: str, target_position: str = "") -> dict:
    skills = extract_resume_skills(text)
    bucket = _target_bucket(target_position)
    required = TARGET_KEYWORDS.get(bucket, [])
    matched = [skill for skill in required if skill in skills]
    missing = [skill for skill in required if skill not in skills]
    coverage = round(len(matched) / len(required) * 100, 1) if required else 0
    if required:
        score = min(
            100,
            round(
                35
                + coverage * 0.45
                + _quantified_signal_score(text)
                + _project_signal_score(text),
                1,
            ),
        )
    else:
        score = min(
            100,
            round(
                45
                + min(len(skills), 10) * 3
                + _quantified_signal_score(text)
                + _project_signal_score(text),
                1,
            ),
        )
    return {
        "skills": skills,
        "target_bucket": bucket,
        "target_keywords": required,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "estimated_match_score": score,
        "skill_coverage": coverage,
        "quantified_signal_score": _quantified_signal_score(text),
        "project_signal_score": _project_signal_score(text),
    }


def compare_resume_versions(
    from_text: str,
    to_text: str,
    target_position: str = "",
) -> dict:
    before = version_profile(from_text, target_position)
    after = version_profile(to_text, target_position)
    before_skills = set(before["skills"])
    after_skills = set(after["skills"])
    before_missing = set(before["missing_keywords"])
    after_missing = set(after["missing_keywords"])
    return {
        "before": before,
        "after": after,
        "added_skills": sorted(after_skills - before_skills),
        "removed_skills": sorted(before_skills - after_skills),
        "resolved_missing_keywords": sorted(before_missing - after_missing),
        "new_missing_keywords": sorted(after_missing - before_missing),
        "score_delta": round(
            after["estimated_match_score"] - before["estimated_match_score"],
            1,
        ),
        "coverage_delta": round(after["skill_coverage"] - before["skill_coverage"], 1),
    }
