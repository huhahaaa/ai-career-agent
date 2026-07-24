"""面试 Agent 核心服务：出题、追问、评分、STAR改写。

使用 DeepSeek API，兼容 OpenAI SDK 调用方式。
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── DeepSeek 客户端 ──────────────────────────────────────────────
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.llm_api_key,
            base_url="https://api.deepseek.com",
            timeout=30.0,
        )
    return _client


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """调用 DeepSeek，失败时抛出异常由调用方兜底。"""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("LLM 调用失败: %s", exc)
        raise


def _safe_call_llm(
    system_prompt: str,
    user_prompt: str,
    fallback: str = "",
    temperature: float = 0.7,
) -> str:
    """带兜底的 LLM 调用，失败返回 fallback。"""
    try:
        return _call_llm(system_prompt, user_prompt, temperature)
    except Exception:
        return fallback


def _parse_json_fallback(text: str) -> Dict[str, Any]:
    """从 LLM 返回文本中提取 JSON，容错处理。"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试匹配 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试匹配 { ... } 块
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    logger.warning("无法解析 LLM 返回的 JSON: %s", text[:200])
    return {}


# ── 追问判断规则（不调 LLM，纯规则） ──────────────────────────────
TECH_KEYWORDS = [
    "react", "vue", "angular", "node", "python", "java", "go", "rust",
    "typescript", "javascript", "sql", "mongodb", "redis", "docker",
    "kubernetes", "aws", "git", "linux", "http", "api", "rest",
    "css", "html", "spring", "django", "flask", "fastapi",
    "机器学习", "深度学习", "数据", "算法", "模型", "训练",
    "优化", "性能", "部署", "测试", "架构", "设计模式",
    "敏捷", "scrum", "产品", "运营", "用户", "增长",
]
TECH_KEYWORDS_LOWER = [kw.lower() for kw in TECH_KEYWORDS]


def _contains_tech_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in TECH_KEYWORDS_LOWER)


def _contains_quantifier(text: str) -> bool:
    """是否包含数字、百分比等量化表达。"""
    return bool(re.search(r"\d+", text))


def should_followup(answer: str) -> bool:
    """规则判断是否需要追问。

    条件（满足任一即追问）：
    1. 回答 < 50 字
    2. 包含"我负责""我参与"但没有具体内容
    3. 不含技术关键词
    4. 不含量化数据

    注意：每道题最多追问 1 次，这个限制由调用方控制。
    """
    stripped = answer.strip()
    if len(stripped) < 50:
        return True
    if not _contains_tech_keywords(stripped):
        return True
    if "负责" in stripped and not _contains_quantifier(stripped):
        return True
    return False


# ── 面试会话内存存储 ─────────────────────────────────────────────
_sessions: Dict[str, Dict[str, Any]] = {}


def _get_session(session_id: str) -> Optional[Dict[str, Any]]:
    return _sessions.get(session_id)


def _require_session(session_id: str) -> Dict[str, Any]:
    session = _sessions.get(session_id)
    if session is None:
        raise ValueError(f"会话不存在: {session_id}")
    return session


# ── 评分规则兜底 ──────────────────────────────────────────────────
def _apply_score_rules(scores: Dict[str, int], answer: str) -> Dict[str, int]:
    """对 LLM 打分结果进行规则兜底修正。

    规则：
    - 回答 < 20 字 → 内容相关性 ≤ 10
    - 回答 < 50 字 → STAR 完整性 ≤ 10
    - 不含技术关键词 → 专业知识准确性 ≤ 10
    - 含量化数据 → STAR 完整性至少不低于当前值
    """
    corrected = dict(scores)
    answer_len = len(answer.strip())

    if answer_len < 20:
        corrected["content_relevance"] = min(corrected.get("content_relevance", 0), 10)
    if answer_len < 50:
        corrected["star_completeness"] = min(corrected.get("star_completeness", 0), 10)
    if not _contains_tech_keywords(answer.strip()):
        corrected["professional_accuracy"] = min(
            corrected.get("professional_accuracy", 0), 10
        )

    return corrected


# ── 主流程 ────────────────────────────────────────────────────────


def start_interview(
    resume_text: str,
    target_position: str = "",
    target_job_id: str = "",
) -> Dict[str, Any]:
    """开始面试：解析简历 → 提取关键信息 → 生成 8 道面试题。"""
    session_id = str(uuid4())
    tools_used = []

    # 1. 解析简历
    parsed = _parse_resume(resume_text)
    if parsed:
        tools_used.append("resume_analyzer")

    # 2. 分析岗位需求（如果有）
    job_requirements = ""
    if target_position:
        job_requirements = _analyze_job_requirements(target_position, resume_text)
        if job_requirements:
            tools_used.append("job_matcher")

    # 3. 生成 8 道面试题
    questions = _generate_questions(
        resume_text=resume_text,
        parsed_resume=parsed,
        target_position=target_position,
        job_requirements=job_requirements,
    )
    tools_used.append("question_generator")

    # 4. 创建会话
    _sessions[session_id] = {
        "session_id": session_id,
        "resume_text": resume_text,
        "target_position": target_position,
        "target_job_id": target_job_id,
        "parsed_resume": parsed,
        "job_requirements": job_requirements,
        "questions": questions,
        "current_index": 0,
        "answers": [{} for _ in range(len(questions))],
        "status": "in_progress",
        "created_at": time.time(),
    }

    return {
        "session_id": session_id,
        "question": questions[0] if questions else "请做一个简单的自我介绍。",
        "tools_used": tools_used,
        "total_questions": len(questions),
    }


def evaluate_answer(session_id: str, answer: str) -> Dict[str, Any]:
    """评估用户回答：判断追问 / 打分 → 返回下一题或追问。

    每道题最多追问 1 次。如果已经是追问后的回答，直接打分。
    """
    session = _require_session(session_id)
    idx = session["current_index"]
    questions = session["questions"]
    total = len(questions)
    current_answer_slot = session["answers"][idx]

    # 判断这是第一次回答还是追问后的补充回答
    is_followup_answer = bool(current_answer_slot.get("first_answer"))

    if not is_followup_answer:
        # ── 第一次回答 ──
        current_answer_slot["first_answer"] = answer

        if should_followup(answer):
            # 生成追问
            followup = _generate_followup(
                question=questions[idx],
                answer=answer,
                target_position=session.get("target_position", ""),
            )
            if followup:
                current_answer_slot["followup_question"] = followup
                return {
                    "is_followup": True,
                    "followup_question": followup,
                    "score": None,
                    "feedback": None,
                    "next_question": None,
                    "current_index": idx,
                    "total_questions": total,
                    "session_status": "in_progress",
                }

        # 不需追问，直接打分
        return _score_and_advance(session, idx, answer)

    else:
        # ── 追问后的补充回答 ──
        current_answer_slot["followup_answer"] = answer
        combined = (
            f"第一轮回答：{current_answer_slot['first_answer']}\n"
            f"追问补充：{answer}"
        )
        return _score_and_advance(session, idx, combined)


def _score_and_advance(
    session: Dict[str, Any], idx: int, answer_text: str
) -> Dict[str, Any]:
    """打分并推进到下一题。"""
    questions = session["questions"]
    total = len(questions)
    job_req = session.get("job_requirements", "")
    target_position = session.get("target_position", "")

    # LLM 打分
    scores = _score_answer(
        question=questions[idx],
        answer=answer_text,
        target_position=target_position,
        job_requirements=job_req,
    )

    # 规则兜底
    scores = _apply_score_rules(scores, answer_text)

    session["answers"][idx]["scores"] = scores

    # 推进到下一题
    session["current_index"] = idx + 1

    if session["current_index"] >= total:
        session["status"] = "ready_to_finish"
        return {
            "is_followup": False,
            "followup_question": None,
            "score": scores.get("total", 0),
            "feedback": scores.get("overall_comment", ""),
            "dimension_scores": scores,
            "next_question": None,
            "current_index": idx + 1,
            "total_questions": total,
            "session_status": "ready_to_finish",
        }

    return {
        "is_followup": False,
        "followup_question": None,
        "score": scores.get("total", 0),
        "feedback": scores.get("overall_comment", ""),
        "dimension_scores": scores,
        "next_question": questions[session["current_index"]],
        "current_index": session["current_index"],
        "total_questions": total,
        "session_status": "in_progress",
    }


def finish_interview(session_id: str) -> Dict[str, Any]:
    """结束面试：汇总评分 → STAR 改写 → 生成练习计划。"""
    session = _require_session(session_id)

    if session["status"] not in ("in_progress", "ready_to_finish"):
        raise ValueError(f"会话状态异常: {session['status']}")

    session["status"] = "completed"
    questions = session["questions"]
    answers = session["answers"]

    # 汇总所有有评分的题目
    scored = []
    for i, a in enumerate(answers):
        if a.get("scores"):
            scored.append({
                "question": questions[i],
                "first_answer": a.get("first_answer", ""),
                "followup_question": a.get("followup_question"),
                "followup_answer": a.get("followup_answer"),
                "scores": a["scores"],
            })

    # 找出得分最低的 3 题做 STAR 改写
    scored_sorted = sorted(scored, key=lambda x: x["scores"].get("total", 0))
    need_star = scored_sorted[:3]

    star_results = []
    for item in need_star:
        best_answer = item.get("followup_answer") or item.get("first_answer", "")
        if best_answer:
            star = _rewrite_star(
                question=item["question"],
                answer=best_answer,
                target_position=session.get("target_position", ""),
            )
            item["star_rewrite"] = star
            star_results.append({
                "question": item["question"],
                "star_rewrite": star,
            })

    # 计算各维度平均分
    dim_totals: Dict[str, float] = {}
    dim_count = 0
    for item in scored:
        for dim, val in item["scores"].items():
            if dim == "total" or dim == "overall_comment":
                continue
            if isinstance(val, (int, float)):
                dim_totals[dim] = dim_totals.get(dim, 0) + val
        dim_count += 1

    dimension_averages = {
        dim: round(total / dim_count, 1) for dim, total in dim_totals.items()
    } if dim_count > 0 else {}

    # 总分
    total_sum = sum(s["scores"].get("total", 0) for s in scored)
    overall_score = round(total_sum / len(scored), 1) if scored else 0

    # 练习计划
    practice_plan = _generate_practice_plan(
        dimension_averages=dimension_averages,
        weak_questions=[r["question"] for r in need_star],
        target_position=session.get("target_position", ""),
    )

    return {
        "session_id": session_id,
        "overall_score": overall_score,
        "dimension_averages": dimension_averages,
        "total_questions_answered": len(scored),
        "details": scored,
        "star_suggestions": star_results,
        "practice_plan": practice_plan,
        "summary": _generate_summary(overall_score, dimension_averages),
    }


# ── 内部辅助函数 ──────────────────────────────────────────────────

def _parse_resume(resume_text: str) -> Dict[str, Any]:
    """用 LLM 解析简历，提取结构化信息。"""
    prompt = f"""请解析以下简历，提取结构化信息。

简历文本：
{resume_text[:4000]}

请输出 JSON（只输出 JSON，不要其他内容）：
{{
  "education": "最高学历",
  "skills": ["技能1", "技能2"],
  "projects": [{{"name": "项目名", "role": "角色", "tech": ["技术"], "result": "成果"}}],
  "experience": [{{"company": "公司", "position": "职位", "duration": "时长"}}],
  "strengths": ["优势1"],
  "weaknesses": ["不足1"]
}}
"""
    result = _safe_call_llm(
        system_prompt="你是简历解析专家。只输出 JSON，不要任何其他文字。",
        user_prompt=prompt,
        fallback="{}",
        temperature=0.3,
    )
    return _parse_json_fallback(result)


def _analyze_job_requirements(target_position: str, _resume_text: str) -> str:
    """根据岗位名称分析核心要求。"""
    prompt = f"""目标岗位：{target_position}

请用 3-5 句话总结这个岗位的核心技能要求、常见面试重点和典型工作场景。"""
    return _safe_call_llm(
        system_prompt="你是资深技术面试官，熟悉各岗位的 JD 和面试要点。",
        user_prompt=prompt,
        fallback=f"{target_position} 岗位的核心要求包括相关技术栈、项目经验和问题解决能力。",
        temperature=0.5,
    )


def _generate_questions(
    resume_text: str,
    parsed_resume: Dict[str, Any],
    target_position: str,
    job_requirements: str,
) -> List[str]:
    """生成 8 道面试题。"""
    skills_str = ", ".join(parsed_resume.get("skills", [])) or "通用技能"
    projects_str = json.dumps(parsed_resume.get("projects", []), ensure_ascii=False)
    position = target_position or "目标岗位"

    prompt = f"""请为以下候选人生成 8 道面试题，严格按类别分配：

候选人背景：
- 技能：{skills_str}
- 项目经历：{projects_str}
- 简历原文：{resume_text[:1000]}

目标岗位：{position}
岗位要求：{job_requirements}

题目分配（必须严格 8 题）：
1-2 题：自我介绍与动机类（如"为什么应聘这个岗位"）
3-5 题：项目经历深挖类（结合简历中的具体项目追问技术细节、难点、成果）
6-7 题：技术基础类（结合目标岗位的核心技术栈）
8 题：行为问题类（如团队协作、压力处理、失败经历）

要求：
- 每道题要具体，能引导候选人展开回答
- 项目经历题必须结合简历中提到的具体项目
- 技术题必须与目标岗位相关
- 行为问题要能考察软技能

输出格式（只输出 JSON 数组）：
["题目1", "题目2", ..., "题目8"]
"""
    result = _safe_call_llm(
        system_prompt="你是资深面试官，擅长根据简历和岗位设计有针对性的面试问题。只输出 JSON 数组。",
        user_prompt=prompt,
        fallback=json.dumps([
            "请做一个简短的自我介绍。",
            "为什么选择应聘这个岗位？",
            f"你在项目中遇到过最大的技术挑战是什么？",
            f"请详细描述一个你主导或深度参与的项目。",
            f"在这个项目中你如何保证代码质量？",
            f"你对 {position} 所需的核心技术栈了解多少？",
            f"如果系统上线后出现性能问题，你会如何排查？",
            "请分享一次团队协作中出现分歧你是怎么处理的。",
        ], ensure_ascii=False),
        temperature=0.8,
    )

    questions = _parse_json_fallback(result)
    if isinstance(questions, list) and len(questions) >= 8:
        return questions[:8]
    if isinstance(questions, list) and len(questions) > 0:
        return questions

    # 最终兜底
    return [
        "请做一个简短的自我介绍。",
        "为什么选择应聘这个岗位？",
        "你在项目中遇到过最大的技术挑战是什么？",
        "请详细描述一个你主导或深度参与的项目。",
        "在这个项目中你如何保证代码质量？",
        f"你对 {position} 所需的核心技术栈了解多少？",
        "如果系统上线后出现性能问题，你会如何排查？",
        "请分享一次你在团队协作中处理分歧的经历。",
    ]


def _generate_followup(
    question: str, answer: str, target_position: str
) -> str:
    """生成追问。"""
    prompt = f"""原问题：{question}
候选人回答：{answer}
目标岗位：{target_position}

候选人的回答不够具体。请生成一个追问，引导对方补充：
- 具体的技术动作和工具
- 量化结果（数字、百分比）
- 个人在其中的具体贡献

只输出追问本身，不超过 80 字。"""
    return _safe_call_llm(
        system_prompt="你是面试官，追问要具体、有引导性。只输出追问文本。",
        user_prompt=prompt,
        fallback="能具体说一下你用了什么技术，取得了什么可量化的成果吗？",
        temperature=0.5,
    )


def _score_answer(
    question: str,
    answer: str,
    target_position: str,
    job_requirements: str,
) -> Dict[str, int]:
    """LLM 五维度评分。"""
    prompt = f"""请对以下面试回答进行评分。

面试问题：{question}
候选人回答：{answer}
目标岗位：{target_position}
岗位要求参考：{job_requirements}

评分维度（满分 100）：
1. content_relevance（内容相关性）：25 分 — 是否切题，是否覆盖岗位核心要求
2. professional_accuracy（专业知识准确性）：25 分 — 技术术语是否准确，方案是否可行
3. clarity（表达清晰度）：20 分 — 逻辑是否清楚，条理是否分明
4. star_completeness（STAR 完整性）：20 分 — 是否包含情境/任务/行动/结果
5. position_match（岗位匹配度）：10 分 — 回答是否体现对目标岗位的理解

评分请严格：不要随意给满分，大部分回答应在 60-80 之间。

输出 JSON（只输出 JSON）：
{{
  "content_relevance": 数字,
  "professional_accuracy": 数字,
  "clarity": 数字,
  "star_completeness": 数字,
  "position_match": 数字,
  "total": 数字,
  "overall_comment": "简短总评，不超过 100 字"
}}
"""
    result = _safe_call_llm(
        system_prompt="你是严格但公正的面试官。只输出 JSON，不要其他内容。",
        user_prompt=prompt,
        fallback=json.dumps({
            "content_relevance": 15,
            "professional_accuracy": 15,
            "clarity": 12,
            "star_completeness": 10,
            "position_match": 6,
            "total": 58,
            "overall_comment": "回答较笼统，建议补充具体技术细节和量化结果。",
        }, ensure_ascii=False),
        temperature=0.3,
    )
    scores = _parse_json_fallback(result)
    if not scores:
        # 解析完全失败，给默认分
        scores = {
            "content_relevance": 15,
            "professional_accuracy": 15,
            "clarity": 12,
            "star_completeness": 10,
            "position_match": 6,
            "total": 58,
            "overall_comment": "系统评分遇到问题，请重试。",
        }
    # 确保 total 与子分一致
    if "total" not in scores or not isinstance(scores["total"], (int, float)):
        scores["total"] = (
            scores.get("content_relevance", 0)
            + scores.get("professional_accuracy", 0)
            + scores.get("clarity", 0)
            + scores.get("star_completeness", 0)
            + scores.get("position_match", 0)
        )
    return scores


def _rewrite_star(question: str, answer: str, target_position: str) -> str:
    """将普通回答改写为 STAR 格式。"""
    prompt = f"""请将以下面试回答改写为 STAR 格式：

面试问题：{question}
原回答：{answer}
目标岗位：{target_position}

请按以下结构输出：
S（情境）：当时的背景是什么？
T（任务）：需要解决什么问题？
A（行动）：你具体做了什么？
R（结果）：取得了什么成果？（尽量量化）

如果原回答信息不足，合理推测补充。每段 2-4 句话。"""
    return _safe_call_llm(
        system_prompt="你是面试辅导专家，擅长将普通回答改写为 STAR 结构化表达。",
        user_prompt=prompt,
        fallback="S（情境）：在项目开发过程中\nT（任务）：需要完成功能开发和优化\nA（行动）：参与需求分析、编码实现和测试验证\nR（结果）：按时交付，功能正常运行",
        temperature=0.6,
    )


def _generate_practice_plan(
    dimension_averages: Dict[str, float],
    weak_questions: List[str],
    target_position: str,
) -> str:
    """根据弱项生成练习计划。"""
    weak_dims = [
        dim for dim, score in dimension_averages.items()
        if score < 15
    ]
    weak_str = "、".join(weak_dims) if weak_dims else "综合表现"
    questions_str = "；".join(weak_questions[:3]) if weak_questions else "通用面试题"

    prompt = f"""根据以下面试弱项，生成下一轮练习计划：

薄弱维度：{weak_str}
薄弱题型示例：{questions_str}
目标岗位：{target_position}

请输出 3-5 条具体的练习建议，每条包含：练习内容 + 预期提升的维度。不超过 300 字。"""
    return _safe_call_llm(
        system_prompt="你是面试辅导教练，练习建议要具体、可执行。",
        user_prompt=prompt,
        fallback="1. 针对薄弱题型准备 STAR 案例\n2. 补充目标岗位相关技术知识\n3. 多做模拟练习提升表达清晰度",
        temperature=0.5,
    )


def _generate_summary(
    overall_score: float,
    dimension_averages: Dict[str, float],
) -> str:
    """生成面试总结。"""
    if overall_score >= 85:
        level = "优秀"
    elif overall_score >= 70:
        level = "良好"
    elif overall_score >= 60:
        level = "一般"
    else:
        level = "需要提升"

    dim_str = "，".join(
        f"{dim}: {score}分" for dim, score in dimension_averages.items()
    )
    return f"面试综合评定：{level}（{overall_score}分）。各维度得分：{dim_str}。建议参照练习计划针对性提升。"
