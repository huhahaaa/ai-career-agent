import re
from typing import Dict, Iterable, List, Tuple

from app.services.vector_store import (
    search_similar_jobs,
    upsert_approved_job_embeddings,
    upsert_job_embedding,
)
from app.services.knowledge_base import merge_unique, role_profile_gap

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

ROLE_CATEGORY_MAP = {
    "前端开发": "frontend",
    "后端开发": "backend",
    "算法/机器学习": "machine_learning",
    "产品经理": "product",
    "运营": "operations",
    "数字媒体/内容": "content",
}

ROLE_LABELS = {
    "backend": "后端/服务端",
    "frontend": "前端",
    "machine_learning": "算法/机器学习",
    "system": "系统工程",
    "product": "产品",
    "operations": "运营",
    "content": "内容/数字媒体",
}

TECHNICAL_ROLES = {"backend", "frontend", "machine_learning", "system"}
BUSINESS_ROLES = {"product", "operations", "content"}

AI_APPLICATION_KEYWORDS = [
    "ai应用",
    "ai 应用",
    "大模型应用",
    "llm应用",
    "llm 应用",
    "智能体开发",
    "agent开发",
    "agent 开发",
    "rag",
    "langchain",
]

ENGINEERING_KEYWORDS = ["开发", "工程师", "研发", "程序", "技术", "应用"]

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


def _has_any(text: str, keywords: List[str]) -> bool:
    return any(_contains_skill(text, keyword) for keyword in keywords)


def _unique_roles(roles: Iterable[str]) -> List[str]:
    result = []
    seen = set()
    for role in roles:
        if not role or role in seen:
            continue
        seen.add(role)
        result.append(role)
    return result


def _target_role_groups(target_position: str) -> List[str]:
    text = str(target_position or "")
    if not text.strip():
        return []

    roles = []
    if _has_any(text, ["运营", "增长", "新媒体", "用户运营", "产品运营"]):
        roles.append("operations")
    if _has_any(text, ["产品经理", "ai产品", "产品"]) and "operations" not in roles:
        roles.append("product")
    if _has_any(text, ["内容", "数字媒体", "视频", "剪辑", "文案", "设计"]):
        roles.append("content")
    if _has_any(text, ["前端", "frontend", "web开发", "web 开发", "react", "vue"]):
        roles.append("frontend")
    if _has_any(text, ["后端", "服务端", "backend", "fastapi", "django", "java开发", "python开发"]):
        roles.append("backend")
    if _has_any(text, ["算法", "机器学习", "深度学习", "模型训练", "推荐算法", "nlp算法"]):
        roles.append("machine_learning")

    is_ai_application = _has_any(text, AI_APPLICATION_KEYWORDS)
    is_engineering = _has_any(text, ENGINEERING_KEYWORDS)
    if is_ai_application and is_engineering:
        roles.append("backend")

    if not roles:
        roles.extend(_detect_directions(text))
    return _unique_roles(roles)


def _job_role_groups(match: Dict, job_skills: List[str]) -> List[str]:
    category = str(match.get("category") or "").strip()
    mapped = ROLE_CATEGORY_MAP.get(category)
    if mapped:
        return [mapped]

    title = str(match.get("title") or "")
    if _has_any(title, ["运营", "增长", "新媒体运营", "用户运营", "产品运营"]):
        return ["operations"]
    if _has_any(title, ["产品经理", "ai产品", "产品"]):
        return ["product"]
    if _has_any(title, ["内容", "数字媒体", "视频", "剪辑", "文案", "设计"]):
        return ["content"]
    if _has_any(title, ["前端", "frontend", "web前端", "react", "vue"]):
        return ["frontend"]
    if _has_any(title, ["后端", "服务端", "backend", "平台开发", "应用开发"]):
        return ["backend"]
    if _has_any(title, ["算法", "机器学习", "深度学习", "模型训练"]):
        return ["machine_learning"]

    text = " ".join(
        [
            category,
            title,
            str(match.get("company", "")),
            " ".join(job_skills),
        ]
    )
    return _detect_directions(text)


def _role_compatibility_score(target_roles: List[str], job_roles: List[str]) -> float:
    if not target_roles or not job_roles:
        return 1.0
    target_set = set(target_roles)
    job_set = set(job_roles)
    if target_set & job_set:
        return 1.0
    if target_set <= TECHNICAL_ROLES and job_set & BUSINESS_ROLES:
        return 0.2
    if target_set & BUSINESS_ROLES and job_set <= TECHNICAL_ROLES:
        return 0.35
    if target_set <= TECHNICAL_ROLES and job_set <= TECHNICAL_ROLES:
        return 0.65
    if target_set & BUSINESS_ROLES and job_set & BUSINESS_ROLES:
        return 0.5
    return 0.55


def _apply_role_compatibility_cap(score: float, compatibility: float) -> float:
    if compatibility >= 1.0:
        return round(score, 2)
    if compatibility <= 0.25:
        return round(min(score, 42.0), 2)
    if compatibility <= 0.4:
        return round(min(score, 55.0), 2)
    if compatibility <= 0.65:
        return round(min(score, 68.0), 2)
    return round(score, 2)


def _role_labels(roles: List[str]) -> str:
    return "、".join(ROLE_LABELS.get(role, role) for role in roles) or "未识别"


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
        job_missing_skills = list(missing_skills)
        profile_gap = role_profile_gap(resume_text, target_position)
        profile_missing = []
        if profile_gap:
            profile_missing = [
                *profile_gap.get("missing_must_have", []),
                *profile_gap.get("missing_preferred", []),
            ]
            missing_skills = merge_unique(missing_skills, profile_missing, limit=16)
        skill_score, ability_breakdown = _hierarchical_skill_score(
            resume_text,
            target_position,
            match,
            job_skills,
            matched_skills,
        )
        target_roles = _target_role_groups(target_position)
        job_roles = _job_role_groups(match, job_skills)
        role_compatibility = _role_compatibility_score(target_roles, job_roles)
        ability_breakdown["target_roles"] = target_roles
        ability_breakdown["job_roles"] = job_roles
        ability_breakdown["target_compatibility_score"] = round(role_compatibility * 100, 2)
        if profile_gap:
            ability_breakdown["role_profile"] = {
                "role": profile_gap.get("role", ""),
                "profile_id": profile_gap.get("profile_id", ""),
                "profile_version": profile_gap.get("profile_version", ""),
                "matched_must_have": profile_gap.get("matched_must_have", []),
                "missing_must_have": profile_gap.get("missing_must_have", []),
                "missing_preferred": profile_gap.get("missing_preferred", []),
                "evidence_signals": profile_gap.get("evidence_signals", []),
            }
        score = _apply_hierarchy_caps(
            _weighted_match_score(semantic_score, skill_score),
            ability_breakdown,
        )
        score = _apply_role_compatibility_cap(score, role_compatibility)

        if not job_skills:
            gap_analysis = "岗位技能字段不足，暂无法计算技能缺口。"
            suggestion = "建议先补充岗位技能词，再重新运行匹配。"
        elif missing_skills:
            gap_analysis = "已命中 %s/%s 项JD技能，缺少：%s。" % (
                len(matched_skills),
                len(job_skills),
                "、".join(job_missing_skills or missing_skills),
            )
            if profile_gap and profile_missing:
                gap_analysis += " 岗位画像还提示缺口：%s。" % "、".join(profile_missing[:8])
            suggestion = "建议在简历项目或技能栏补充：%s。" % "、".join(missing_skills)
            if profile_gap and profile_gap.get("evidence_signals"):
                suggestion += " 同时补充岗位画像证据信号：%s。" % "、".join(
                    str(item) for item in profile_gap["evidence_signals"][:4]
                )
        else:
            gap_analysis = "岗位技能要求已全部命中。"
            suggestion = "可以继续强化项目量化结果和岗位相关经历。"

        if role_compatibility < 1.0:
            gap_analysis += " 目标岗位大类为%s，当前岗位大类为%s，已按岗位方向不匹配降权。" % (
                _role_labels(target_roles),
                _role_labels(job_roles),
            )
            if role_compatibility <= 0.25:
                suggestion = "建议优先查看目标岗位同方向的开发/技术岗位；该岗位更适合作为跨方向参考，不建议作为主匹配结果。"

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
    candidate_limit = min(80, max(top_k, top_k * 8))
    matches = search_similar_jobs(query=query, top_k=candidate_limit)
    return enrich_match_results(resume_text, matches, target_position)[:top_k]


def index_approved_job(job: Dict) -> Dict:
    return upsert_job_embedding(job)


def index_approved_jobs(jobs: Iterable[Dict]) -> Dict:
    return upsert_approved_job_embeddings(jobs)
