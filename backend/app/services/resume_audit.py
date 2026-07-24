"""简历审核服务：用 LLM 深度检测空泛表达、夸大风险、前后不一致等问题。"""

import json
import logging
import re
from typing import Any, Dict, List

from app.services.interview_agent import _parse_json_fallback, _safe_call_llm

logger = logging.getLogger(__name__)

# ── 规则层快速检测（不调 LLM） ────────────────────────────────────
VAGUE_PHRASES = [
    "熟悉", "了解", "参与", "负责相关", "具有一定",
    "协助", "配合", "支持", "帮忙",
]
BIASED_PHRASES = [
    "精通所有", "完全负责", "全权负责",
    "业内顶尖", "无人能及", "最优秀",
]


def _find_vague_phrases(text: str) -> List[str]:
    return [p for p in VAGUE_PHRASES if p in text]


def _find_biased_phrases(text: str) -> List[str]:
    return [p for p in BIASED_PHRASES if p in text]


def _has_quantifier(text: str) -> bool:
    return bool(re.search(r"\d+", text))


# ── LLM 深度审核 ──────────────────────────────────────────────────


def audit_resume_text(resume_text: str, target_position: str = "") -> Dict[str, Any]:
    """审核简历：规则层快速扫描 + LLM 深度分析双保险。"""
    # 1. 规则层快速扫描
    vague_flags = _find_vague_phrases(resume_text)
    biased_flags = _find_biased_phrases(resume_text)

    rule_score = 100 - len(vague_flags) * 5 - len(biased_flags) * 10

    # 2. LLM 深度分析
    llm_result = _llm_deep_audit(resume_text, target_position)

    # 3. 合并结果
    llm_issues = llm_result.get("issues", [])
    llm_score = llm_result.get("score", 75)
    llm_suggestions = llm_result.get("suggestions", [])

    # 综合评分：规则 30% + LLM 70%
    final_score = int(rule_score * 0.3 + llm_score * 0.7)
    final_score = max(0, min(100, final_score))

    # 合并风险标记
    all_risks: List[str] = []
    all_risks.extend(f"空泛表达: {p}" for p in vague_flags)
    all_risks.extend(f"夸大风险: {p}" for p in biased_flags)
    all_risks.extend(llm_issues)

    # 合并建议
    suggestions = list(llm_suggestions)
    if vague_flags and "补充量化数据" not in str(suggestions):
        suggestions.insert(0, "避免使用'熟悉''参与'等笼统词汇，改为'使用XX实现了YY，提升ZZ%'")
    if biased_flags and "避免夸大" not in str(suggestions):
        suggestions.insert(0, "降低表述的绝对化程度，用数据和事实代替主观评价")
    if not suggestions:
        suggestions.append("补充项目背景、个人职责、技术动作和量化结果")

    # 缺失关键词
    missing_keywords = llm_result.get("missing_keywords", [])
    if target_position and not missing_keywords:
        missing_keywords = _extract_missing_keywords(resume_text, target_position)

    return {
        "score": final_score,
        "risk_flags": all_risks[:10],  # 最多 10 条
        "suggestions": suggestions[:8],  # 最多 8 条
        "missing_keywords": missing_keywords[:8],
        "risk_level": _determine_risk_level(final_score, all_risks),
    }


def _llm_deep_audit(resume_text: str, target_position: str) -> Dict[str, Any]:
    """LLM 深度审核简历。"""
    position_hint = ""
    if target_position:
        position_hint = f"\n目标岗位：{target_position}\n请同时检查简历与目标岗位的匹配度。"

    prompt = f"""请审核以下简历，从以下维度逐一检查：

简历内容：
{resume_text[:4000]}
{position_hint}

检查维度：
1. 技能是否有项目经历支撑？（宣称"掌握React"但项目中没有React经验）
2. 项目描述是否缺少量化结果？（如"负责系统优化"未说明优化了多少）
3. 是否出现前后不一致？（技能列表说会 A，但项目经历全是 B）
4. 是否有夸大风险？（"精通所有框架""完全负责整个项目"）
5. 项目经历是否说明了个人贡献？（vs 只说团队成果）
6. 是否缺少必要字段？（无教育背景、无项目时间等）

输出 JSON（只输出 JSON）：
{{
  "score": 0-100,
  "issues": ["问题描述1", "问题描述2"],
  "suggestions": ["改进建议1", "改进建议2"],
  "missing_keywords": ["缺失关键词1"]
}}
"""
    result = _safe_call_llm(
        system_prompt="你是资深 HR 和简历审核专家。请严格审核简历问题。只输出 JSON。",
        user_prompt=prompt,
        fallback=json.dumps({
            "score": 70,
            "issues": [],
            "suggestions": ["建议补充具体数字和成果"],
            "missing_keywords": [],
        }, ensure_ascii=False),
        temperature=0.3,
    )
    return _parse_json_fallback(result)


def _extract_missing_keywords(resume_text: str, target_position: str) -> List[str]:
    """提取简历中缺失的岗位关键词。"""
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
    if isinstance(parsed, list):
        return parsed
    return []


def _determine_risk_level(score: int, issues: List[str]) -> str:
    """根据分数和问题数量确定风险等级。"""
    if score < 50 or len(issues) >= 5:
        return "高"
    elif score < 70 or len(issues) >= 2:
        return "中"
    return "低"
