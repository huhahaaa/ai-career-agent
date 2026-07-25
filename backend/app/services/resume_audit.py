"""Resume audit service with rule checks and optional LLM review."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from app.services.interview_agent import _parse_json_fallback, _safe_call_llm

VAGUE_PHRASES = [
    "熟悉",
    "了解",
    "参与",
    "负责相关",
    "具有一定",
    "协助",
    "配合",
    "支持",
    "帮忙",
]
BIASED_PHRASES = [
    "精通所有",
    "完全负责",
    "全权负责",
    "业内顶尖",
    "无人能及",
    "最优秀",
]


def _find_vague_phrases(text: str) -> List[str]:
    return [phrase for phrase in VAGUE_PHRASES if phrase in text]


def _find_biased_phrases(text: str) -> List[str]:
    return [phrase for phrase in BIASED_PHRASES if phrase in text]


def _has_quantifier(text: str) -> bool:
    return bool(re.search(r"\d+|百分之|提升|降低|减少|增加", text))


def audit_resume_text(resume_text: str, target_position: str = "") -> Dict[str, Any]:
    vague_flags = _find_vague_phrases(resume_text)
    biased_flags = _find_biased_phrases(resume_text)
    rule_score = 100 - len(vague_flags) * 5 - len(biased_flags) * 10
    if not _has_quantifier(resume_text):
        rule_score -= 8

    llm_result = _llm_deep_audit(resume_text, target_position)
    llm_score = int(llm_result.get("score", 72))
    final_score = int(rule_score * 0.3 + llm_score * 0.7)
    final_score = max(0, min(100, final_score))

    risk_flags: List[str] = []
    risk_flags.extend("空泛表达: %s" % phrase for phrase in vague_flags)
    risk_flags.extend("夸大风险: %s" % phrase for phrase in biased_flags)
    risk_flags.extend(str(issue) for issue in llm_result.get("issues", []) if issue)

    suggestions = [
        str(item) for item in llm_result.get("suggestions", []) if item
    ]
    if vague_flags:
        suggestions.insert(
            0,
            "减少“熟悉、了解、参与”等笼统表达，改成“使用 XX 完成 YY，带来 ZZ 结果”。",
        )
    if biased_flags:
        suggestions.insert(0, "避免绝对化夸大表述，用事实和数据支撑能力描述。")
    if not _has_quantifier(resume_text):
        suggestions.append("补充量化结果，例如性能提升、缺陷减少、用户规模或交付周期。")
    if target_position:
        suggestions.append("围绕 %s 调整项目顺序和技能关键词。" % target_position)
    if not suggestions:
        suggestions.append("补充项目背景、个人职责、技术动作和量化结果。")

    missing_keywords = llm_result.get("missing_keywords", [])
    if target_position and not missing_keywords:
        missing_keywords = _extract_missing_keywords(resume_text, target_position)

    return {
        "score": final_score,
        "risk_flags": risk_flags[:10],
        "suggestions": suggestions[:8],
        "missing_keywords": [str(keyword) for keyword in missing_keywords[:8]],
        "risk_level": _determine_risk_level(final_score, risk_flags),
    }


def _llm_deep_audit(resume_text: str, target_position: str) -> Dict[str, Any]:
    position_hint = ""
    if target_position:
        position_hint = "\n目标岗位：%s\n请同时检查简历与目标岗位的匹配度。" % target_position

    prompt = f"""请审核以下简历：

简历内容：
{resume_text[:4000]}
{position_hint}

检查维度：
1. 技能是否有项目经历支撑
2. 项目描述是否缺少量化结果
3. 是否出现前后不一致
4. 是否有夸大风险
5. 项目经历是否说明个人贡献
6. 是否缺少必要字段

只输出 JSON：
{{
  "score": 0-100,
  "issues": ["问题描述1"],
  "suggestions": ["改进建议1"],
  "missing_keywords": ["缺失关键词1"]
}}
"""
    fallback = json.dumps(
        {
            "score": 72,
            "issues": [],
            "suggestions": ["建议补充具体数字、项目成果和个人贡献。"],
            "missing_keywords": [],
        },
        ensure_ascii=False,
    )
    result = _safe_call_llm(
        system_prompt="你是资深 HR 和简历审核专家。请严格审核简历问题，只输出 JSON。",
        user_prompt=prompt,
        fallback=fallback,
        temperature=0.3,
    )
    parsed = _parse_json_fallback(result)
    return parsed if isinstance(parsed, dict) else json.loads(fallback)


def _extract_missing_keywords(resume_text: str, target_position: str) -> List[str]:
    prompt = f"""目标岗位：{target_position}
简历内容：{resume_text[:2000]}

请列出 3-5 个该岗位通常需要但简历中缺失的技能关键词。
只输出 JSON 数组：["关键词1", "关键词2"]"""
    result = _safe_call_llm(
        system_prompt="你是招聘专家。只输出 JSON 数组。",
        user_prompt=prompt,
        fallback="[]",
        temperature=0.3,
    )
    parsed = _parse_json_fallback(result)
    return parsed if isinstance(parsed, list) else []


def _determine_risk_level(score: int, issues: List[str]) -> str:
    if score < 50 or len(issues) >= 5:
        return "高"
    if score < 70 or len(issues) >= 2:
        return "中"
    return "低"
