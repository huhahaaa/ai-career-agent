"""简历审核 Agent 服务。

覆盖开发计划「阶段 3：简历审核」要求识别的四类风险：
  - 模糊表达（vague）          -> 空泛、套话、无具体动作
  - 关键词缺失（missing）       -> 岗位/通用技能关键词缺失
  - 项目描述不完整（incomplete） -> 缺个人职责/贡献/量化结果
  - 夸大风险（biased）          -> 绝对化、夸大表述

并参考面试 Agent 的做法，补充：
  - 岗位感知（position-aware）：按目标岗位用专属关键词库做缺失检测与匹配度评分
  - 结构化维度评分：完整度/岗位匹配/量化/表达/项目质量 五维
  - 评分校准（rule vs llm）：保留规则基线分，便于与 LLM 分对照
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.interview_agent import (
    DEFAULT_POSITIONS,
    _contains_quantifier,
    _contains_tech_keywords,
    _llm_enabled,
    _normalize_position,
    _parse_json_fallback,
    _safe_call_llm,
    _strip_markdown,
)
from app.services.job_data import derive_all_position_keywords, FALLBACK_KEYWORDS

# ---------------------------------------------------------------------------
# 常量与词表
# ---------------------------------------------------------------------------

# 简历必备字段检测（正则）
RESUME_FIELD_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)"),
    "education": re.compile(r"(本科|硕士|研究生|博士|大专|学历|毕业|大学|学院|学校)"),
    "experience": re.compile(r"(实习|工作经历|工作经验|就职|任职|公司|岗位|职责)"),
    "projects": re.compile(r"(项目|project|作品|案例)"),
    "skills": re.compile(r"(技能|熟悉|掌握|精通|擅长|技术栈|工具)"),
    "portfolio": re.compile(r"(github|portfolio|个人主页|作品集|网站|http[s]?://)"),
}
RESUME_FIELD_CN = {
    "email": "联系方式(邮箱)",
    "phone": "手机号",
    "education": "教育背景",
    "experience": "工作经历",
    "projects": "项目经历",
    "skills": "技能清单",
    "portfolio": "作品集/主页",
}

# 简历审核维度（满分 100）
RESUME_DIMENSION_MAX = {
    "completeness": 25,    # 字段齐全度
    "position_match": 25,  # 岗位匹配度
    "quantification": 20,  # 量化程度
    "clarity": 15,         # 表达质量（空泛扣分）
    "project_quality": 15, # 项目完整度
}
RESUME_DIMENSION_CN = {
    "completeness": "内容完整度",
    "position_match": "岗位匹配度",
    "quantification": "量化程度",
    "clarity": "表达清晰度",
    "project_quality": "项目完整度",
}

# 各岗位核心技能关键词（用于「关键词缺失」检测，无 LLM 也生效）
# 优先使用 24 条真实岗位数据自动派生；数据缺失/缺桶时回退到兜底词库
POSITION_REQUIRED_KEYWORDS = {**FALLBACK_KEYWORDS, **derive_all_position_keywords()}

# 简历场景的模糊/夸大词表（相比面试 Agent 更聚焦项目与成果表述）
VAGUE_PHRASES = [
    "一些", "比较好", "差不多", "还可以", "很多", "一定程度", "相关经验",
    "之类的", "等等", "大概", "参与过", "负责过", "协助", "熟练使用", "独立负责",
]
BIASED_PHRASES = [
    "唯一", "绝对", "完美", "100%", "完全", "肯定", "一定", "没有缺点",
    "精通一切", "无人能及", "天下第一", "最优秀的", "业界领先", "顶尖",
]


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _clamp(value: Any, max_score: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = 0
    return max(0, min(max_score, number))


def _detect_resume_fields(text: str) -> Dict[str, bool]:
    """检测简历是否包含各类必备字段。"""
    return {field: bool(p.search(text)) for field, p in RESUME_FIELD_PATTERNS.items()}


def _detect_expression_risks(text: str) -> "tuple[List[str], List[str]]":
    """返回 (空泛词列表, 夸大词列表)。"""
    vague = [p for p in VAGUE_PHRASES if p in text]
    biased = [p for p in BIASED_PHRASES if p in text]
    return vague, biased


def _split_projects(text: str) -> List[str]:
    """粗略切分简历中的项目段落（每段 >20 字）。"""
    chunks = re.split(r"(?:项目[一二三四五六七八九十0-9]+|项目经历|项目经验|作品|案例)", text)
    return [c.strip() for c in chunks if len(c.strip()) > 20]


def _assess_project_quality(projects: List[str]) -> "tuple[int, List[str]]":
    """返回 (项目完整度评分 0-15, 问题列表)。"""
    issues: List[str] = []
    if not projects:
        return 6, ["未检测到结构化项目经历，建议增加 2-3 个重点项目"]
    good = 0
    for p in projects:
        has_role = any(k in p for k in ("负责", "角色", "主导", "参与", "设计", "开发", "实现", "搭建"))
        has_quant = _contains_quantifier(p)
        has_result = any(
            k in p for k in ("提升", "降低", "增长", "提高", "减少", "达成", "结果", "效果", "收益", "优化")
        )
        if has_role and (has_quant or has_result):
            good += 1
        else:
            if not has_role:
                issues.append("存在缺少个人职责与贡献说明的项目描述")
            if not (has_quant or has_result):
                issues.append("存在缺少量化结果/效果的项目描述")
    ratio = good / len(projects)
    score = round(15 * ratio)
    issues = list(dict.fromkeys(issues))[:2]
    return score, issues


def _missing_keywords(text: str, target_position: str) -> List[str]:
    """岗位/通用技能关键词缺失检测（无 LLM 也生效）。"""
    lowered = text.lower()
    normalized = _normalize_position(target_position) if target_position else ""
    if normalized:
        pool = POSITION_REQUIRED_KEYWORDS.get(normalized, [])
    else:
        seen = set()
        pool = []
        for kws in POSITION_REQUIRED_KEYWORDS.values():
            for k in kws:
                if k.lower() not in seen:
                    seen.add(k.lower())
                    pool.append(k)
        pool = pool[:12]
    return [k for k in pool if k.lower() not in lowered][:6]


def _score_resume_dimensions(text: str, target_position: str) -> Dict[str, Any]:
    """按规则计算五维评分与风险标记。"""
    lowered = text.lower()
    fields = _detect_resume_fields(text)

    # 内容完整度：必备字段齐全比例
    present = sum(1 for v in fields.values() if v)
    completeness = round(25 * present / len(fields))

    # 岗位匹配度：目标岗位专属关键词命中率（命中过半给高分）
    normalized = _normalize_position(target_position) if target_position else ""
    if normalized:
        required = POSITION_REQUIRED_KEYWORDS.get(normalized, [])
        if required:
            hit = sum(1 for kw in required if kw.lower() in lowered)
            position_match = round(25 * min(1.0, hit / max(1, len(required) * 0.5)))
        else:
            position_match = 8
    else:
        position_match = 18 if _contains_tech_keywords(text) else 8
    position_match = max(0, min(25, position_match))

    # 量化程度：是否含数字/百分比
    quant_count = len(re.findall(r"\d+(?:\.\d+)?\s*(?:%|倍|个|次|万|k|w|人|元|月|天)", text))
    if _contains_quantifier(text) and quant_count >= 3:
        quantification = 20
    elif _contains_quantifier(text):
        quantification = 12
    else:
        quantification = 4

    # 表达清晰度：空泛词扣分
    vague, biased = _detect_expression_risks(text)
    clarity = 15 - min(10, len(vague) * 3)
    clarity = max(3, clarity)

    # 项目完整度
    projects = _split_projects(text)
    project_score, _ = _assess_project_quality(projects)

    scores = {
        "completeness": completeness,
        "position_match": position_match,
        "quantification": quantification,
        "clarity": clarity,
        "project_quality": project_score,
    }
    return {
        "dimension_scores": scores,
        "total": sum(scores.values()),
        "vague_flags": vague,
        "biased_flags": biased,
        "fields": fields,
    }


def _build_rule_suggestions(
    scores: Dict[str, int],
    missing_keywords: List[str],
    missing_fields: List[str],
    vague: List[str],
    biased: List[str],
    normalized: str,
) -> List[str]:
    out: List[str] = []
    if missing_keywords:
        out.append("补充岗位关键词：%s，提升 ATS 命中率与岗位匹配度。" % "、".join(missing_keywords[:5]))
    if missing_fields:
        out.append("补齐缺失板块：%s，保证简历信息完整。" % "、".join(missing_fields))
    if vague:
        out.append("替换空泛表述（如 %s），用具体动作和量化结果描述经历。" % "、".join(vague[:3]))
    if biased:
        out.append("弱化绝对化/夸大表述（如 %s），用可验证事实替代。" % "、".join(biased[:3]))
    if scores.get("quantification", 0) < 12:
        out.append("增加量化成果（效率提升%、成本降低、用户增长等），增强说服力。")
    if scores.get("project_quality", 0) < 10:
        out.append("用 STAR 描述项目：明确你的角色、行动与可量化结果。")
    if normalized:
        out.append("针对「%s」岗位，突出匹配的技术栈与项目成果。" % normalized)
    return out


def _llm_deep_audit(
    text: str, target_position: str, normalized: str
) -> "tuple[Optional[Dict[str, int]], Optional[List[str]], Optional[List[str]]]":
    """调用 LLM 做深度审核，返回 (维度分, 缺失关键词, 建议)。失败返回全 None。"""
    position_hint = (
        "目标岗位：%s（归一化：%s）" % (target_position, normalized)
        if target_position
        else "目标岗位：未指定"
    )
    prompt = (
        "请对以下简历做深度审核，覆盖：模糊表达、关键词缺失、项目描述完整性、夸大风险。\n\n"
        "简历文本：\n%s\n\n%s\n\n"
        "请只输出 JSON：\n"
        '{\n'
        '  "dimension_scores": {"completeness": 数字, "position_match": 数字, "quantification": 数字, "clarity": 数字, "project_quality": 数字},\n'
        '  "missing_keywords": ["建议补充的岗位/技能关键词1", "..."],\n'
        '  "suggestions": ["改进建议1", "改进建议2"]\n'
        '}' % (text[:4000], position_hint)
    )
    result = _safe_call_llm(
        system_prompt="你是资深简历优化顾问，严格只输出 JSON，不要其他文字。",
        user_prompt=prompt,
        fallback="",
        temperature=0.3,
    )
    parsed = _parse_json_fallback(result)
    if not isinstance(parsed, dict):
        return None, None, None
    dim = parsed.get("dimension_scores")
    if not isinstance(dim, dict):
        dim = None
    else:
        dim = {k: _clamp(v, RESUME_DIMENSION_MAX[k]) for k, v in dim.items() if k in RESUME_DIMENSION_MAX}
    missing = parsed.get("missing_keywords")
    if not isinstance(missing, list):
        missing = None
    sugg = parsed.get("suggestions")
    if not isinstance(sugg, list):
        sugg = None
    return dim, missing, sugg


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------

def audit_resume_text(resume_text: str, target_position: str = "") -> Dict[str, Any]:
    """审核简历文本，返回结构化结果（含维度评分、风险标记、建议、校准分）。"""
    text = resume_text or ""
    normalized = _normalize_position(target_position) if target_position else ""

    dim = _score_resume_dimensions(text, target_position)
    scores = dim["dimension_scores"]
    vague = dim["vague_flags"]
    biased = dim["biased_flags"]
    fields = dim["fields"]

    missing_keywords = _missing_keywords(text, target_position)
    projects = _split_projects(text)
    _, proj_issues = _assess_project_quality(projects)

    # 四类风险标记（开发计划阶段 3）
    risk_flags: List[str] = []
    if vague:
        risk_flags.append("模糊表达：存在空泛/套话（如 %s）" % "、".join(vague[:4]))
    if biased:
        risk_flags.append("夸大风险：存在绝对化/夸大表述（如 %s）" % "、".join(biased[:4]))
    if missing_keywords:
        risk_flags.append("关键词缺失：建议补充 %s" % "、".join(missing_keywords[:5]))
    missing_fields = [RESUME_FIELD_CN[f] for f, ok in fields.items() if not ok]
    if missing_fields:
        risk_flags.append("内容不完整：缺少 %s" % "、".join(missing_fields))
    if proj_issues:
        risk_flags.extend(proj_issues)

    rule_total = dim["total"]

    # LLM 深度审核（可选；失败回退规则评分）
    llm_dim = None
    llm_missing = None
    llm_suggestions = None
    if _llm_enabled():
        llm_dim, llm_missing, llm_suggestions = _llm_deep_audit(text, target_position, normalized)

    # 合并维度评分：有 LLM 用 LLM，否则用规则
    final_scores = llm_dim if llm_dim else scores
    final_total = sum(final_scores.get(k, scores.get(k, 0)) for k in RESUME_DIMENSION_MAX)

    # 缺失关键词：LLM 优先，规则兜底
    if llm_missing:
        missing_keywords = list(dict.fromkeys(llm_missing))[:6]

    # 建议：规则兜底 + LLM 补充
    rule_suggestions = _build_rule_suggestions(scores, missing_keywords, missing_fields, vague, biased, normalized)
    suggestions = (llm_suggestions or []) + rule_suggestions
    suggestions = list(dict.fromkeys(suggestions))[:8]

    risk_level = "高" if final_total < 50 else ("中" if final_total < 75 else "低")

    return {
        "score": final_total,
        "dimension_scores": final_scores,
        "risk_flags": risk_flags,
        "suggestions": suggestions,
        "missing_keywords": missing_keywords,
        "risk_level": risk_level,
        "rule_score": rule_total,
        "llm_score": final_total if llm_dim else None,
        "detected_fields": fields,
        "position_bucket": normalized,
    }
