"""Interview Agent service.

The service can call an OpenAI-compatible LLM when configured, but every path has
rule-based fallbacks so local tests and classroom demos work without an API key.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Any = None

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


def should_followup(answer: str) -> bool:
    stripped = answer.strip()
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
) -> Dict[str, Any]:
    parsed_resume = _parse_resume(resume_text)
    tools_used = ["resume_analyzer"]

    job_requirements = ""
    if target_position:
        job_requirements = _analyze_job_requirements(target_position)
        tools_used.append("job_matcher")

    questions = _generate_questions(
        resume_text=resume_text,
        parsed_resume=parsed_resume,
        target_position=target_position,
        job_requirements=job_requirements,
    )
    tools_used.append("question_generator")

    agent_state = {
        "version": 1,
        "session_uuid": str(uuid4()),
        "resume_excerpt": resume_text[:1000],
        "target_position": target_position,
        "target_job_id": str(target_job_id or ""),
        "parsed_resume": parsed_resume,
        "job_requirements": job_requirements,
        "questions": questions,
        "current_index": 0,
        "answers": [{} for _ in questions],
        "status": "in_progress",
        "created_at": time.time(),
    }

    return {
        "session_id": agent_state["session_uuid"],
        "question": questions[0],
        "tools_used": tools_used,
        "total_questions": len(questions),
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
            "agent_state": state,
        }

    slot = state["answers"][idx]
    first_answer = slot.get("first_answer")
    if not first_answer:
        slot["first_answer"] = answer
        if should_followup(answer):
            followup = _generate_followup(
                question=questions[idx],
                answer=answer,
                target_position=state.get("target_position", ""),
            )
            slot["followup_question"] = followup
            return {
                "is_followup": True,
                "followup_question": followup,
                "score": None,
                "feedback": "回答还不够具体，需要补充追问。",
                "dimension_scores": None,
                "next_question": followup,
                "current_index": idx,
                "total_questions": total,
                "session_status": "in_progress",
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
    practice_plan = _generate_practice_plan(
        dimension_averages=dimension_averages,
        weak_questions=[item["question"] for item in weakest_answers],
        target_position=state.get("target_position", ""),
    )

    report = {
        "session_id": str(session_id),
        "overall_score": overall_score,
        "dimension_averages": dimension_averages,
        "total_questions_answered": len(scored),
        "details": scored,
        "star_suggestions": star_suggestions,
        "practice_plan": practice_plan,
        "summary": _generate_summary(overall_score, dimension_averages),
    }
    state["status"] = "completed"
    state["completed_report"] = report
    return report


def _ensure_state(state: Dict[str, Any]) -> Dict[str, Any]:
    questions = state.get("questions")
    if not isinstance(questions, list) or not questions:
        questions = _default_questions(state.get("target_position", ""))
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
    scores = _score_answer(
        question=questions[idx],
        answer=answer_text,
        target_position=state.get("target_position", ""),
        job_requirements=state.get("job_requirements", ""),
    )
    scores = _apply_score_rules(scores, answer_text)
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
        "feedback": scores["overall_comment"],
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


def _analyze_job_requirements(target_position: str) -> str:
    prompt = f"""目标岗位：{target_position}

请用 3-5 句话总结这个岗位的核心技能要求、常见面试重点和典型工作场景。"""
    return _safe_call_llm(
        system_prompt="你是资深技术面试官，熟悉各岗位的 JD 和面试要点。",
        user_prompt=prompt,
        fallback="%s 岗位通常关注技术基础、项目落地能力、沟通协作和问题排查能力。" % target_position,
        temperature=0.5,
    )


def _generate_questions(
    resume_text: str,
    parsed_resume: Dict[str, Any],
    target_position: str,
    job_requirements: str,
) -> List[str]:
    skills_text = "、".join(parsed_resume.get("skills", [])) or "通用技能"
    projects_text = json.dumps(parsed_resume.get("projects", []), ensure_ascii=False)
    position = target_position or "目标岗位"
    fallback_questions = _default_questions(position)

    prompt = f"""请为以下候选人生成 8 道面试题，严格按类别分配：

候选人背景：
- 技能：{skills_text}
- 项目经历：{projects_text}
- 简历原文：{resume_text[:1000]}

目标岗位：{position}
岗位要求：{job_requirements}

题目分配：
1-2 题：自我介绍与动机类
3-5 题：项目经历深挖类
6-7 题：技术基础类
8 题：行为问题类

只输出 JSON 数组，例如 ["题目1", "题目2"]。
"""
    result = _safe_call_llm(
        system_prompt="你是资深面试官。只输出 JSON 数组。",
        user_prompt=prompt,
        fallback=json.dumps(fallback_questions, ensure_ascii=False),
        temperature=0.8,
    )
    parsed = _parse_json_fallback(result)
    questions = [str(item).strip() for item in parsed] if isinstance(parsed, list) else []
    questions = [question for question in questions if question]
    return (questions + fallback_questions)[:8]


def _default_questions(position: str = "") -> List[str]:
    target = position or "目标岗位"
    return [
        "请做一个简短的自我介绍，并说明你与%s最匹配的优势。" % target,
        "你为什么选择应聘%s？" % target,
        "请详细描述一个你主导或深度参与的项目。",
        "这个项目中最困难的问题是什么，你是怎样定位和解决的？",
        "你如何保证项目代码质量、接口稳定性或交付质量？",
        "你对%s所需的核心技术栈了解多少？" % target,
        "如果系统上线后出现性能问题，你会如何排查并优化？",
        "请分享一次团队协作中出现分歧时你的处理方式。",
    ]


def _generate_followup(question: str, answer: str, target_position: str) -> str:
    prompt = f"""原问题：{question}
候选人回答：{answer}
目标岗位：{target_position}

候选人的回答不够具体。请生成一个追问，引导对方补充具体技术动作、量化结果和个人贡献。
只输出追问本身，不超过 80 字。"""
    return _safe_call_llm(
        system_prompt="你是面试官，追问要具体、有引导性。",
        user_prompt=prompt,
        fallback="能具体说一下你用了什么技术、承担了哪部分工作，以及取得了什么量化成果吗？",
        temperature=0.5,
    )


def _score_answer(
    question: str,
    answer: str,
    target_position: str,
    job_requirements: str,
) -> Dict[str, Any]:
    prompt = f"""请对以下面试回答进行评分。

面试问题：{question}
候选人回答：{answer}
目标岗位：{target_position}
岗位要求参考：{job_requirements}

评分维度：
1. content_relevance：25 分
2. professional_accuracy：25 分
3. clarity：20 分
4. star_completeness：20 分
5. position_match：10 分

请严格输出 JSON：
{{
  "content_relevance": 数字,
  "professional_accuracy": 数字,
  "clarity": 数字,
  "star_completeness": 数字,
  "position_match": 数字,
  "overall_comment": "简短总评"
}}
"""
    fallback = {
        **DEFAULT_DIMENSION_SCORES,
        "overall_comment": "回答较笼统，建议补充具体技术细节、个人贡献和量化结果。",
    }
    result = _safe_call_llm(
        system_prompt="你是严格但公正的面试官。只输出 JSON，不要其他内容。",
        user_prompt=prompt,
        fallback=json.dumps(fallback, ensure_ascii=False),
        temperature=0.3,
    )
    parsed = _parse_json_fallback(result)
    raw_scores = parsed if isinstance(parsed, dict) else fallback

    scores: Dict[str, Any] = {}
    for key, max_score in DIMENSION_MAX.items():
        scores[key] = _clamp_score(raw_scores.get(key, fallback.get(key, 0)), max_score)
    scores["total"] = sum(scores[key] for key in DIMENSION_MAX)
    scores["overall_comment"] = str(
        raw_scores.get("overall_comment") or fallback["overall_comment"]
    )[:160]
    return scores


def _clamp_score(value: Any, max_score: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = 0
    return max(0, min(max_score, number))


def _apply_score_rules(scores: Dict[str, Any], answer: str) -> Dict[str, Any]:
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


def _rewrite_star(question: str, answer: str, target_position: str) -> str:
    prompt = f"""请将以下面试回答改写为 STAR 格式：

面试问题：{question}
原回答：{answer}
目标岗位：{target_position}

请按 S（情境）、T（任务）、A（行动）、R（结果）输出。"""
    return _safe_call_llm(
        system_prompt="你是面试辅导专家，擅长将普通回答改写为 STAR 结构化表达。",
        user_prompt=prompt,
        fallback=(
            "S（情境）：在项目开发过程中遇到明确业务或技术问题。\n"
            "T（任务）：需要按时完成方案设计、开发实现和测试验证。\n"
            "A（行动）：我拆解需求，选择合适技术方案，完成核心功能并补充测试。\n"
            "R（结果）：功能稳定交付，后续可继续用数据量化效率、性能或质量提升。"
        ),
        temperature=0.6,
    )


def _generate_practice_plan(
    dimension_averages: Dict[str, float],
    weak_questions: List[str],
    target_position: str,
) -> str:
    weak_dims = [key for key, score in dimension_averages.items() if score < 15]
    weak_text = "、".join(weak_dims) if weak_dims else "综合表达"
    questions_text = "；".join(weak_questions[:3]) if weak_questions else "通用面试题"
    prompt = f"""根据以下面试弱项，生成下一轮练习计划：

薄弱维度：{weak_text}
薄弱题型示例：{questions_text}
目标岗位：{target_position}

请输出 3-5 条具体练习建议，每条包含练习内容和预期提升维度。"""
    return _safe_call_llm(
        system_prompt="你是面试辅导教练，练习建议要具体、可执行。",
        user_prompt=prompt,
        fallback=(
            "1. 每天准备 2 个 STAR 项目案例，重点补齐情境、任务、行动、结果。\n"
            "2. 针对目标岗位整理核心技术清单，并为每项准备一个项目应用例子。\n"
            "3. 回答时加入数字化结果，例如性能提升、缺陷减少或交付周期缩短。"
        ),
        temperature=0.5,
    )


def _generate_summary(overall_score: float, dimension_averages: Dict[str, float]) -> str:
    if overall_score >= 85:
        level = "优秀"
    elif overall_score >= 70:
        level = "良好"
    elif overall_score >= 60:
        level = "一般"
    else:
        level = "需要提升"
    dimension_text = "，".join(
        "%s: %s分" % (dimension, score)
        for dimension, score in dimension_averages.items()
    )
    return "面试综合评定：%s（%s分）。各维度得分：%s。建议参照练习计划针对性提升。" % (
        level,
        overall_score,
        dimension_text or "暂无",
    )
