"""Interview Agent service.

Supports 4 interview modes:
  - HR面 (behavioural): focus on soft skills, motivation, team fit
  - 技术面 (technical): focus on technical depth and project experience (default)
  - 压力面 (pressure): challenging followups, stress testing
  - 反馈教练 (coach): gentle tone, detailed improvement suggestions
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from app.core.config import settings
from app.services.job_data import (
    get_position_job_summary,
    get_position_responsibilities,
)
from app.services.answer_quality import AnswerVerdict, judge_answer_quality
from app.services.interview_question_bank import (
    _POSITION_QUESTIONS,
    get_position_question_pool,
    get_question_bank_summary,
    load_question_bank,
    normalize_position,
)

logger = logging.getLogger(__name__)

_client: Any = None

# ── interview mode constants ──────────────────────────────────────────
INTERVIEW_MODES = frozenset({"HR面", "技术面", "压力面", "反馈教练"})
DEFAULT_INTERVIEW_MODE = "技术面"

# 过渡到下一题的话术池（随机选取，避免每次雷同）。
# 专业、尊重、无“嗯/呃”等无意义语气填充，也不要冗长客套。
_TRANSITIONS = [
    "好的，下一个问题。",
    "明白了，那我再问一个：",
    "了解，我们继续。",
    "好的，接着聊下一题。",
    "明白，下一个，",
]

# ── technology keyword bank ───────────────────────────────────────────
TECH_KEYWORDS = [
    "react",
    "vue",
    "angular",
    "node",
    "python",
    "java",
    "go",
    "rust",
    "typescript",
    "javascript",
    "sql",
    "mongodb",
    "redis",
    "docker",
    "kubernetes",
    "aws",
    "git",
    "linux",
    "http",
    "api",
    "rest",
    "css",
    "html",
    "spring",
    "django",
    "flask",
    "fastapi",
    "机器学习",
    "深度学习",
    "数据",
    "算法",
    "模型",
    "训练",
    "优化",
    "性能",
    "部署",
    "测试",
    "架构",
    "设计模式",
    "敏捷",
    "产品",
    "运营",
    "用户",
    "增长",
]
TECH_KEYWORDS_LOWER = [keyword.lower() for keyword in TECH_KEYWORDS]

DEFAULT_DIMENSION_SCORES = {
    "content_relevance": 20,
    "professional_accuracy": 20,
    "clarity": 16,
    "star_completeness": 14,
    "position_match": 8,
}
DIMENSION_MAX = {
    "content_relevance": 25,
    "professional_accuracy": 25,
    "clarity": 20,
    "star_completeness": 20,
    "position_match": 10,
}

DIMENSION_CN_NAMES = {
    "content_relevance": "内容相关度",
    "professional_accuracy": "专业准确性",
    "clarity": "表达清晰度",
    "star_completeness": "STAR完整度",
    "position_match": "岗位匹配度",
}


def _llm_enabled() -> bool:
    return (
        settings.llm_provider.lower() not in {"", "mock", "none", "local"}
        and bool(settings.llm_api_key)
    )


def _get_client() -> Any:
    global _client
    if _client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed") from exc
        _client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=30.0,
        )
    return _client


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    if not _llm_enabled():
        raise RuntimeError("LLM provider is disabled")
    client = _get_client()
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def _safe_call_llm(
    system_prompt: str,
    user_prompt: str,
    fallback: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    if not _llm_enabled():
        return fallback
    try:
        return _call_llm(system_prompt, user_prompt, temperature, max_tokens)
    except Exception as exc:
        logger.warning("LLM call failed, using fallback: %s", exc)
        return fallback


def _parse_json_fallback(text: str) -> Any:
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        pass

    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text or "")
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text or "")
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _contains_tech_keywords(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in TECH_KEYWORDS_LOWER)


def _contains_quantifier(text: str) -> bool:
    return bool(re.search(r"\d+|百分之|提升|降低|减少|增加", text))


# 乱码/脏话判定已统一收敛到 AnswerQualityAgent（见 app/services/answer_quality.py）。
# judge_answer_quality() 返回结构化 verdict，规则 + LLM 双轨，并容忍少量人为输入错误。


# 空泛表达与夸大/绝对化表达词表，用于识别回答中的表达风险（需求 #15）。
VAGUE_PHRASES = [
    "一些", "比较好", "差不多", "还可以", "很多", "一定程度", "相关经验",
    "之类的", "等等", "大概", "可能吧", "应该可以", "还行", "挺好",
]
BIASED_PHRASES = [
    "唯一", "绝对", "完美", "100%", "完全", "肯定", "一定",
    "没有缺点", "精通一切", "无人能及", "天下第一",
]
# 注意：不使用“最/第一”等短词，避免误命中“最后/最初/第一轮”等正常表述。

# 题目要点覆盖规则。LLM 负责生成追问文本，规则层先兜住“是否答到题目问点”。
QUESTION_REQUIREMENT_RULES = [
    {
        "question_any": ["为什么", "感兴趣", "动机", "选择", "应聘"],
        "answer_any": [
            "因为", "感兴趣", "选择", "希望", "想", "适合", "喜欢",
            "发展", "成长", "方向", "动机", "规划", "目标",
        ],
        "hint": "说明你为什么对这个岗位或方向感兴趣",
    },
    {
        "question_all": ["价值"],
        "question_any": ["后端", "技术", "平台", "系统", "业务", "项目"],
        "answer_any": [
            "价值", "作用", "支撑", "稳定", "可靠", "安全", "效率",
            "自动化", "闭环", "基础", "核心", "复用", "扩展", "保障",
        ],
        "hint": "说明该岗位或技术在业务系统中的价值",
    },
    {
        "question_any": ["如何", "怎么", "实现", "设计", "方案", "流程", "优化", "排查"],
        "answer_any": [
            "使用", "通过", "设计", "实现", "流程", "接口", "数据库",
            "缓存", "日志", "测试", "优化", "指标", "分层", "封装",
        ],
        "hint": "补充具体技术动作、流程或实现细节",
    },
    {
        "question_any": ["结果", "效果", "成果", "提升", "优化", "量化", "指标"],
        "answer_any": [
            "%", "秒", "分钟", "次", "个", "降低", "提升", "减少",
            "增加", "覆盖", "响应时间", "通过率", "错误率",
        ],
        "hint": "补充可验证的结果或量化指标",
    },
]


def _detect_expression_risks(text: str) -> "tuple[List[str], List[str]]":
    """识别空泛表达与夸大/绝对化表达，返回 (vague_flags, biased_flags)。"""
    vague = [phrase for phrase in VAGUE_PHRASES if phrase in text]
    biased = [phrase for phrase in BIASED_PHRASES if phrase in text]
    return vague, biased


def _strip_markdown(text: str) -> str:
    """Remove Markdown formatting symbols so the output reads cleanly."""
    if not text:
        return text
    # bold / italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # headings
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # horizontal rules
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
    # inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # leading / trailing whitespace
    return text.strip()


# 面试官话术里的违禁表述（角色错乱 / 与实际流程矛盾）。
# - “面试到此为止/结束”：与实际流程矛盾（面试仍会继续到下一题）；
# - “我学不到东西/无法获得信息”：把面试官当成了学生，角色错乱。
_FORBIDDEN_INTERVIEWER_PHRASES = [
    "面试到此为止", "面试结束", "到此为止", "今天就到这", "面试终止", "结束面试", "面试就到这里",
    "我无法从中", "我学不到", "无法从中学到", "从中学不到", "学不到任何", "学不到东西",
    "无法获得任何", "没有可学习",
]


def _sanitize_interviewer_line(text: str) -> str:
    """清理面试官话术里的角色错乱 / 前后矛盾表述（LLM 输出护栏）。

    - 去掉句首“嗯/呃/额/啊”等无意义语气填充；
    - 删除含违禁表述的分句（如“面试到此为止”“我学不到东西”），保留其余正常内容。
    若清理后为空，返回空串，由调用方用中性话术兜底。
    """
    if not text:
        return ""
    cleaned = re.sub(r"^(嗯+|呃+|额+|啊+|哦+)[，,。\s]*", "", text.strip())
    parts = re.split(r"(?<=[。！？!?；;])", cleaned)
    kept = [
        part for part in parts
        if part.strip() and not any(ph in part for ph in _FORBIDDEN_INTERVIEWER_PHRASES)
    ]
    return "".join(kept).strip()


def _contains_any_keyword(text: str, keywords: List[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _question_matches_rule(question: str, rule: Dict[str, Any]) -> bool:
    lowered = question.lower()
    question_all = rule.get("question_all") or []
    question_any = rule.get("question_any") or []
    if question_all and not all(keyword.lower() in lowered for keyword in question_all):
        return False
    if question_any and not _contains_any_keyword(question, question_any):
        return False
    return bool(question_all or question_any)


def _missing_question_requirements(question: str, answer: str) -> List[str]:
    """Return hints for question requirements not covered by the answer."""
    missing: List[str] = []
    stripped_question = (question or "").strip()
    stripped_answer = (answer or "").strip()
    if not stripped_question or not stripped_answer:
        return missing

    for rule in QUESTION_REQUIREMENT_RULES:
        if not _question_matches_rule(stripped_question, rule):
            continue
        answer_keywords = rule.get("answer_any") or []
        if not _contains_any_keyword(stripped_answer, answer_keywords):
            hint = str(rule["hint"])
            if hint not in missing:
                missing.append(hint)
    return missing


def _join_feedback(existing: Any, extra: str, limit: int) -> str:
    existing_text = str(existing or "").strip("；; ")
    if existing_text:
        text = f"{existing_text}；{extra}"
    else:
        text = extra
    return _strip_markdown(text)[:limit]


def should_followup(answer: str, question: str = "") -> bool:
    stripped = answer.strip()
    if question and _missing_question_requirements(question, stripped):
        return True
    if len(stripped) < 50:
        return True
    if not _contains_tech_keywords(stripped):
        return True
    if "负责" in stripped and not _contains_quantifier(stripped):
        return True
    return False


def start_interview(
    resume_text: str,
    target_position: str = "",
    target_job_id: Optional[Union[int, str]] = None,
    interview_mode: str = DEFAULT_INTERVIEW_MODE,
) -> Dict[str, Any]:
    if interview_mode not in INTERVIEW_MODES:
        logger.warning("Unknown interview_mode %r, fallback to %s", interview_mode, DEFAULT_INTERVIEW_MODE)
        interview_mode = DEFAULT_INTERVIEW_MODE

    # 解析简历 / 岗位分析 / 生成题目 三个 LLM 调用并行，把“开始面试”从 2 轮串行降为 1 轮。
    # 出题不再等待 LLM 简历解析与岗位分析的结果：题面 LLM 会直接读 resume_text 原文与
    # 原始岗位资料（本地数据、零成本），技能提示用规则解析即可，问题质量不受影响。
    parsed_resume: Dict[str, Any] = {}
    job_requirements = ""
    rule_parsed = _parse_resume_by_rules(resume_text)
    raw_job_context = (
        get_position_job_summary(normalize_position(target_position), target_job_id)
        if target_position
        else ""
    )
    with ThreadPoolExecutor(max_workers=3) as _ex:
        f_parse = _ex.submit(_parse_resume, resume_text)
        f_job = (
            _ex.submit(_analyze_job_requirements, target_position, interview_mode, target_job_id)
            if target_position
            else None
        )
        f_questions = _ex.submit(
            _generate_questions,
            resume_text=resume_text,
            parsed_resume=rule_parsed,
            target_position=target_position,
            job_requirements=raw_job_context,
            interview_mode=interview_mode,
            job_id=target_job_id,
        )
        parsed_resume = f_parse.result()
        if f_job is not None:
            job_requirements = f_job.result()
        questions = f_questions.result()
    tools_used = ["resume_analyzer"]
    if target_position:
        tools_used.append("job_matcher")
    tools_used.append("question_generator")

    agent_state = {
        "version": 1,
        "session_uuid": str(uuid4()),
        "resume_excerpt": resume_text[:1000],
        "target_position": target_position,
        "target_job_id": str(target_job_id or ""),
        "interview_mode": interview_mode,
        "parsed_resume": parsed_resume,
        "job_requirements": job_requirements,
        "questions": questions,
        "current_index": 0,
        "answers": [{} for _ in questions],
        "status": "in_progress",
        "created_at": time.time(),
    }

    position_bucket = normalize_position(target_position) if target_position else ""
    return {
        "session_id": agent_state["session_uuid"],
        "interview_mode": interview_mode,
        "question": questions[0],
        "tools_used": tools_used,
        "total_questions": len(questions),
        "position_bucket": position_bucket,
        "agent_state": agent_state,
    }


def evaluate_answer(session_state: Dict[str, Any], answer: str) -> Dict[str, Any]:
    state = _ensure_state(session_state)
    questions = state["questions"]
    idx = int(state.get("current_index", 0))
    total = len(questions)

    if idx >= total:
        state["status"] = "ready_to_finish"
        return {
            "is_followup": False,
            "followup_question": None,
            "score": None,
            "feedback": "本轮题目已完成，可以结束面试生成报告。",
            "dimension_scores": None,
            "next_question": None,
            "current_index": total,
            "total_questions": total,
            "session_status": "ready_to_finish",
            "strengths": "",
            "issues": "",
            "improvement_suggestions": "",
            "agent_state": state,
        }

    slot = state["answers"][idx]
    first_answer = slot.get("first_answer")
    interview_mode = state.get("interview_mode", DEFAULT_INTERVIEW_MODE)

    if not first_answer:
        slot["first_answer"] = answer
        missing_requirements = _missing_question_requirements(questions[idx], answer)

        # LLM 不可用时走原串行路径（mock 零成本，行为与旧版一致，保证测试稳定）。
        if not _llm_enabled():
            return _evaluate_answer_legacy(state, idx, answer, missing_requirements)

        # LLM 可用：单次调用同时完成质量检定 + 五维评分 +（必要时）追问生成，
        # 把原来 judge→score / judge→followup 的 2 段串行往返压成 1 段往返（约 5–6 秒）。
        u = _unified_evaluate(
            question=questions[idx],
            answer=answer,
            target_position=state.get("target_position", ""),
            job_requirements=state.get("job_requirements", ""),
            interview_mode=interview_mode,
        )
        verdict = _verdict_from_unified(u, questions[idx], answer, state, interview_mode)
        is_invalid = verdict.category == "invalid_nonanswer"
        need_followup = (not is_invalid) and (
            bool(u.get("need_followup"))
            or bool(missing_requirements)
            or should_followup(answer, question=questions[idx])
        )
        if is_invalid:
            return _advance_with_unified(state, idx, answer, verdict, u)
        if need_followup:
            followup = (
                _sanitize_interviewer_line(str(u.get("followup_question") or ""))
                or _fallback_followup_text(questions[idx], answer, interview_mode, missing_requirements)
            )
            missing_text = "；".join(missing_requirements)
            feedback = (
                "回答与题目要点覆盖不足：%s。需要补充追问。" % missing_text
                if missing_requirements
                else "回答还不够具体，需要补充追问。"
            )
            return {
                "is_followup": True,
                "followup_question": followup,
                "score": None,
                "feedback": feedback,
                "dimension_scores": None,
                "next_question": followup,
                "current_index": idx,
                "total_questions": total,
                "session_status": "in_progress",
                "strengths": "",
                "issues": "",
                "improvement_suggestions": "",
                "llm_score": None,
                "rule_score": None,
                "vague_flags": [],
                "biased_flags": [],
                "agent_state": state,
            }
        # 有效且完整：单次调用内已产出五维评分，直接推进。
        return _advance_with_unified(state, idx, answer, verdict, u)

    slot["followup_answer"] = answer
    combined_answer = "第一轮回答：%s\n追问补充：%s" % (first_answer, answer)
    if not _llm_enabled():
        return _score_and_advance(state, idx, combined_answer)
    # 追问补充后评分：同样合并成单次 LLM 调用（质量检定 + 评分）。
    u = _unified_evaluate(
        question=questions[idx],
        answer=combined_answer,
        target_position=state.get("target_position", ""),
        job_requirements=state.get("job_requirements", ""),
        interview_mode=interview_mode,
    )
    verdict = _verdict_from_unified(u, questions[idx], combined_answer, state, interview_mode)
    return _advance_with_unified(state, idx, combined_answer, verdict, u)


def _evaluate_answer_legacy(state, idx, answer, missing_requirements):
    """LLM 禁用时使用的原串行路径：judge 与 score/followup 分别调用，行为与新版合并前一致。"""
    questions = state["questions"]
    total = len(questions)
    interview_mode = state.get("interview_mode", DEFAULT_INTERVIEW_MODE)
    _v = judge_answer_quality(
        questions[idx],
        answer,
        state.get("target_position", ""),
        state.get("job_requirements", ""),
        interview_mode,
    )
    _skip_followup = _v is not None and _v.category == "invalid_nonanswer"
    if _skip_followup:
        return _score_and_advance(state, idx, answer, _v)
    if should_followup(answer, question=questions[idx]):
        followup = _generate_followup(
            question=questions[idx],
            answer=answer,
            target_position=state.get("target_position", ""),
            interview_mode=interview_mode,
            missing_requirements=missing_requirements,
        )
        state["answers"][idx]["followup_question"] = followup
        if missing_requirements:
            feedback = "回答与题目要点覆盖不足：%s。需要补充追问。" % "；".join(missing_requirements)
        else:
            feedback = "回答还不够具体，需要补充追问。"
        return {
            "is_followup": True,
            "followup_question": followup,
            "score": None,
            "feedback": feedback,
            "dimension_scores": None,
            "next_question": followup,
            "current_index": idx,
            "total_questions": total,
            "session_status": "in_progress",
            "strengths": "",
            "issues": "",
            "improvement_suggestions": "",
            "agent_state": state,
        }
    return _score_and_advance(state, idx, answer, _v)


# ---------------------------------------------------------------------------
# 合并调用：单次 LLM 完成质量检定 + 五维评分 +（必要时）追问生成
# ---------------------------------------------------------------------------

_UNIFIED_SYSTEM = (
    "你是资深技术面试官，同时负责回答质量检定、评分与追问设计。"
    "严格只输出 JSON，不要输出任何其他文字或 Markdown 围栏。"
)


def _unified_evaluate(
    question: str,
    answer: str,
    target_position: str,
    job_requirements: str,
    interview_mode: str = DEFAULT_INTERVIEW_MODE,
) -> Dict[str, Any]:
    """单次 LLM 调用：质量检定 + 评分 +（必要时）追问生成，合并原两次串行调用。"""
    mode_scoring_hint = _mode_scoring_hint(interview_mode)
    mode_followup_tone = _mode_followup_tone(interview_mode)
    prompt = f"""面试模式：{interview_mode}
面试问题：{question}
候选人回答：{answer}
目标岗位：{target_position}
岗位要求参考：{job_requirements}

请完成两件事并严格输出 JSON：

一、质量检定
- gibberish：是否整体为无意义乱码/随机敲键（含真实语义内容则 false）
- abuse：是否含辱骂/脏话/纯粹非作答
- off_topic：是否明显跑题、完全没回应题目
- relevance：与题目的相关性（0~1）
- coherence：连贯度/合理性（0~1）
- signals：1~3 个中文质量信号（如“技术细节充分”“缺乏量化”“偏题”）

二、评分与追问（二者取其一）
- 若 gibberish/abuse 为 true：verdict="invalid_nonanswer"，need_followup=false，followup_question=null，五个维度给最低分，overall_comment 以面试官口吻指出这是无效作答、请就题作答。
- 若回答偏空泛/过短/漏答题目要点、需要补充：need_followup=true，给出 followup_question（一句自然追问，不超过 80 字）；五个维度可给粗略值、overall_comment 简短即可。
- 若回答有效且完整：need_followup=false，followup_question=null，给出完整五维评分与详细反馈。

{mode_scoring_hint}

评分维度（满分100）：
content_relevance 25 / professional_accuracy 25 / clarity 20 / star_completeness 20 / position_match 10

输出 JSON 结构：
{{
  "gibberish": true/false,
  "abuse": true/false,
  "off_topic": true/false,
  "relevance": 0.0,
  "coherence": 0.0,
  "signals": ["..."],
  "verdict": "valid|invalid_nonanswer|off_topic|low_quality",
  "need_followup": true/false,
  "followup_question": "..." 或 null,
  "content_relevance": 数字,
  "professional_accuracy": 数字,
  "clarity": 数字,
  "star_completeness": 数字,
  "position_match": 数字,
  "strengths": "优点（1-2句）",
  "issues": "存在问题（1-2句）",
  "improvement_suggestions": "改进建议（分号分隔）",
  "overall_comment": "真人面试官口吻的一句自然反应+简评"
}}

约束：
- followup_question / overall_comment 必须是真人面试官口吻，不出现“面试到此为止/结束”“我学不到东西”等矛盾表述；不堆砌“嗯/呃/额”等无意义语气词。
- 你是面试官，只评价候选人的回答本身。
{mode_followup_tone}"""
    fallback = {
        "gibberish": False,
        "abuse": False,
        "off_topic": False,
        "relevance": 0.5,
        "coherence": 0.5,
        "signals": [],
        "verdict": "valid",
        "need_followup": False,
        "followup_question": None,
        **DEFAULT_DIMENSION_SCORES,
        "strengths": "回答涉及了相关主题。",
        "issues": "缺少具体细节和量化数据。",
        "improvement_suggestions": "补充技术动作说明；加入量化成果；明确个人贡献。",
        "overall_comment": "回答较笼统，建议补充具体技术细节、个人贡献和量化结果。",
    }
    result = _safe_call_llm(
        system_prompt=_UNIFIED_SYSTEM,
        user_prompt=prompt,
        fallback=json.dumps(fallback, ensure_ascii=False),
        temperature=0.3,
        max_tokens=900,
    )
    parsed = _parse_json_fallback(result)
    return parsed if isinstance(parsed, dict) else fallback


def _verdict_from_unified(u, question, answer, state, interview_mode):
    gibberish = bool(u.get("gibberish"))
    abuse = bool(u.get("abuse"))
    off_topic = bool(u.get("off_topic"))
    category = str(u.get("verdict") or "valid")
    if category not in {"valid", "invalid_nonanswer", "off_topic", "low_quality"}:
        category = "valid"
    if gibberish or abuse:
        category = "invalid_nonanswer"
    return AnswerVerdict(
        valid=not (gibberish or abuse),
        category=category,
        gibberish=gibberish,
        abuse=abuse,
        relevance=float(u.get("relevance", 0.0)),
        coherence=float(u.get("coherence", 0.0)),
        noise_ratio=0.0,
        signals=list(u.get("signals", [])) or (["偏题"] if off_topic else []),
        confidence=0.9,
        llm_used=True,
    )


def _scores_from_unified(u, answer, question, verdict, interview_mode):
    """把合并调用的评分结果接入原后处理管线（惩罚/表达风险/漏答/校准），与 _score_answer 一致。"""
    scores = {}
    for key, max_score in DIMENSION_MAX.items():
        scores[key] = _clamp_score(u.get(key, DEFAULT_DIMENSION_SCORES[key]), max_score)
    scores["total"] = sum(scores[key] for key in DIMENSION_MAX)
    scores["strengths"] = _strip_markdown(str(u.get("strengths") or "回答涉及了相关主题。"))[:200]
    scores["issues"] = _strip_markdown(str(u.get("issues") or "缺少具体细节和量化数据。"))[:200]
    scores["improvement_suggestions"] = _strip_markdown(
        str(u.get("improvement_suggestions") or "补充技术动作说明；加入量化成果；明确个人贡献。")
    )[:300]
    overall = _strip_markdown(str(u.get("overall_comment") or "回答较笼统，建议补充具体技术细节。"))
    scores["overall_comment"] = _sanitize_interviewer_line(overall) or "回答较笼统，建议补充具体技术细节。"
    scores = _apply_invalid_penalty(scores, verdict)
    vague, biased = _detect_expression_risks(answer.strip())
    scores["vague_flags"] = vague
    scores["biased_flags"] = biased
    scores["missing_question_requirements"] = _missing_question_requirements(question, answer.strip())
    scores["total"] = sum(scores[key] for key in DIMENSION_MAX)
    base_total = sum(
        _clamp_score(u.get(key, DEFAULT_DIMENSION_SCORES[key]), DIMENSION_MAX[key])
        for key in DIMENSION_MAX
    )
    scores["llm_score"] = base_total
    rule_only = _apply_score_rules(dict(DEFAULT_DIMENSION_SCORES), answer.strip(), verdict)
    rule_only = _apply_question_relevance_rules(rule_only, question, answer.strip())
    scores["rule_score"] = rule_only["total"]
    return scores


def _advance_with_unified(state, idx, answer_text, verdict, u):
    questions = state["questions"]
    total = len(questions)
    interview_mode = state.get("interview_mode", DEFAULT_INTERVIEW_MODE)
    scores = _scores_from_unified(u, answer_text, questions[idx], verdict, interview_mode)
    state["answers"][idx]["scores"] = scores
    state["current_index"] = idx + 1
    if state["current_index"] >= total:
        state["status"] = "ready_to_finish"
        next_question = None
        session_status = "ready_to_finish"
    else:
        next_question = questions[state["current_index"]]
        session_status = "in_progress"
    feedback = scores.get("overall_comment", "")
    is_invalid = verdict.category == "invalid_nonanswer"
    if next_question and not is_invalid:
        feedback = random.choice(_TRANSITIONS) + feedback
    return {
        "is_followup": False,
        "followup_question": None,
        "score": scores["total"],
        "feedback": feedback,
        "strengths": scores.get("strengths", ""),
        "issues": scores.get("issues", ""),
        "improvement_suggestions": scores.get("improvement_suggestions", ""),
        "llm_score": scores.get("llm_score"),
        "rule_score": scores.get("rule_score"),
        "vague_flags": scores.get("vague_flags", []),
        "biased_flags": scores.get("biased_flags", []),
        "dimension_scores": scores,
        "next_question": next_question,
        "current_index": state["current_index"],
        "total_questions": total,
        "session_status": session_status,
        "agent_state": state,
    }


def _fallback_followup_text(question, answer, interview_mode, missing_requirements):
    missing_text = "；".join(missing_requirements or [])
    if missing_text:
        return random.choice(_FOLLOWUP_MISSING_FALLBACKS).format(points=missing_text)
    return random.choice(_FOLLOWUP_FALLBACKS)


def finish_interview(
    session_state: Dict[str, Any],
    session_id: Union[int, str],
) -> Dict[str, Any]:
    state = _ensure_state(session_state)
    existing_report = state.get("completed_report")
    if isinstance(existing_report, dict):
        existing_report["session_id"] = str(session_id)
        return existing_report

    scored = _scored_answer_details(state)
    scored_sorted = sorted(scored, key=lambda item: item["scores"].get("total", 0))
    weakest_answers = scored_sorted[:3]

    star_suggestions = []
    for item in weakest_answers:
        answer = item.get("followup_answer") or item.get("first_answer", "")
        if not answer:
            continue
        star_rewrite = _rewrite_star(
            question=item["question"],
            answer=answer,
            target_position=state.get("target_position", ""),
        )
        item["star_rewrite"] = star_rewrite
        star_suggestions.append(
            {
                "question": item["question"],
                "star_rewrite": star_rewrite,
            }
        )

    dimension_averages = _dimension_averages(scored)
    total_score = sum(item["scores"].get("total", 0) for item in scored)
    overall_score = round(total_score / len(scored), 1) if scored else 0
    interview_mode = state.get("interview_mode", DEFAULT_INTERVIEW_MODE)
    practice_plan = _generate_practice_plan(
        dimension_averages=dimension_averages,
        weak_questions=[item["question"] for item in weakest_answers],
        target_position=state.get("target_position", ""),
        interview_mode=interview_mode,
    )

    report = {
        "session_id": str(session_id),
        "interview_mode": interview_mode,
        "overall_score": overall_score,
        "dimension_averages": dimension_averages,
        "total_questions_answered": len(scored),
        "details": scored,
        "star_suggestions": star_suggestions,
        "practice_plan": practice_plan,
        "summary": _generate_summary(overall_score, dimension_averages, interview_mode),
        "question_bank_summary": get_question_bank_summary(),
        "calibration_summary": _build_calibration_summary(scored),
    }
    state["status"] = "completed"
    state["completed_report"] = report
    return report


def _ensure_state(state: Dict[str, Any]) -> Dict[str, Any]:
    interview_mode = state.get("interview_mode", DEFAULT_INTERVIEW_MODE)
    if interview_mode not in INTERVIEW_MODES:
        interview_mode = DEFAULT_INTERVIEW_MODE
    state["interview_mode"] = interview_mode
    questions = state.get("questions")
    if not isinstance(questions, list) or not questions:
        questions = _default_questions(state.get("target_position", ""), interview_mode)
        state["questions"] = questions
    answers = state.get("answers")
    if not isinstance(answers, list):
        answers = []
    while len(answers) < len(questions):
        answers.append({})
    state["answers"] = answers[: len(questions)]
    state["current_index"] = max(0, min(int(state.get("current_index", 0)), len(questions)))
    state.setdefault("status", "in_progress")
    return state


def _score_and_advance(state: Dict[str, Any], idx: int, answer_text: str, verdict=None) -> Dict[str, Any]:
    questions = state["questions"]
    total = len(questions)
    interview_mode = state.get("interview_mode", DEFAULT_INTERVIEW_MODE)

    scores = _score_answer(
        question=questions[idx],
        answer=answer_text,
        target_position=state.get("target_position", ""),
        job_requirements=state.get("job_requirements", ""),
        interview_mode=interview_mode,
        verdict=verdict,
    )
    state["answers"][idx]["scores"] = scores
    state["current_index"] = idx + 1

    if state["current_index"] >= total:
        state["status"] = "ready_to_finish"
        next_question = None
        session_status = "ready_to_finish"
    else:
        next_question = questions[state["current_index"]]
        session_status = "in_progress"

    # 过渡到下一题的真人感话术（仅对有效作答；无效作答直接用“对应反馈”）。
    feedback = scores.get("overall_comment", "")
    is_invalid = verdict is not None and verdict.category == "invalid_nonanswer"
    if next_question and not is_invalid:
        feedback = random.choice(_TRANSITIONS) + feedback

    return {
        "is_followup": False,
        "followup_question": None,
        "score": scores["total"],
        "feedback": feedback,
        "strengths": scores.get("strengths", ""),
        "issues": scores.get("issues", ""),
        "improvement_suggestions": scores.get("improvement_suggestions", ""),
        "llm_score": scores.get("llm_score"),
        "rule_score": scores.get("rule_score"),
        "vague_flags": scores.get("vague_flags", []),
        "biased_flags": scores.get("biased_flags", []),
        "dimension_scores": scores,
        "next_question": next_question,
        "current_index": state["current_index"],
        "total_questions": total,
        "session_status": session_status,
        "agent_state": state,
    }


def _parse_resume(resume_text: str) -> Dict[str, Any]:
    prompt = f"""请解析以下简历，提取结构化信息。

简历文本：
{resume_text[:4000]}

请只输出 JSON：
{{
  "education": "最高学历",
  "skills": ["技能1", "技能2"],
  "projects": [{{"name": "项目名", "role": "角色", "tech": ["技术"], "result": "成果"}}],
  "experience": [{{"company": "公司", "position": "职位", "duration": "时长"}}],
  "strengths": ["优势1"],
  "weaknesses": ["不足1"]
}}
"""
    fallback = json.dumps(_parse_resume_by_rules(resume_text), ensure_ascii=False)
    result = _safe_call_llm(
        system_prompt="你是简历解析专家。只输出 JSON，不要任何其他文字。",
        user_prompt=prompt,
        fallback=fallback,
        temperature=0.3,
    )
    parsed = _parse_json_fallback(result)
    return parsed if isinstance(parsed, dict) else _parse_resume_by_rules(resume_text)


def _parse_resume_by_rules(resume_text: str) -> Dict[str, Any]:
    skills = []
    lowered = resume_text.lower()
    for keyword in TECH_KEYWORDS:
        if keyword.lower() in lowered and keyword not in skills:
            skills.append(keyword)
    return {
        "education": "",
        "skills": skills[:12],
        "projects": [],
        "experience": [],
        "strengths": skills[:5],
        "weaknesses": [],
    }


def _analyze_job_requirements(
    target_position: str,
    interview_mode: str = DEFAULT_INTERVIEW_MODE,
    job_id: Optional[Union[int, str]] = None,
) -> str:
    mode_hint = _mode_analysis_hint(interview_mode)
    position_bucket = normalize_position(target_position)
    real_summary = get_position_job_summary(position_bucket, job_id)
    prompt = f"""目标岗位：{target_position}
面试模式：{interview_mode}

真实岗位资料（来自岗位库）：
{real_summary}

请用 3-5 句话总结这个岗位在{interview_mode}中的核心关注点、常见面试重点和典型工作场景，需结合上面的真实职责与要求。
{mode_hint}"""
    fallback = (
        f"{target_position} 岗位通常关注技术基础、项目落地能力、沟通协作和问题排查能力。\n"
        f"【真实岗位参考】{real_summary}"
    )
    return _safe_call_llm(
        system_prompt="你是资深技术面试官，熟悉各岗位的 JD 和面试要点。",
        user_prompt=prompt,
        fallback=fallback,
        temperature=0.5,
    )


# 真实岗位职责题的多样化模板（轮换使用，避免每题同一句式——这是“问题都一样”的根因）。
_RESP_TEMPLATES = [
    "结合你过往项目，聊聊你在「{r}」上的实际经验，最好有量化成果。",
    "简历里如果做过「{r}」相关的事，能具体讲讲过程和结果吗？",
    "假如让你负责「{r}」这样的工作，你会怎么入手？说个类似经历。",
    "「{r}」这类任务你之前踩过什么坑、怎么解决的？分享一次真实经历。",
    "关于「{r}」，你最有成就感的一次实践是什么？怎么做的、效果如何？",
]


def _grounded_questions(responsibilities: List[str], max_n: int = 4) -> List[str]:
    """把真实职责转成多样化的问题（轮换模板，避免雷同）。"""
    out: List[str] = []
    for i, resp in enumerate(responsibilities or []):
        resp = (resp or "").strip()
        if not resp:
            continue
        template = _RESP_TEMPLATES[i % len(_RESP_TEMPLATES)]
        out.append(template.format(r=resp[:50]))
        if len(out) >= max_n:
            break
    return out


def _build_question_pool(
    opening: str,
    grounded: List[str],
    bank: List[str],
    others: List[str],
    max_n: int = 8,
) -> List[str]:
    """汇总开场题、真实职责题、题库题、其它默认题，去重后取前 max_n 道。

    顺序：开场题 → 交错穿插职责题与题库题 → 其它默认题补足，保证既有针对性又不重复。
    """
    pool: List[str] = []
    seen: set = set()

    def _push(q: str) -> None:
        q = (q or "").strip()
        if q and q not in seen and len(pool) < max_n:
            seen.add(q)
            pool.append(q)

    if opening:
        _push(opening)
    # 交错穿插职责题与题库题，提升多样性
    max_len = max(len(grounded), len(bank))
    for i in range(max_len):
        if i < len(grounded):
            _push(grounded[i])
        if i < len(bank):
            _push(bank[i])
    for q in others:
        _push(q)
    return pool[:max_n]


def _generate_questions(
    resume_text: str,
    parsed_resume: Dict[str, Any],
    target_position: str,
    job_requirements: str,
    interview_mode: str = DEFAULT_INTERVIEW_MODE,
    job_id: Optional[Union[int, str]] = None,
) -> List[str]:
    skills_text = "、".join(parsed_resume.get("skills", [])) or "通用技能"
    projects_text = json.dumps(parsed_resume.get("projects", []), ensure_ascii=False)
    position = target_position or "目标岗位"
    default_questions = _default_questions(position, interview_mode)

    position_bucket = normalize_position(target_position)
    real_resp = get_position_responsibilities(position_bucket, job_id)
    # 真实职责题：多样化模板（最多 4 道），不再是同一句式
    grounded = _grounded_questions(real_resp[:4], max_n=4)
    # 岗位+模式题库题：直接用数据（“不是有数据吗”）
    bank = [q for q in get_position_question_pool(position, interview_mode) if q]

    opening = default_questions[0] if default_questions else "请先做一个简短的自我介绍。"
    # 兜底题池：开场 + 多样化职责题 + 题库题 + 其余默认题
    fallback_questions = _build_question_pool(
        opening=opening,
        grounded=grounded,
        bank=bank,
        others=default_questions[1:],
        max_n=8,
    )
    allocation, mode_instruction = _mode_question_allocation(interview_mode)

    # 给 LLM 提供题库参考，要求生成互不重复、风格多样的题目
    bank_reference = "；".join(bank[:6]) if bank else "（无）"
    prompt = f"""请为以下候选人生成 8 道面试题，严格按类别分配：

面试模式：{interview_mode}
候选人背景：
- 技能：{skills_text}
- 项目经历：{projects_text}
- 简历原文：{resume_text[:1000]}

目标岗位：{position}
岗位要求：{job_requirements}
真实岗位职责参考：{("；".join(real_resp[:4]) if real_resp else "（无）")}
题库参考（可改写/扩展，但不要逐字照搬全部）：{bank_reference}

题目分配：
{allocation}

{mode_instruction}

要求：每道题的切入点与表述都要不同，避免重复与模板化；首题适合做开场。
只输出 JSON 数组，例如 ["题目1", "题目2"]。
"""
    result = _safe_call_llm(
        system_prompt=f"你是{interview_mode}的资深面试官，出题要多样、有针对性。只输出 JSON 数组。",
        user_prompt=prompt,
        fallback=json.dumps(fallback_questions, ensure_ascii=False),
        temperature=0.9,
    )
    parsed = _parse_json_fallback(result)
    questions = [str(item).strip() for item in parsed] if isinstance(parsed, list) else []
    questions = [question for question in questions if question]
    if not questions:
        return fallback_questions[:8]
    # 去重 + 保证首题是开场题，不足用兜底题池补全
    final: List[str] = []
    seen: set = set()
    if opening:
        final.append(opening)
        seen.add(opening)
    for q in questions:
        if q not in seen and len(final) < 8:
            seen.add(q)
            final.append(q)
    for q in fallback_questions:
        if len(final) >= 8:
            break
        if q not in seen:
            seen.add(q)
            final.append(q)
    return final[:8]


def _mode_analysis_hint(interview_mode: str) -> str:
    hints = {
        "HR面": "侧重软技能、文化匹配和职业素养评估。",
        "技术面": "侧重技术深度、项目经验和问题解决能力。",
        "压力面": "侧重抗压能力、临场反应和真实水平暴露。",
        "反馈教练": "侧重当前水平摸底，以便给出针对性提升建议。",
    }
    return hints.get(interview_mode, "")


def _mode_question_allocation(interview_mode: str):
    allocations = {
        "HR面": (
            "1-2 题：自我介绍与职业规划\n"
            "3-4 题：团队协作与沟通\n"
            "5-6 题：价值观与文化匹配\n"
            "7 题：抗压与情绪管理\n"
            "8 题：情景模拟",
            "题目应聚焦软技能、团队合作、职业规划和价值观。",
        ),
        "技术面": (
            "1-2 题：自我介绍与动机类\n"
            "3-5 题：项目经历深挖类\n"
            "6-7 题：技术基础类\n"
            "8 题：行为问题类",
            "题目应聚焦技术深度、项目落地能力和问题排查思路。",
        ),
        "压力面": (
            "1-2 题：自我认知与短板\n"
            "3-4 题：失败经历深挖\n"
            "5-6 题：高压场景模拟\n"
            "7 题：极限挑战\n"
            "8 题：自我辩护",
            "题目应有挑战性和压迫感，测试候选人在压力下的真实反应。",
        ),
        "反馈教练": (
            "1-2 题：自我认知与目标\n"
            "3-4 题：项目复盘\n"
            "5-6 题：技能自评\n"
            "7 题：STAR结构化练习\n"
            "8 题：自我提升计划",
            "题目应温和且有引导性，帮助候选人发现提升空间。",
        ),
    }
    return allocations.get(interview_mode, allocations["技术面"])


def _mode_followup_tone(interview_mode: str) -> str:
    tones = {
        "HR面": "请友好地引导对方补充更多具体事例和真实感受。",
        "技术面": "请引导对方补充具体技术动作、量化结果和个人贡献。",
        "压力面": "请用尖锐的角度追问，测试对方在压力下的真实水平。",
        "反馈教练": "请用鼓励的语气引导对方补充细节，为后续建议做准备。",
    }
    return tones.get(interview_mode, "请引导对方补充具体技术动作、量化结果和个人贡献。")


def _mode_scoring_hint(interview_mode: str) -> str:
    hints = {
        "HR面": "评分时侧重沟通表达、价值观匹配和团队意识，技术维度适当降低权重。",
        "技术面": "评分时侧重技术深度、方案可行性和项目落地能力。",
        "压力面": "评分时侧重抗压表现、逻辑清晰度和临场反应，回答本身可能不完美但能体现真实水平。",
        "反馈教练": "评分后要以鼓励为主，问题描述温和，改进建议要具体可执行。",
    }
    return hints.get(interview_mode, "")


def _default_questions(position: str = "", interview_mode: str = DEFAULT_INTERVIEW_MODE) -> List[str]:
    target = position or "目标岗位"
    position_questions = get_position_question_pool(position, interview_mode)
    if position_questions:
        return position_questions[:8]
    mode_questions = {
        "HR面": [
            "请做一个简短的自我介绍，重点说明你的职业规划和个人优势。",
            "你为什么选择应聘%s？你对公司的了解是什么？" % target,
            "请描述一次你与他人发生分歧的经历，你是如何处理的？",
            "你未来的3-5年职业规划是什么？",
            "你觉得团队合作中最重要的因素是什么？为什么？",
            "请分享一次你主动承担责任超出职责范围的经历。",
            "你是如何平衡工作与个人成长的？",
            "如果进入公司后发现实际工作与预期不符，你会怎么做？",
        ],
        "技术面": [
            "请做一个简短的自我介绍，并说明你与%s最匹配的优势。" % target,
            "你为什么选择应聘%s？" % target,
            "请详细描述一个你主导或深度参与的项目。",
            "这个项目中最困难的问题是什么，你是怎样定位和解决的？",
            "你如何保证项目代码质量、接口稳定性或交付质量？",
            "你对%s所需的核心技术栈了解多少？" % target,
            "如果系统上线后出现性能问题，你会如何排查并优化？",
            "请分享一次团队协作中出现分歧时你的处理方式。",
        ],
        "压力面": [
            "请用三句话证明你比其他人更适合%s这个岗位。" % target,
            "你简历里提到的最成功项目，如果重来一次你会在哪些环节改进？",
            "你的技术方案被 leader 否决过吗？具体是怎么处理的？",
            "说说你最近一次技术决策失误，带来了什么后果？",
            "你觉得自己最薄弱的技术环节是什么？凭什么让我们录用你？",
            "如果给你一个不熟悉的领域，deadline 只有一周，你怎么交付？",
            "你认为自己过去一年技术上最大的退步是什么？",
            "如果明天就要你独立负责整个%s系统，你敢接吗？为什么？" % target,
        ],
        "反馈教练": [
            "请做一个自我介绍，我会在你回答后给出优化建议。",
            "说说你最有成就感的一个项目经历。",
            "描述一下你日常的工作流程和学习习惯。",
            "你在团队中通常扮演什么角色？举例说明。",
            "你有没有遇到过特别沮丧的项目经历？",
            "你对%s的技能准备程度如何？哪方面还需要加强？" % target,
            "请用STAR法则描述一个你解决技术难题的案例。",
            "你对这次练习有什么特别想提升的方面？",
        ],
    }
    return mode_questions.get(interview_mode, mode_questions["技术面"])


# 追问兜底话术池（随机选取，避免每次雷同；仅在 LLM 不可用时使用）。
_FOLLOWUP_FALLBACKS = [
    "能具体说说你用了什么技术、承担了哪部分工作，最后取得了什么成果吗？",
    "可以再展开一点吗？比如你在其中的角色、关键动作和可量化的结果。",
    "我想多了解一些细节——这个过程中你具体做了什么、效果如何？",
    "能举个例子说明一下吗？最好带一点数据或最终结果。",
    "听起来方向对，但还不够落地。能讲讲你具体是怎么做的吗？",
]

# 漏答要点的兜底话术池。
_FOLLOWUP_MISSING_FALLBACKS = [
    "你刚才的回答还没回应到{points}，能补充一下吗？",
    "这一点——{points}——你好像没展开，能具体说说吗？",
    "关于{points}，我还想听你多讲讲。",
]


def _generate_followup(
    question: str,
    answer: str,
    target_position: str,
    interview_mode: str = DEFAULT_INTERVIEW_MODE,
    missing_requirements: Optional[List[str]] = None,
) -> str:
    tone = _mode_followup_tone(interview_mode)
    missing_text = "；".join(missing_requirements or [])
    if missing_text:
        focus_line = f"候选人漏答的题目要点：{missing_text}\n请优先围绕这些漏答点追问。"
        fallback = random.choice(_FOLLOWUP_MISSING_FALLBACKS).format(points=missing_text)
    else:
        focus_line = "候选人的回答不够具体。"
        fallback = random.choice(_FOLLOWUP_FALLBACKS)
    prompt = f"""你是一位{interview_mode}的真人面试官，正在与候选人对话。
原问题：{question}
候选人回答：{answer}
目标岗位：{target_position}

{focus_line}{tone}
请用自然、口语化但专业的语气提出一句追问，像真人在对话中追问一样，不要客套模板、不要每次都一样。
注意：你是面试官，只引导候选人补充，不要评价自己能否学到东西，也不要说“面试到此为止/结束”；
不要堆砌“嗯/呃/额”等无意义语气词。
只输出追问本身，不超过 80 字。"""
    followup = _safe_call_llm(
        system_prompt=f"你是{interview_mode}的真人面试官，追问要自然、口语化、每次切入角度不同，且专业、尊重人。{tone}",
        user_prompt=prompt,
        fallback=fallback,
        temperature=0.9,
        max_tokens=256,
    )
    # 护栏：清理可能的角色错乱/矛盾表述或句首语气填充；被清空则用兜底话术。
    return _sanitize_interviewer_line(followup) or fallback


def _build_mock_feedback(answer: str, scores: Dict[str, Any], verdict=None) -> Dict[str, str]:
    """mock 模式下基于 AnswerQualityAgent 的 verdict 生成内容相关反馈（替代固定 canned 模板）。

    仅在 LLM 未启用时使用。乱码/脏话/无实质内容按“对应反馈”生成，且用多套措辞
    避免每次雷同；无效回答不再复用“缺少具体细节/量化数据”这类面向有效作答的建议。
    """
    stripped = (answer or "").strip()
    # 非作答：verdict 优先，兜底看 vague_flags；
    # mock 无语义判定时，极短/无实质内容（<10 字，如“萨达萨达”）也按“无意义”给反馈。
    is_invalid = (
        (verdict is not None and verdict.category == "invalid_nonanswer")
        or any(
            f in (scores.get("vague_flags") or [])
            for f in ("无意义/乱码", "不当内容/非作答")
        )
        or (not _llm_enabled() and len(stripped) < 10)
    )
    if is_invalid:
        # 对应反馈：脏话 vs 乱码分别处理；用多套措辞避免每次雷同。
        # 关键点：无效回答不再复用“缺少具体细节/量化数据”这类面向有效作答的建议，
        # 否则会自相矛盾（乱码谈不上“补充技术动作”）。
        if verdict is not None and verdict.abuse:
            comment = random.choice([
                "回答包含不当内容或完全没有实质内容，本次不计分。",
                "检测到脏话或纯粹敷衍，无法作为有效作答，本次记为不及格。",
                "回答不符合面试基本要求（含不当内容或非作答），请重新就题目作答。",
            ])
            issues = "含不当内容，或仅为敷衍、非作答。"
            suggest = "请围绕题目给出真实、具体的回答，避免脏话与无意义灌水。"
        else:
            comment = random.choice([
                "回答内容无意义或疑似乱码，无法评估实质内容。",
                "未检测到有效作答内容，疑似随机输入或乱码，本次不计分。",
                "回答缺乏可理解的内容，无法判断与题目的相关性，记为不及格。",
            ])
            issues = "回答内容无意义或疑似乱码，无法评估实质内容。"
            suggest = "请就题目给出真实、可理解的回答，避免使用无意义的随机输入。"
        return {
            "strengths": "—",
            "overall_comment": comment[:160],
            "issues": issues[:200],
            "improvement_suggestions": suggest[:300],
        }

    strengths_parts: List[str] = []
    issues_parts: List[str] = []
    suggest_parts: List[str] = []

    if _contains_tech_keywords(stripped):
        strengths_parts.append("回答覆盖了具体技术栈与技术动作")
    if _contains_quantifier(stripped):
        strengths_parts.append("给出了量化成果")
    if len(stripped) >= 50:
        strengths_parts.append("内容较充实、结构清晰")
    if verdict is not None and verdict.relevance >= 0.6:
        strengths_parts.append("回答切题、与岗位要求匹配")

    if not _contains_tech_keywords(stripped):
        issues_parts.append("缺少具体技术细节")
        suggest_parts.append("补充技术动作说明")
    if not _contains_quantifier(stripped):
        issues_parts.append("缺少量化数据")
        suggest_parts.append("加入量化成果")
    if len(stripped) < 20:
        issues_parts.append("回答过短")
        suggest_parts.append("适当展开说明")
    if scores.get("missing_question_requirements"):
        issues_parts.append(
            "漏答题目要点：" + "；".join(scores["missing_question_requirements"])
        )
        suggest_parts.append("先逐项回应题目要求")
    if verdict is not None:
        if verdict.category == "off_topic":
            issues_parts.append("回答与题目关联较弱，疑似跑题")
            suggest_parts.append("紧扣问题核心作答")
        elif verdict.category == "low_quality" and verdict.coherence < 0.35:
            issues_parts.append("回答偏空泛，缺少实质内容")
            suggest_parts.append("用具体事例与数据充实回答")

    if not strengths_parts:
        strengths_parts.append("回答涉及了相关主题")
    if not issues_parts:
        issues_parts.append("整体回答较具体，可继续深化个人贡献描述")
    if not suggest_parts:
        suggest_parts.append("继续用量化数据与 STAR 结构强化个人贡献")

    overall = "回答较具体、贴合岗位要求。" if len(strengths_parts) >= 2 else "涉及了相关主题，可进一步具体化。"
    return {
        "strengths": "；".join(strengths_parts)[:200],
        "issues": "；".join(issues_parts)[:200],
        "improvement_suggestions": "；".join(suggest_parts)[:300],
        "overall_comment": overall[:160],
    }


def _score_answer(
    question: str,
    answer: str,
    target_position: str,
    job_requirements: str,
    interview_mode: str = DEFAULT_INTERVIEW_MODE,
    verdict=None,
) -> Dict[str, Any]:
    mode_scoring_hint = _mode_scoring_hint(interview_mode)
    prompt = f"""请对以下面试回答进行评分。

面试模式：{interview_mode}
面试问题：{question}
候选人回答：{answer}
目标岗位：{target_position}
岗位要求参考：{job_requirements}

评分维度（满分100）：
1. content_relevance：25 分
2. professional_accuracy：25 分
3. clarity：20 分
4. star_completeness：20 分
5. position_match：10 分

{mode_scoring_hint}

请严格输出 JSON：
{{
  "content_relevance": 数字,
  "professional_accuracy": 数字,
  "clarity": 数字,
  "star_completeness": 数字,
  "position_match": 数字,
  "strengths": "回答的优点（1-2句）",
  "issues": "存在的问题（1-2句）",
  "improvement_suggestions": "改进建议（1-3条，每条用分号分隔）",
  "overall_comment": "以真人面试官口吻给出的一句自然反应+简评（切入角度随回答内容变化，不套话、不雷同）"
}}

overall_comment 必须遵守：
- 你是面试官，只评价候选人的回答本身；不要说“我从中学不到东西”“无法获得任何信息”这类把自己当学生的话；
- 即使回答很差，也只指出问题并要求对方就题作答，不要宣布“面试到此为止”“面试结束”“今天就到这里”——面试还会继续；
- 语气专业、尊重人，不堆砌“嗯/呃/额”等无意义语气词。
"""
    fallback = {
        **DEFAULT_DIMENSION_SCORES,
        "overall_comment": "回答较笼统，建议补充具体技术细节、个人贡献和量化结果。",
        "strengths": "回答涉及了相关主题。",
        "issues": "缺少具体细节和量化数据。",
        "improvement_suggestions": "补充技术动作说明；加入量化成果；明确个人贡献。",
    }
    result = _safe_call_llm(
        system_prompt=f"你是{interview_mode}的严格但公正的面试官。只输出 JSON，不要其他内容。",
        user_prompt=prompt,
        fallback=json.dumps(fallback, ensure_ascii=False),
        temperature=0.3,
        max_tokens=700,
    )
    parsed = _parse_json_fallback(result)
    raw_scores = parsed if isinstance(parsed, dict) else fallback

    scores: Dict[str, Any] = {}
    for key, max_score in DIMENSION_MAX.items():
        scores[key] = _clamp_score(raw_scores.get(key, fallback.get(key, 0)), max_score)
    scores["total"] = sum(scores[key] for key in DIMENSION_MAX)
    scores["strengths"] = _strip_markdown(
        str(raw_scores.get("strengths") or fallback["strengths"])
    )[:200]
    scores["issues"] = _strip_markdown(
        str(raw_scores.get("issues") or fallback["issues"])
    )[:200]
    scores["improvement_suggestions"] = _strip_markdown(
        str(raw_scores.get("improvement_suggestions") or fallback["improvement_suggestions"])
    )[:300]
    scores["overall_comment"] = _strip_markdown(
        str(raw_scores.get("overall_comment") or fallback["overall_comment"])
    )[:160]
    # 护栏：清理角色错乱/前后矛盾表述（如“我学不到东西”“面试到此为止”）；被清空则回退到中性兜底。
    scores["overall_comment"] = (
        _sanitize_interviewer_line(scores["overall_comment"]) or fallback["overall_comment"]
    )

    # 先用 AnswerQualityAgent 对回答做质量检定（乱码/脏话/相关性/合理性）。
    # 乱码/脏话/跑题等语义判定已由 LLM 主导；规则仅做基础兜底。
    if verdict is None:
        verdict = judge_answer_quality(question, answer, target_position, job_requirements, interview_mode)

    # 质量检定（乱码/脏话/相关性/合理性）由 LLM 主导；mock 下走规则兜底。
    if _llm_enabled():
        # 加大 AI 权重（别写死规则兜底）：维度分与反馈文本都来自 LLM，规则不再盖帽/覆盖。
        # 仅保留“无效作答（乱码/脏话）”强惩罚，确保瞎说/脏话给到低分；
        # 空泛/夸大/漏答仅作为元数据（flags）供报告展示，不再改分或覆盖反馈。
        scores = _apply_invalid_penalty(scores, verdict)
        vague, biased = _detect_expression_risks(answer.strip())
        scores["vague_flags"] = vague
        scores["biased_flags"] = biased
        scores["missing_question_requirements"] = _missing_question_requirements(question, answer.strip())
        scores["total"] = sum(scores[key] for key in DIMENSION_MAX)
    else:
        # mock 兜底：长度底线 + 脏话清零 + 漏答盖帽 + 内容相关反馈。
        scores = _apply_score_rules(scores, answer.strip(), verdict)
        scores = _apply_question_relevance_rules(scores, question, answer.strip())
        mock_fb = _build_mock_feedback(answer, scores, verdict)
        for _k in ("strengths", "issues", "improvement_suggestions", "overall_comment"):
            if _k in mock_fb:
                scores[_k] = mock_fb[_k]

    # 评分校准（进阶 #2）：对照 Agent(LLM) 评分与纯规则评分，辅助评估 Agent 稳定性。
    base_total = sum(
        _clamp_score(raw_scores.get(key, fallback.get(key, 0)), DIMENSION_MAX[key])
        for key in DIMENSION_MAX
    )
    scores["llm_score"] = base_total if _llm_enabled() else None
    rule_only = _apply_score_rules(dict(DEFAULT_DIMENSION_SCORES), answer.strip(), verdict)
    rule_only = _apply_question_relevance_rules(rule_only, question, answer.strip())
    scores["rule_score"] = rule_only["total"]
    return scores


def _clamp_score(value: Any, max_score: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = 0
    return max(0, min(max_score, number))


def _apply_invalid_penalty(scores: Dict[str, Any], verdict=None) -> Dict[str, Any]:
    """对无效作答（乱码/脏话）施加强惩罚：LLM 模式下维度分清零，确保瞎说/脏话给到低分。

    只压分数，不改反馈文本——反馈由 LLM 生成（“对应反馈”，不死板）。
    """
    corrected = dict(scores)
    if verdict is not None and verdict.category == "invalid_nonanswer":
        corrected["content_relevance"] = 0
        corrected["professional_accuracy"] = 0
        corrected["clarity"] = 1
        corrected["star_completeness"] = 0
        corrected["position_match"] = 1
    corrected["total"] = sum(corrected[key] for key in DIMENSION_MAX)
    return corrected


def _apply_score_rules(scores: Dict[str, Any], answer: str, verdict=None) -> Dict[str, Any]:
    """基于规则对评分做兜底修正，并识别表达风险（需求 #15）。

    返回的分数字典会带上 vague_flags / biased_flags，便于结构化反馈与评分校准。
    """
    corrected = dict(scores)
    stripped = answer.strip()
    if len(stripped) < 20:
        corrected["content_relevance"] = min(corrected["content_relevance"], 10)
    if len(stripped) < 50:
        corrected["star_completeness"] = min(corrected["star_completeness"], 10)
    if not _contains_tech_keywords(stripped):
        corrected["professional_accuracy"] = min(corrected["professional_accuracy"], 10)
    if not _contains_quantifier(stripped):
        corrected["star_completeness"] = min(corrected["star_completeness"], 12)

    # 表达风险识别：空泛表达 -> 降表达清晰度；夸大/绝对化 -> 降专业准确性。
    vague, biased = _detect_expression_risks(stripped)
    if vague:
        corrected["clarity"] = min(corrected["clarity"], 10)
        flag_text = "、".join(vague)
        issues = corrected.get("issues", "") or ""
        corrected["issues"] = _strip_markdown(
            (issues + f"；回答存在空泛表达（如：{flag_text}），缺少具体信息")[:200]
        )
        suggestion = corrected.get("improvement_suggestions", "") or ""
        corrected["improvement_suggestions"] = _strip_markdown(
            (suggestion + "；用 STAR 补充具体动作与量化结果，避免空泛词")[:300]
        )
    if biased:
        corrected["professional_accuracy"] = min(corrected["professional_accuracy"], 10)
        flag_text = "、".join(biased)
        issues = corrected.get("issues", "") or ""
        corrected["issues"] = _strip_markdown(
            (issues + f"；存在夸大/绝对化表达（如：{flag_text}），易引发质疑")[:200]
        )
        suggestion = corrected.get("improvement_suggestions", "") or ""
        corrected["improvement_suggestions"] = _strip_markdown(
            (suggestion + "；用可验证事实替代绝对化表述")[:300]
        )
    corrected["vague_flags"] = vague
    corrected["biased_flags"] = biased

    # 脏话/非作答强惩罚（由 LLM 判定，规则仅兜底）：乱说也不能拿分。
    # 纯“疑似乱码”（无脏话）在 LLM 模式下已能可靠识别；mock 模式不进此分支。
    # 仅压分数与打标记，不回写 feedback 文本——反馈文字统一由 _build_mock_feedback
    # （mock）或 LLM 产出，避免重复/死板。
    if verdict is not None and verdict.category == "invalid_nonanswer" and verdict.abuse:
        corrected["content_relevance"] = 0
        corrected["professional_accuracy"] = 0
        corrected["clarity"] = 1
        corrected["star_completeness"] = 0
        corrected["position_match"] = 1
        flag_label = "不当内容/非作答"
        vague_flags = corrected.get("vague_flags") or []
        if flag_label not in vague_flags:
            vague_flags.append(flag_label)
        corrected["vague_flags"] = vague_flags
    # mock（无 LLM 语义判定）下，对“极短、几乎无实质内容”的回答设低分底线。
    # 这是通用评分启发式（按内容量），不是乱码判定；长回答不受影响。
    if not _llm_enabled():
        stripped_ans = (answer or "").strip()
        if len(stripped_ans) < 10:
            for _k in DIMENSION_MAX:
                corrected[_k] = min(corrected[_k], 3)

    corrected["total"] = sum(corrected[key] for key in DIMENSION_MAX)
    return corrected


def _apply_question_relevance_rules(
    scores: Dict[str, Any],
    question: str,
    answer: str,
) -> Dict[str, Any]:
    corrected = dict(scores)
    missing_requirements = _missing_question_requirements(question, answer)
    corrected["missing_question_requirements"] = missing_requirements

    if not missing_requirements:
        corrected["total"] = sum(corrected[key] for key in DIMENSION_MAX)
        return corrected

    missing_text = "；".join(missing_requirements)
    corrected["content_relevance"] = min(corrected["content_relevance"], 12)
    corrected["clarity"] = min(corrected["clarity"], 14)
    corrected["issues"] = _join_feedback(
        corrected.get("issues"),
        f"回答与题目要点覆盖不足，漏答：{missing_text}",
        200,
    )
    corrected["improvement_suggestions"] = _join_feedback(
        corrected.get("improvement_suggestions"),
        f"先逐项回应题目要求，再展开项目细节：{missing_text}",
        300,
    )
    corrected["total"] = sum(corrected[key] for key in DIMENSION_MAX)
    return corrected


def _scored_answer_details(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    details = []
    questions = state.get("questions", [])
    for index, answer in enumerate(state.get("answers", [])):
        scores = answer.get("scores")
        if not scores:
            continue
        details.append(
            {
                "question": questions[index] if index < len(questions) else "",
                "first_answer": answer.get("first_answer", ""),
                "followup_question": answer.get("followup_question"),
                "followup_answer": answer.get("followup_answer"),
                "scores": scores,
            }
        )
    return details


def _dimension_averages(scored: List[Dict[str, Any]]) -> Dict[str, float]:
    if not scored:
        return {}
    averages = {}
    for key in DIMENSION_MAX:
        values = [item["scores"].get(key, 0) for item in scored]
        averages[key] = round(sum(values) / len(values), 1)
    return averages


def _build_calibration_summary(scored: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总 Agent(LLM) 评分与规则评分的对照，用于评分校准（进阶 #2）。"""
    if not scored:
        return {}
    llm_scores = [item["scores"].get("llm_score") for item in scored if item["scores"].get("llm_score") is not None]
    rule_scores = [item["scores"].get("rule_score", 0) for item in scored if item["scores"].get("rule_score") is not None]
    final_scores = [item["scores"].get("total", 0) for item in scored]
    vague_count = sum(1 for item in scored if item["scores"].get("vague_flags"))
    biased_count = sum(1 for item in scored if item["scores"].get("biased_flags"))
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
    return {
        "agent_avg_score": avg(final_scores),
        "llm_avg_score": avg(llm_scores) if llm_scores else None,
        "rule_avg_score": avg(rule_scores),
        "samples_with_llm": len(llm_scores),
        "flagged_vague": vague_count,
        "flagged_biased": biased_count,
        "note": "rule_avg_score 为纯规则评分基线；llm_avg_score 仅在启用 LLM 时存在，用于与 Agent 评分对照校准。",
    }


def _rewrite_star(question: str, answer: str, target_position: str) -> str:
    prompt = f"""请将以下面试回答改写为 STAR 格式：

面试问题：{question}
原回答：{answer}
目标岗位：{target_position}

请按 S（情境）、T（任务）、A（行动）、R（结果）输出，不要使用任何 Markdown 格式。"""
    return _strip_markdown(
        _safe_call_llm(
            system_prompt="你是面试辅导专家，擅长将普通回答改写为 STAR 结构化表达。不要输出 Markdown 符号。",
            user_prompt=prompt,
            fallback=(
                "S（情境）：在项目开发过程中遇到明确业务或技术问题。\n"
                "T（任务）：需要按时完成方案设计、开发实现和测试验证。\n"
                "A（行动）：我拆解需求，选择合适技术方案，完成核心功能并补充测试。\n"
                "R（结果）：功能稳定交付，后续可继续用数据量化效率、性能或质量提升。"
            ),
            temperature=0.6,
        )
    )


def _generate_practice_plan(
    dimension_averages: Dict[str, float],
    weak_questions: List[str],
    target_position: str,
    interview_mode: str = DEFAULT_INTERVIEW_MODE,
) -> str:
    weak_dims = [key for key, score in dimension_averages.items() if score < 15]
    weak_text = "、".join(weak_dims) if weak_dims else "综合表达"
    questions_text = "；".join(weak_questions[:3]) if weak_questions else "通用面试题"
    prompt = f"""根据以下面试弱项，生成下一轮练习计划：

面试模式：{interview_mode}
薄弱维度：{weak_text}
薄弱题型示例：{questions_text}
目标岗位：{target_position}

请输出 3-5 条具体练习建议，每条包含练习内容和预期提升维度。不要使用 Markdown 格式。"""
    return _strip_markdown(
        _safe_call_llm(
            system_prompt="你是面试辅导教练，练习建议要具体、可执行，不要 Markdown。",
            user_prompt=prompt,
            fallback=(
                "1. 每天准备 2 个 STAR 项目案例，重点补齐情境、任务、行动、结果。\n"
                "2. 针对目标岗位整理核心技术清单，并为每项准备一个项目应用例子。\n"
                "3. 回答时加入数字化结果，例如性能提升、缺陷减少或交付周期缩短。"
            ),
            temperature=0.5,
        )
    )


def _generate_summary(overall_score: float, dimension_averages: Dict[str, float], interview_mode: str = DEFAULT_INTERVIEW_MODE) -> str:
    if overall_score >= 85:
        level = "优秀"
    elif overall_score >= 70:
        level = "良好"
    elif overall_score >= 60:
        level = "一般"
    else:
        level = "需要提升"
    dimension_text = "，".join(
        "%s: %s分" % (DIMENSION_CN_NAMES.get(dimension, dimension), score)
        for dimension, score in dimension_averages.items()
    )
    return "[%s] 面试综合评定：%s（%s分）。各维度得分：%s。建议参照练习计划针对性提升。" % (
        interview_mode,
        level,
        overall_score,
        dimension_text or "暂无",
    )
