"""Interview Agent service.

Supports 4 interview modes (each with distinct persona, question style,
follow-up strategy and scoring rubric):
  - HR面 (behavioural): focus on soft skills, motivation, team fit
  - 技术面 (technical): focus on technical depth and project experience (default)
  - 压力面 (pressure): challenging followups, stress testing
  - 反馈教练 (coach): gentle tone, detailed improvement suggestions

Design principles:
  - Temperature is scenario-based: high for interactive Q&A (questions,
    follow-ups), low for evaluation/report generation, very low for judgments.
  - Agent (LLM) semantic judgement takes priority; hard-coded rules only
    dominate as fallback when the LLM is unavailable, otherwise rules act
    as soft guardrails.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from app.core.config import settings
from app.services.job_data import (
    get_position_job_summary,
    get_position_responsibilities,
)
from app.services.interview_question_bank import (
    _POSITION_QUESTIONS,
    get_position_question_pool,
    get_question_bank_summary,
    load_question_bank,
    normalize_position,
)
from app.services.knowledge_base import (
    get_failure_case_by_scenario,
    role_profile_context,
)

logger = logging.getLogger(__name__)

_client: Any = None

# ── interview mode constants ──────────────────────────────────────────
INTERVIEW_MODES = frozenset({"HR面", "技术面", "压力面", "反馈教练"})
DEFAULT_INTERVIEW_MODE = "技术面"

# ── 模式专属面试官人设（System Prompt），强化四种模式的区分度 ──────────
MODE_PERSONAS = {
    "HR面": {
        "question": (
            "你是资深 HR 面试官，擅长行为面试与动机挖掘。"
            "你只关心候选人的沟通表达、职业规划、价值观与团队契合度，"
            "绝不提问八股式技术细节。出题风格亲切但有穿透力。"
        ),
        "followup": "你是资深 HR 面试官，正在进行行为面试，擅长从回答中捕捉真实动机与具体经历。",
        "scoring": "你是资深 HR 面试官，从软技能、价值观与文化匹配角度严格但公正地评分。",
    },
    "技术面": {
        "question": (
            "你是资深技术面试官，长期负责一线技术招聘。"
            "你只关心候选人的技术深度、项目落地能力与问题排查思路，"
            "出题直奔具体技术场景，拒绝空泛的概念背诵题。"
        ),
        "followup": "你是资深技术面试官，擅长追问技术细节、个人贡献边界与量化结果。",
        "scoring": "你是资深技术面试官，从技术深度与工程落地角度严格但公正地评分。",
    },
    "压力面": {
        "question": (
            "你是以犀利著称的压力面面试官。"
            "你的任务就是制造适度压迫感：质疑、挑战、设置两难，"
            "逼迫候选人暴露真实水平与临场反应，每道题都必须带有挑战性。"
        ),
        "followup": "你是压力面面试官，追问尖锐直接，专挑回答中最薄弱、最矛盾的点施压。",
        "scoring": "你是压力面面试官，重点评估候选人在压力下的逻辑、情绪稳定性与临场应变，评分严格但公正。",
    },
    "反馈教练": {
        "question": (
            "你是耐心的面试教练，目标是帮候选人摸底并提升。"
            "出题温和、有引导性，让候选人愿意充分表达，便于后续给出针对性建议。"
        ),
        "followup": "你是面试教练，追问是为了帮候选人补全表达要素，语气温和鼓励。",
        "scoring": (
            "你是面试教练，反馈从细：问题描述温和但诚实，改进建议必须具体可执行。"
            "你的鼓励只对真实的努力有效——没有内容时如实指出，才是对候选人最大的负责。"
        ),
    },
}


def _mode_persona(interview_mode: str, task: str) -> str:
    """返回模式专属人设 System Prompt，task 为 question/followup/scoring。"""
    persona = MODE_PERSONAS.get(interview_mode, MODE_PERSONAS["技术面"])
    return persona.get(task, persona["question"])


# ── 分场景温度配置 ──────────────────────────────────────────────────
# 面试交互（出题、追问）用高温度，问答更自然、不死板
TEMP_INTERACTIVE = 0.85
# 解析/分析类（简历解析、岗位分析）用中低温度，保证结构稳定
TEMP_ANALYSIS = 0.3
# 评分与报告生成（打分、STAR 改写、练习计划）用低温度，严格依据规则
TEMP_EVALUATION = 0.2
# 判断类（追问判断）用极低温度，只要稳定输出
TEMP_JUDGE = 0.1

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


def _is_meaningless_answer(answer: str) -> bool:
    """检测无意义输入（乱敲键盘、无内容重复字符等）。

    此类输入不应进入 LLM 评分：模型会被"鼓励人设"倒逼，给乱码编造并不存在的
    优点（如实测中"啊打发嘎达"被评价为"显示了积极的态度"）。
    判定逻辑：仅拦截"长度足够但内容无意义"的输入（用字多样性过低 + 高频重复
    片段），避免误伤两类正常情况：
    - 短回答（如"我负责了一个项目"）：应走追问流程引导补充，而非直接拒绝；
    - 排比表述（如"我负责A，我负责B，我负责C"）：用字多样性正常。
    """
    text = re.sub(r"\s+", "", answer)
    if len(text) < 10:
        # 短回答交给追问逻辑处理，不视为乱码
        return False
    unique_ratio = len(set(text)) / len(text)
    if unique_ratio >= 0.45:
        return False
    lowered = text.lower()
    for i in range(len(lowered) - 3):
        bigram = lowered[i : i + 2]
        if bigram.strip() and lowered.count(bigram) >= 3:
            return True
    # 用字多样性极低（如"啊啊啊啊啊啊"），无需重复片段也视为无意义
    return unique_ratio < 0.25


def _mode_meaningless_reply(interview_mode: str) -> str:
    """无效输入的重答提示，语气按模式区分，但都必须如实指出问题。"""
    replies = {
        "HR面": "刚才的回答似乎没有录入完整内容，可能是误操作。可以重新回答一下刚才的问题吗？",
        "技术面": "这段回答没有有效内容，无法进行评估。请针对刚才的问题给出具体回答。",
        "压力面": "这就是你的回答？一串没有意义的字符。面试中这就是直接淘汰项——再给你一次机会，认真回答。",
        "反馈教练": "看起来这条回答可能是误输入，还没有包含可以分析的内容。别着急，我们再来一次：试着用一两句话说清楚你的经历，我会在你回答后给出具体建议。",
    }
    return replies.get(interview_mode, replies["技术面"])


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


def should_followup(answer: str, question: str = "", interview_mode: str = DEFAULT_INTERVIEW_MODE) -> bool:
    """判断是否需要追问。规则层处理极端情况，LLM 做语义级判断。

    各模式的追问策略不同：
    - HR面：关注是否缺少具体事例，不强制技术关键词
    - 技术面：要求技术细节和量化结果
    - 压力面：倾向追问施压，但回答足够完整时放过
    - 反馈教练：少追问，仅在明显不完整时引导补充
    """
    stripped = answer.strip()

    # ── 规则层：无论哪种模式都适用的硬性触发 ──
    # 回答为空或极短（不到一句话），任何模式都必须追问
    if len(stripped) < 15:
        return True
    # 题目要点覆盖不足，任何模式都应追问
    if question and _missing_question_requirements(question, stripped):
        return True

    # ── LLM 语义判断：可用的前提下让模型判断回答质量 ──
    if _llm_enabled():
        return _llm_should_followup(question, stripped, interview_mode)

    # ── 规则兜底（LLM 不可用时）：按模式分别判断 ──
    return _rule_should_followup(stripped, interview_mode)


def _llm_should_followup(question: str, answer: str, interview_mode: str) -> bool:
    """用 LLM 做语义级的追问判断，避免硬编码规则的死板。"""
    mode_criteria = {
        "HR面": "回答缺少具体事例、个人感受或真实动机描述",
        "技术面": "回答缺少具体技术动作、量化结果或个人贡献说明",
        "压力面": "回答过于圆滑、缺乏实质内容，或明显在回避问题",
        "反馈教练": "回答严重缺少细节，无法据此给出有意义的改进建议",
    }
    criteria = mode_criteria.get(interview_mode, mode_criteria["技术面"])
    prompt = f"""你正在判断面试中是否需要追问候选人。

面试问题：{question}
候选人回答：{answer}

当前是{interview_mode}，需要追问的标准是：{criteria}。

请判断：这个回答是否需要追问？只输出"是"或"否"，不要输出其他内容。"""
    result = _safe_call_llm(
        system_prompt=f"你是{interview_mode}的资深面试官，判断是否需要追问。只输出一个字。",
        user_prompt=prompt,
        fallback="",
        temperature=TEMP_JUDGE,
        max_tokens=10,
    ).strip()
    if "是" in result:
        return True
    if "否" in result:
        return False
    # LLM 输出不可解析时退回规则
    return _rule_should_followup(answer, interview_mode)


def _rule_should_followup(answer: str, interview_mode: str) -> bool:
    """LLM 不可用时的规则兜底，按模式区分触发条件。"""
    if interview_mode == "HR面":
        # HR 面不强制技术关键词，关注事例和感受
        if len(answer) < 40:
            return True
        if "负责" in answer and not _contains_quantifier(answer):
            return True
        return False

    if interview_mode == "压力面":
        # 压力面倾向追问施压，但完整回答也放过
        if len(answer) < 60:
            return True
        if not _contains_quantifier(answer) and len(answer) < 100:
            return True
        return False

    if interview_mode == "反馈教练":
        # 教练模式少追问，只在明显不够时引导
        if len(answer) < 40:
            return True
        return False

    # 技术面（默认）：要求技术细节 + 量化
    if len(answer) < 50:
        return True
    if not _contains_tech_keywords(answer):
        return True
    if "负责" in answer and not _contains_quantifier(answer):
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

    parsed_resume = _parse_resume(resume_text)
    tools_used = ["resume_analyzer"]

    job_requirements = ""
    knowledge_context = role_profile_context(target_position)
    if target_position:
        job_requirements = _analyze_job_requirements(target_position, interview_mode, target_job_id)
        tools_used.append("job_matcher")
    if knowledge_context:
        tools_used.append("text_knowledge_base")

    questions = _generate_questions(
        resume_text=resume_text,
        parsed_resume=parsed_resume,
        target_position=target_position,
        job_requirements=job_requirements,
        interview_mode=interview_mode,
        job_id=target_job_id,
    )
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
        "knowledge_context": knowledge_context,
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
            "feedback": "全部题目已完成，可以生成面试报告。",
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

    # 无效输入拦截：乱码/无意义字符不进入追问和评分流程，
    # 直接要求重答（不消耗追问次数，也不产生分数）。
    if _is_meaningless_answer(answer):
        return {
            "is_followup": False,
            "followup_question": None,
            "score": None,
            "feedback": _mode_meaningless_reply(interview_mode),
            "dimension_scores": None,
            "next_question": questions[idx],
            "current_index": idx,
            "total_questions": total,
            "session_status": "in_progress",
            "strengths": "",
            "issues": "",
            "improvement_suggestions": "",
            "agent_state": state,
        }

    if not first_answer:
        slot["first_answer"] = answer
        missing_requirements = _missing_question_requirements(questions[idx], answer)
        if should_followup(answer, question=questions[idx], interview_mode=interview_mode):
            followup = _generate_followup(
                question=questions[idx],
                answer=answer,
                target_position=state.get("target_position", ""),
                interview_mode=interview_mode,
                missing_requirements=missing_requirements,
            )
            slot["followup_question"] = followup
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
        return _score_and_advance(state, idx, answer)

    slot["followup_answer"] = answer
    combined_answer = "第一轮回答：%s\n追问补充：%s" % (first_answer, answer)
    return _score_and_advance(state, idx, combined_answer)


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


def _score_and_advance(state: Dict[str, Any], idx: int, answer_text: str) -> Dict[str, Any]:
    questions = state["questions"]
    total = len(questions)
    interview_mode = state.get("interview_mode", DEFAULT_INTERVIEW_MODE)

    scores = _score_answer(
        question=questions[idx],
        answer=answer_text,
        target_position=state.get("target_position", ""),
        job_requirements=state.get("job_requirements", ""),
        interview_mode=interview_mode,
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

    return {
        "is_followup": False,
        "followup_question": None,
        "score": scores["total"],
        "feedback": scores.get("overall_comment", ""),
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
        temperature=TEMP_ANALYSIS,
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
    profile_context = role_profile_context(target_position)
    has_real_data = not real_summary.startswith("暂无")

    if has_real_data:
        data_constraint = (
            "请结合上面的真实职责与要求总结，不要引入资料之外的技能要求。"
            "【相关性校验】若真实岗位资料的方向与目标岗位名称明显不符"
            "（例如目标是 3D 美术岗、资料却是内容运营/视频剪辑岗），"
            "说明岗位库数据不匹配，此时以岗位名称的行业常识为主，忽略不相关的资料。"
        )
    else:
        # 无真实岗位数据时，LLM 只能凭常识概括通用能力，
        # 明确禁止编造具体工具/业务要求（实测中曾编造出"视频剪辑、SEO"等错位要求污染评分）。
        data_constraint = (
            "【注意】岗位库暂无该岗位的真实数据。你只能基于该岗位名称做行业常识性的通用概括，"
            "禁止编造具体的软件工具、业务指标或细分方向要求；不确定的内容一律不写。"
        )

    prompt = f"""目标岗位：{target_position}
面试模式：{interview_mode}

真实岗位资料（来自岗位库）：
{real_summary}

文本知识库岗位画像：
{profile_context or "（无）"}

请用 3-5 句话总结这个岗位在{interview_mode}中的核心关注点、常见面试重点和典型工作场景。
{data_constraint}
{mode_hint}"""
    fallback = (
        f"{target_position} 岗位通常关注技术基础、项目落地能力、沟通协作和问题排查能力。\n"
        f"【真实岗位参考】{real_summary}"
        + (f"\n{profile_context}" if profile_context else "")
    )
    return _safe_call_llm(
        system_prompt="你是资深技术面试官，熟悉各岗位的 JD 和面试要点。",
        user_prompt=prompt,
        fallback=fallback,
        temperature=TEMP_ANALYSIS,
    )


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
    question_bank_reference = "\n".join(
        f"{index + 1}. {question}"
        for index, question in enumerate(default_questions[:8])
    )

    position_bucket = normalize_position(target_position)
    real_resp = get_position_responsibilities(position_bucket, job_id)
    profile_context = role_profile_context(target_position)
    # 以真实岗位职责题为主（最多 6 道），首题保留为模式专属开场，不足 8 道用默认题补足
    grounded = [
        f"结合真实岗位职责「{r[:50]}」，请分享你过往项目中对应的经验、做法与可量化成果。"
        for r in (real_resp[:6] if real_resp else [])
    ]
    fallback_questions = [default_questions[0]] + grounded if default_questions else list(grounded)
    idx = 1
    while len(fallback_questions) < 8 and idx < len(default_questions):
        fallback_questions.append(default_questions[idx])
        idx += 1
    # 去重，避免与真实职责题叠加后重复
    _seen: set = set()
    _final: List[str] = []
    for q in fallback_questions:
        if q not in _seen:
            _seen.add(q)
            _final.append(q)
    fallback_questions = _final[:8]
    allocation, mode_instruction = _mode_question_allocation(interview_mode)

    prompt = f"""请为以下候选人生成 8 道面试题，严格按类别分配：

面试模式：{interview_mode}
候选人背景：
- 技能：{skills_text}
- 项目经历：{projects_text}
- 简历原文：{resume_text[:1000]}

目标岗位：{position}
岗位要求：{job_requirements}
岗位画像知识：{profile_context or "（无）"}
真实岗位职责参考：{("；".join(real_resp[:4]) if real_resp else "（无）")}
题库参考：
{question_bank_reference or "（无）"}

题目分配：
{allocation}

{mode_instruction}
请优先从题库参考中选取或改写题目，并结合候选人简历和真实岗位职责进行个性化调整。

【出题硬性要求】
1. 每道题只聚焦一个核心问题，禁止在一道题里堆砌多个子问题或要求候选人逐项罗列。
2. 题目长度控制在 80 字以内，简洁有力。
3. 不要求候选人现场写代码片段或画图，口头描述思路即可。
4. 结合简历时只引用一个最相关的项目点，不要强行串联多个项目。

只输出 JSON 数组，例如 ["题目1", "题目2"]。
"""
    result = _safe_call_llm(
        system_prompt=_mode_persona(interview_mode, "question") + "只输出 JSON 数组。",
        user_prompt=prompt,
        fallback=json.dumps(fallback_questions, ensure_ascii=False),
        temperature=TEMP_INTERACTIVE,
    )
    parsed = _parse_json_fallback(result)
    questions = [str(item).strip() for item in parsed] if isinstance(parsed, list) else []
    questions = [question for question in questions if question]
    if not questions:
        # LLM 离线/解析失败：直接使用去重后的真实职责兜底题库
        return fallback_questions[:8]
    # LLM 成功返回：若不足 8 道，用真实职责兜底题补全（去重）
    for q in fallback_questions:
        if q not in questions:
            questions.append(q)
        if len(questions) >= 8:
            break
    return questions[:8]


def _mode_analysis_hint(interview_mode: str) -> str:
    hints = {
        "HR面": (
            "你需要站在 HR 视角，分析这个岗位对候选人软技能、职业稳定性、"
            "价值观和团队契合度的要求，不涉及具体技术栈细节。"
        ),
        "技术面": (
            "你需要站在技术负责人视角，分析这个岗位的核心技术栈、"
            "项目落地难点和常见技术考察点，聚焦工程实现能力。"
        ),
        "压力面": (
            "你需要分析这个岗位最真实的高压工作场景（如紧急上线、线上事故、"
            "需求频繁变更），找出候选人最容易被挑战和质疑的薄弱环节。"
        ),
        "反馈教练": (
            "你需要分析这个岗位的核心能力模型，找出初级候选人最常见的"
            "能力短板和最容易提升的维度，便于后续给出可执行建议。"
        ),
    }
    return hints.get(interview_mode, "")


def _mode_question_allocation(interview_mode: str):
    allocations = {
        "HR面": (
            "1-2 题：自我介绍与职业规划（必须包含动机和长期目标）\n"
            "3-4 题：团队协作与沟通（要求举出真实合作/冲突案例）\n"
            "5-6 题：价值观与文化匹配（如加班态度、公司文化理解）\n"
            "7 题：抗压与情绪管理（非技术场景，侧重人际压力）\n"
            "8 题：情景模拟（职场人际或取舍类场景）",
            "【严格约束】题目只涉及软技能、动机、价值观和职场行为，"
            "禁止出现任何技术栈、代码、架构相关词汇。",
        ),
        "技术面": (
            "1-2 题：技术自我介绍与岗位动机（结合简历技术栈）\n"
            "3-5 题：项目经历深挖（架构选型、难点攻克、个人贡献边界）\n"
            "6-7 题：技术基础与场景设计（核心技术栈原理或系统设计）\n"
            "8 题：工程协作类（Code Review、技术分歧处理）",
            "【严格约束】每道题都要落到具体技术动作上，"
            "禁止出现纯软技能题（如'你怎么和同事相处'）。",
        ),
        "压力面": (
            "1-2 题：尖锐质疑自我认知（如'凭什么录用你'）\n"
            "3-4 题：失败/失误经历连续深挖（要求承认并复盘真实失败）\n"
            "5-6 题：高压场景两难选择（时间不够、资源不足、被否决）\n"
            "7 题：极限挑战（极短 deadline 或不熟悉领域交付）\n"
            "8 题：自我辩护（在质疑中为自己辩护）",
            "【严格约束】每道题都要带质疑、挑战或压迫感，语气尖锐直接，"
            "禁止使用温和、鼓励性的措辞。",
        ),
        "反馈教练": (
            "1-2 题：自我认知与求职目标（引导真实表达现状）\n"
            "3-4 题：项目复盘（引导说出成功点和遗憾点）\n"
            "5-6 题：技能自评与差距分析（自评 + 说明依据）\n"
            "7 题：STAR 结构化表达练习\n"
            "8 题：自我提升计划（引导制定可执行计划）",
            "【严格约束】语气温和、有引导性，题目末尾可带提示"
            "（如'可以结合一个具体项目来谈'），禁止使用质疑或施压措辞。",
        ),
    }
    return allocations.get(interview_mode, allocations["技术面"])


def _mode_followup_tone(interview_mode: str) -> str:
    tones = {
        "HR面": (
            "语气友好但有穿透力，聚焦'具体事例+真实感受'。"
            "例如：'能举一个具体发生过的例子吗？当时你是怎么想的？'"
        ),
        "技术面": (
            "语气专业直接，聚焦'技术动作+量化结果+个人贡献边界'。"
            "例如：'这个方案里哪些是你独立完成的？性能提升了多少？'"
        ),
        "压力面": (
            "语气尖锐、带质疑，制造适度压迫感。"
            "例如：'这个结果听起来很普通，你觉得凭什么算亮点？'"
        ),
        "反馈教练": (
            "语气温和鼓励，先肯定再引导补充。"
            "例如：'这个方向不错，如果能再具体说说你当时是怎么做的就更好了。'"
        ),
    }
    return tones.get(interview_mode, tones["技术面"])


def _mode_scoring_hint(interview_mode: str) -> str:
    hints = {
        "HR面": (
            "评分侧重：clarity（表达清晰度）和 position_match（文化匹配）权重最高；"
            "star_completeness 看是否有完整的事例叙述；"
            "professional_accuracy 评估自我认知的真实性而非技术正确性；"
            "不要求技术关键词，回答中没有技术名词不扣分。"
        ),
        "技术面": (
            "评分侧重：content_relevance 和 professional_accuracy 权重最高，"
            "考察技术细节是否准确、方案是否可行；"
            "star_completeness 要求有清晰的问题→行动→结果链路；"
            "回答中出现技术错误要明显扣分。"
        ),
        "压力面": (
            "评分侧重：重点评估候选人在压力下是否保持逻辑清晰、不慌乱、不回避；"
            "回答内容本身的完美度可以降低要求，但闪烁其词、明显说谎要重扣；"
            "overall_comment 中必须评价候选人的抗压表现。"
        ),
        "反馈教练": (
            "评分严格参照锚点，不要上浮；教练模式的特殊性体现在反馈语气而非分数："
            "issues 用温和语气描述（说'可以更好'而不是'错误'）；"
            "improvement_suggestions 必须给 3 条以上，每条具体到可以直接执行；"
            "overall_comment 先肯定回答中真实存在的可取之处（没有就如实跳过），再指出 1-2 个最值得提升的点。"
        ),
    }
    return hints.get(interview_mode, "")


def _default_questions(position: str = "", interview_mode: str = DEFAULT_INTERVIEW_MODE) -> List[str]:
    target = position or "目标岗位"
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
    generic_questions = mode_questions.get(interview_mode, mode_questions["技术面"])
    position_questions = get_position_question_pool(position, interview_mode)
    if not position_questions:
        return generic_questions

    combined_questions: List[str] = []
    for question in position_questions + generic_questions:
        if question and question not in combined_questions:
            combined_questions.append(question)
        if len(combined_questions) >= 8:
            break
    return combined_questions


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
        fallback = f"你刚才的回答还没有回应题目中的这些要点：{missing_text}。请补充说明。"
    else:
        failure_case = get_failure_case_by_scenario("answer_too_short_follow_up")
        rule_hint = str(failure_case.get("audit_rule", "")) if failure_case else ""
        behavior_hint = str(failure_case.get("expected_system_behavior", "")) if failure_case else ""
        focus_line = "候选人的回答不够具体。%s" % (rule_hint or "")
        fallback = (
            behavior_hint
            or "能具体说一下你用了什么技术、承担了哪部分工作，以及取得了什么量化成果吗？"
        )
    prompt = f"""原问题：{question}
候选人回答：{answer}
目标岗位：{target_position}
面试模式：{interview_mode}

{focus_line}{tone}
只输出追问本身，不超过 80 字。"""
    return _safe_call_llm(
        system_prompt=_mode_persona(interview_mode, "followup") + f"追问要求：{tone}",
        user_prompt=prompt,
        fallback=fallback,
        temperature=TEMP_INTERACTIVE,
    )


def _score_answer(
    question: str,
    answer: str,
    target_position: str,
    job_requirements: str,
    interview_mode: str = DEFAULT_INTERVIEW_MODE,
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

评分锚点（必须参照，避免随意打分）：
- 每个维度得分率 90%+：回答精准、有细节、有量化，几乎无可挑剔
- 70-89%：内容切题、有实质信息，但深度或完整度略有不足
- 50-69%：切题但偏笼统，缺少具体细节或量化结果
- 30-49%：大部分内容空泛或偏离题目，仅有少量有效信息
- 30% 以下：几乎未回答题目或完全无关
注意：没有回答能轻易拿到所有维度满分，总分超过 90 需要真正出色的回答。

诚实底线（优先级高于一切语气要求）：
- strengths 必须基于回答中真实存在的内容，禁止为了鼓励而编造并不存在的优点。
- 如果回答空泛、答非所问或几乎没有有效信息，strengths 应如实写"本次回答暂无可提炼的亮点"，
  issues 直接指出核心问题，overall_comment 也要如实反映，不得套用"已经开始思考""态度积极"等万能话术。
- 鼓励只能体现在建议的建设性上，不能体现在对事实的美化上。

分数与评语一致性（必须遵守）：
- 各维度分数必须与 issues 描述的严重程度一致，禁止"评语说严重偏离、分数却给高分"。
- 若 issues 指出"未回答问题核心/答非所问/完全偏离"，content_relevance 不得超过 50% 得分率。
- 若 issues 指出"回避核心质疑/闪烁其词"，professional_accuracy 不得超过 60% 得分率。
- 若第一轮回答空泛、仅靠追问补充内容，star_completeness 不得超过 75% 得分率。
- 总分超过 90 意味着回答几乎无可挑剔：只要 issues 中有实质性批评，总分就不得上 90。

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
  "overall_comment": "简短总评（1句话）"
}}
"""
    fallback = {
        **DEFAULT_DIMENSION_SCORES,
        "overall_comment": "回答较笼统，建议补充具体技术细节、个人贡献和量化结果。",
        "strengths": "回答涉及了相关主题。",
        "issues": "缺少具体细节和量化数据。",
        "improvement_suggestions": "补充技术动作说明；加入量化成果；明确个人贡献。",
    }
    fallback_json = json.dumps(fallback, ensure_ascii=False)
    result = _safe_call_llm(
        system_prompt=_mode_persona(interview_mode, "scoring") + "只输出 JSON，不要其他内容。",
        user_prompt=prompt,
        fallback=fallback_json,
        temperature=TEMP_EVALUATION,
    )
    # LLM 是否真正返回了评分（区别于降级使用 fallback）
    llm_scored = _llm_enabled() and result.strip() != fallback_json.strip()
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

    # 规则修正 + 表达风险识别（需求 #15）。
    # Agent 已评分时规则只做软纠偏（Agent 优先）；降级时规则主导压分。
    scores = _apply_score_rules(scores, answer.strip(), interview_mode, strict=not llm_scored)
    scores = _apply_question_relevance_rules(scores, question, answer.strip(), strict=not llm_scored)

    # 评分校准（进阶 #2）：对照 Agent(LLM) 评分与纯规则评分，辅助评估 Agent 稳定性。
    base_total = sum(
        _clamp_score(raw_scores.get(key, fallback.get(key, 0)), DIMENSION_MAX[key])
        for key in DIMENSION_MAX
    )
    scores["llm_score"] = base_total if _llm_enabled() else None
    # 纯规则基线：始终用严格规则，作为校准对照
    rule_only = _apply_score_rules(dict(DEFAULT_DIMENSION_SCORES), answer.strip(), interview_mode, strict=True)
    rule_only = _apply_question_relevance_rules(rule_only, question, answer.strip(), strict=True)
    scores["rule_score"] = rule_only["total"]
    return scores


def _clamp_score(value: Any, max_score: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = 0
    return max(0, min(max_score, number))


def _apply_score_rules(
    scores: Dict[str, Any],
    answer: str,
    interview_mode: str = DEFAULT_INTERVIEW_MODE,
    strict: bool = True,
) -> Dict[str, Any]:
    """基于规则对评分做修正，并识别表达风险（需求 #15）。

    规则与 Agent 的优先级：
    - strict=True（LLM 未参与评分）：规则主导，按模式硬性压分。
    - strict=False（LLM 已评分）：Agent 语义判断优先，规则只保留
      极端情况护栏（回答过短）和软性纠偏，不再用关键词硬压分。
    """
    corrected = dict(scores)
    stripped = answer.strip()

    # 极端护栏：无论是否有 LLM，回答过短都说明内容不足
    if len(stripped) < 20:
        corrected["content_relevance"] = min(corrected["content_relevance"], 10)
    if len(stripped) < 50:
        corrected["star_completeness"] = min(corrected["star_completeness"], 10)

    if strict:
        # ── 规则主导（无 LLM 兜底）：按模式硬性压分 ──
        if interview_mode == "技术面":
            if not _contains_tech_keywords(stripped):
                corrected["professional_accuracy"] = min(corrected["professional_accuracy"], 10)
            if not _contains_quantifier(stripped):
                corrected["star_completeness"] = min(corrected["star_completeness"], 12)
        elif interview_mode == "HR面":
            if not _contains_quantifier(stripped) and len(stripped) < 80:
                corrected["star_completeness"] = min(corrected["star_completeness"], 14)
        elif interview_mode == "压力面":
            if len(stripped) < 40 and not _contains_quantifier(stripped):
                corrected["professional_accuracy"] = min(corrected["professional_accuracy"], 12)
        # 反馈教练：不做硬性压分，以鼓励为主
    else:
        # ── Agent 优先：关键词规则退化为软性纠偏 ──
        # 只有"回答明显短且缺关键要素"时才轻压，避免误伤语义上合格的回答
        if interview_mode == "技术面" and not _contains_tech_keywords(stripped) and len(stripped) < 60:
            corrected["professional_accuracy"] = min(corrected["professional_accuracy"], 15)

    # 表达风险识别：空泛表达 -> 降表达清晰度；夸大/绝对化 -> 降专业准确性。
    # LLM 已评分时压分放缓（Agent 优先），仅保留提示性反馈。
    vague, biased = _detect_expression_risks(stripped)
    vague_cap = 10 if strict else 14
    biased_cap = 10 if strict else 14
    if vague:
        corrected["clarity"] = min(corrected["clarity"], vague_cap)
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
        corrected["professional_accuracy"] = min(corrected["professional_accuracy"], biased_cap)
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
    corrected["total"] = sum(corrected[key] for key in DIMENSION_MAX)
    return corrected


def _apply_question_relevance_rules(
    scores: Dict[str, Any],
    question: str,
    answer: str,
    strict: bool = True,
) -> Dict[str, Any]:
    """题目要点覆盖修正。strict=True 时硬压分；Agent 已评分时（False）软纠偏。"""
    corrected = dict(scores)
    missing_requirements = _missing_question_requirements(question, answer)
    corrected["missing_question_requirements"] = missing_requirements

    if not missing_requirements:
        corrected["total"] = sum(corrected[key] for key in DIMENSION_MAX)
        return corrected

    missing_text = "；".join(missing_requirements)
    # Agent 已做语义评分时，关键词规则可能误伤，压分放缓
    relevance_cap = 12 if strict else 16
    clarity_cap = 14 if strict else 17
    corrected["content_relevance"] = min(corrected["content_relevance"], relevance_cap)
    corrected["clarity"] = min(corrected["clarity"], clarity_cap)
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
            temperature=TEMP_EVALUATION,
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
            temperature=TEMP_EVALUATION,
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
