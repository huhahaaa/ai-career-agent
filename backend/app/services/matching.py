import re
from typing import Dict, Iterable, List, Tuple

from app.services.vector_store import (
    search_similar_jobs,
    upsert_approved_job_embeddings,
    upsert_job_embedding,
)

SEMANTIC_SCORE_WEIGHT = 0.6
SKILL_COVERAGE_SCORE_WEIGHT = 0.4

DIRECTION_RULES = {
    "backend": [
        "后端",
        "backend",
        "后端开发",
        "后端服务",
        "fastapi",
        "django",
        "flask",
        "rest api",
        "api",
        "微服务",
        "数据库",
    ],
    "frontend": [
        "前端",
        "frontend",
        "react",
        "vue",
        "angular",
        "html",
        "css",
        "web 开发",
    ],
    "machine_learning": [
        "机器学习",
        "machine learning",
        "deep learning",
        "深度学习",
        "模型训练",
        "模型评估",
        "pytorch",
        "tensorflow",
        "jax",
        "nlp",
        "transformer",
        "llm",
        "rag",
        "计算机视觉",
        "多模态",
    ],
    "system": [
        "系统编程",
        "system programming",
        "rust",
        "c++",
        "zig",
        "网络",
        "可靠性",
        "可扩展性",
        "区块链",
    ],
    "product": [
        "产品",
        "product manager",
        "产品管理",
        "用户研究",
        "竞品分析",
        "需求",
        "路线图",
        "a/b 测试",
    ],
    "operations": [
        "运营",
        "operations",
        "sop",
        "流程",
        "项目协调",
        "客户运营",
        "招聘运营",
        "people operations",
    ],
    "content": [
        "内容",
        "content",
        "视频",
        "社交媒体",
        "seo",
        "文案",
        "数字媒体",
        "cms",
    ],
}

PROGRAMMING_LANGUAGE_KEYS = {
    "python",
    "javascript",
    "typescript",
    "go",
    "java",
    "rust",
    "c",
    "c++",
    "c#",
    "zig",
    "sql",
}

FRAMEWORK_TOOL_KEYS = {
    "fastapi",
    "django",
    "flask",
    "react",
    "vue",
    "angular",
    "rest api",
    "api",
    "docker",
    "aws",
    "gcp",
    "azure",
    "sqlalchemy",
    "pytest",
    "pytorch",
    "tensorflow",
    "jax",
    "langchain",
    "llm",
    "rag",
    "微服务",
    "容器",
    "云平台",
    "数据管道",
    "数据工程",
    "分布式系统",
    "模型训练",
    "模型评估",
    "部署测试",
}

LAYER_WEIGHTS = {
    "direction": 0.4,
    "language": 0.3,
    "framework_tool": 0.2,
    "bonus": 0.1,
}


def build_matching_query(resume_text: str, target_position: str = "") -> str:
    sections = [target_position.strip(), resume_text.strip()]
    return "\n".join(section for section in sections if section)


def _normalize_skill(skill: str) -> str:
    return re.sub(r"\s+", " ", str(skill).strip()).lower()


def _contains_skill(text: str, skill: str) -> bool:
    normalized_skill = _normalize_skill(skill)
    if not normalized_skill:
        return False
    if re.search(r"[a-z0-9+#.]", normalized_skill):
        pattern = r"(?<![a-z0-9+#.])%s(?![a-z0-9+#.])" % re.escape(normalized_skill)
        return re.search(pattern, text, re.IGNORECASE) is not None
    return normalized_skill in text.lower()


def _normalize_job_skills(value: object) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        raw_items = re.split(r"[,，/、\n]", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []

    seen = set()
    skills = []
    for item in raw_items:
        skill = str(item).strip()
        key = _normalize_skill(skill)
        if not skill or key in seen:
            continue
        seen.add(key)
        skills.append(skill)
    return skills


def _detect_directions(text: str) -> List[str]:
    directions = []
    for direction, keywords in DIRECTION_RULES.items():
        if any(_contains_skill(text, keyword) for keyword in keywords):
            directions.append(direction)
    return directions


def _skill_layer(skill: str) -> str:
    key = _normalize_skill(skill)
    if key in PROGRAMMING_LANGUAGE_KEYS:
        return "language"
    if key in FRAMEWORK_TOOL_KEYS:
        return "framework_tool"
    if any(key == _normalize_skill(keyword) for keywords in DIRECTION_RULES.values() for keyword in keywords):
        return "direction"
    return "bonus"


def _group_skills_by_layer(job_skills: List[str]) -> Dict[str, List[str]]:
    grouped = {"language": [], "framework_tool": [], "bonus": []}
    for skill in job_skills:
        layer = _skill_layer(skill)
        if layer == "direction":
            continue
        grouped[layer].append(skill)
    return grouped


def _capped_layer_score(matched_count: int, required_count: int, cap: int) -> float | None:
    if required_count == 0:
        return None
    denominator = min(required_count, cap)
    return round(min(matched_count, denominator) / denominator * 100, 2)


def _direction_layer_score(
    resume_text: str,
    target_position: str,
    match: Dict,
    job_skills: List[str],
) -> Tuple[float | None, List[str], List[str]]:
    job_text = " ".join(
        [
            str(match.get("title", "")),
            str(match.get("company", "")),
            " ".join(job_skills),
        ]
    )
    candidate_text = "\n".join([target_position, resume_text])
    job_directions = _detect_directions(job_text)
    candidate_directions = _detect_directions(candidate_text)
    if not job_directions:
        return None, job_directions, candidate_directions
    overlap = set(job_directions) & set(candidate_directions)
    return (100.0 if overlap else 0.0), job_directions, candidate_directions


def _hierarchical_skill_score(
    resume_text: str,
    target_position: str,
    match: Dict,
    job_skills: List[str],
    matched_skills: List[str],
) -> Tuple[float | None, Dict[str, object]]:
    if not job_skills:
        return None, {}

    direction_score, job_directions, candidate_directions = _direction_layer_score(
        resume_text,
        target_position,
        match,
        job_skills,
    )
    grouped = _group_skills_by_layer(job_skills)
    matched_keys = {_normalize_skill(skill) for skill in matched_skills}
    language_score = _capped_layer_score(
        sum(1 for skill in grouped["language"] if _normalize_skill(skill) in matched_keys),
        len(grouped["language"]),
        cap=2,
    )
    framework_score = _capped_layer_score(
        sum(1 for skill in grouped["framework_tool"] if _normalize_skill(skill) in matched_keys),
        len(grouped["framework_tool"]),
        cap=3,
    )
    bonus_score = _capped_layer_score(
        sum(1 for skill in grouped["bonus"] if _normalize_skill(skill) in matched_keys),
        len(grouped["bonus"]),
        cap=2,
    )

    weighted_parts = []
    breakdown = {}
    if direction_score is not None:
        weighted_parts.append((LAYER_WEIGHTS["direction"], direction_score))
        breakdown["direction_score"] = direction_score
    if language_score is not None:
        weighted_parts.append((LAYER_WEIGHTS["language"], language_score))
        breakdown["language_score"] = language_score
    if framework_score is not None:
        weighted_parts.append((LAYER_WEIGHTS["framework_tool"], framework_score))
        breakdown["framework_tool_score"] = framework_score
    if bonus_score is not None:
        weighted_parts.append((LAYER_WEIGHTS["bonus"], bonus_score))
        breakdown["bonus_score"] = bonus_score

    if not weighted_parts:
        return None, breakdown

    weight_total = sum(weight for weight, _score in weighted_parts)
    score = sum(weight * value for weight, value in weighted_parts) / weight_total
    if direction_score == 0:
        score *= 0.55
    if language_score == 0:
        score *= 0.65

    breakdown["job_directions"] = job_directions
    breakdown["candidate_directions"] = candidate_directions
    return round(score, 2), breakdown


def _semantic_component_score(raw_score: float) -> float:
    if raw_score <= 0:
        return 0
    return round(min(100, 50 + raw_score * 0.5), 2)


def _weighted_match_score(semantic_score: float, skill_score: float | None) -> float:
    if skill_score is None:
        return round(semantic_score, 2)
    return round(
        semantic_score * SEMANTIC_SCORE_WEIGHT
        + skill_score * SKILL_COVERAGE_SCORE_WEIGHT,
        2,
    )


def _apply_hierarchy_caps(score: float, ability_breakdown: Dict[str, object]) -> float:
    if ability_breakdown.get("direction_score") == 0:
        score = min(score, 55.0)
    if ability_breakdown.get("language_score") == 0:
        score = min(score, 59.0)
    return round(score, 2)


def _weighted_reason(semantic_score: float, skill_score: float | None) -> str:
    if skill_score is None:
        return "简历与岗位描述的语义匹配分为 %.1f 分" % semantic_score
    return "综合匹配分由语义匹配分 %.1f 和分层能力匹配分 %.1f 加权得到" % (
        semantic_score,
        skill_score,
    )


def enrich_match_results(
    resume_text: str,
    matches: List[Dict],
    target_position: str = "",
) -> List[Dict]:
    enriched = []
    for match in matches:
        raw_semantic_score = round(float(match.get("score") or 0), 2)
        semantic_score = _semantic_component_score(raw_semantic_score)
        job_skills = _normalize_job_skills(match.get("skills"))
        matched_skills = [
            skill for skill in job_skills if _contains_skill(resume_text, skill)
        ]
        missing_skills = [
            skill for skill in job_skills if skill not in matched_skills
        ]
        skill_score, ability_breakdown = _hierarchical_skill_score(
            resume_text,
            target_position,
            match,
            job_skills,
            matched_skills,
        )
        score = _apply_hierarchy_caps(
            _weighted_match_score(semantic_score, skill_score),
            ability_breakdown,
        )

        if not job_skills:
            gap_analysis = "岗位技能字段不足，暂无法计算技能缺口。"
            suggestion = "建议先补充岗位技能词，再重新运行匹配。"
        elif missing_skills:
            gap_analysis = "已命中 %s/%s 项技能，缺少：%s。" % (
                len(matched_skills),
                len(job_skills),
                "、".join(missing_skills),
            )
            suggestion = "建议在简历项目或技能栏补充：%s。" % "、".join(missing_skills)
        else:
            gap_analysis = "岗位技能要求已全部命中。"
            suggestion = "可以继续强化项目量化结果和岗位相关经历。"

        enriched.append(
            {
                **match,
                "score": score,
                "semantic_score": semantic_score,
                "skill_coverage_score": skill_score,
                "ability_breakdown": ability_breakdown,
                "reason": _weighted_reason(semantic_score, skill_score),
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "gap_analysis": gap_analysis,
                "suggestion": suggestion,
            }
        )
    enriched.sort(key=lambda item: item.get("score", 0), reverse=True)
    return enriched


def match_resume_to_jobs(
    resume_text: str,
    target_position: str = "",
    top_k: int = 5,
) -> List[Dict]:
    query = build_matching_query(resume_text, target_position)
    matches = search_similar_jobs(query=query, top_k=top_k)
    return enrich_match_results(resume_text, matches, target_position)


def index_approved_job(job: Dict) -> Dict:
    return upsert_job_embedding(job)


def index_approved_jobs(jobs: Iterable[Dict]) -> Dict:
    return upsert_approved_job_embeddings(jobs)
