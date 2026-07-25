"""4 号成员（简历审核与面试 Agent）的面试 Agent 单元测试。

覆盖：多面试模式、岗位感知出题、低质量/过短/信息不足的兜底与追问、
空泛表达识别、评分校准汇总，以及 Prompt 去 Markdown。
无 API Key 时自动走 mock 兜底，保证测试稳定可独立运行。
"""
import pytest

from app.services import interview_agent as ia
from app.services.interview_agent import (
    _strip_markdown,
    _detect_expression_risks,
    _normalize_position,
    start_interview,
    evaluate_answer,
    finish_interview,
    load_question_bank,
)


# ── 题库加载（修复：parents[4] -> parents[3] 后题库应可正常加载） ──────────
def test_question_bank_loads_thirty_questions_and_six_position_banks():
    questions = load_question_bank()
    assert len(questions) == 30
    assert len(ia._POSITION_QUESTIONS) == 6


def test_question_bank_summary_includes_positions():
    summary = ia.get_question_bank_summary()
    assert summary["total"] == 30
    assert set(summary["positions"].keys()) == set(ia.DEFAULT_POSITIONS)
    assert summary["position_bank_count"] == 6


# ── 多面试模式 ────────────────────────────────────────────────────────
def test_interview_mode_generates_mode_specific_first_question():
    questions = {}
    for mode in ["HR面", "技术面", "压力面", "反馈教练"]:
        result = start_interview(resume_text="熟悉 Python 与前端开发。", interview_mode=mode)
        assert result["interview_mode"] == mode
        assert result["question"]
        questions[mode] = result["question"]
    # 四种模式应产生四个不同的首题，证明按模式区分出题
    assert len(set(questions.values())) == 4


def test_unknown_interview_mode_fallback_to_default():
    result = start_interview(resume_text="测试简历", interview_mode="不存在的模式")
    assert result["interview_mode"] == ia.DEFAULT_INTERVIEW_MODE


def test_start_interview_returns_expected_number_of_questions():
    result = start_interview(resume_text="测试简历", interview_mode="技术面")
    assert result["total_questions"] >= 8


# ── 岗位感知出题（需求 #14：按岗位生成不同题库） ───────────────────────
def test_frontend_position_uses_position_bank():
    result = start_interview(resume_text="熟悉 Vue 和 React。", target_position="前端工程师")
    assert "重排" in result["question"] or "reflow" in result["question"]


def test_backend_position_uses_position_bank():
    result = start_interview(resume_text="熟悉 Java 后端。", target_position="后端开发")
    assert "索引" in result["question"] or "事务" in result["question"]


def test_position_normalization():
    assert _normalize_position("前端工程师") == "前端"
    assert _normalize_position("Backend Developer") == "后端"
    assert _normalize_position("数字媒体设计师") == "数媒"
    assert _normalize_position("") == ""


# ── 低质量 / 过短 / 信息不足的兜底与追问（任务书第 5 条） ────────────────
def _answer_until_finished(state, answer):
    """反复提交同一回答直到结束，返回最后一个真正被打分的回答（非终止态）。"""
    last = None
    for _ in range(len(state["questions"]) + 2):
        res = evaluate_answer(state, answer)
        if res.get("session_status") != "ready_to_finish":
            last = res
        if res.get("session_status") == "ready_to_finish":
            break
    return last


def test_short_answer_triggers_followup():
    state = start_interview(resume_text="测试", interview_mode="技术面")["agent_state"]
    result = evaluate_answer(state, "还行吧")
    assert result["is_followup"] is True
    assert result["followup_question"]


def test_low_quality_answer_is_scored_low_or_flagged():
    state = start_interview(resume_text="测试", interview_mode="技术面")["agent_state"]
    # 第一轮过短 -> 追问；第二轮仍空泛 -> 评分
    evaluate_answer(state, "还行吧")
    result = evaluate_answer(state, "嗯，大概做了一些吧")
    scores = result["dimension_scores"]
    assert scores is not None
    # 至少某一维度被规则压低，或 issue 中标识了表达风险
    low_dim = any(scores.get(k, 99) <= 10 for k in ia.DIMENSION_MAX)
    assert low_dim or bool(scores.get("issues"))


def test_empty_or_whitespace_answer_triggers_followup():
    state = start_interview(resume_text="测试", interview_mode="技术面")["agent_state"]
    result = evaluate_answer(state, "   ")
    assert result["is_followup"] is True
    assert result["followup_question"]


def test_consecutive_low_quality_answers_still_scored():
    state = start_interview(resume_text="测试", interview_mode="技术面")["agent_state"]
    # 每轮：先过短触发追问，再补一句仍空泛 -> 得到评分
    evaluate_answer(state, "不知道")            # idx0 追问
    r1 = evaluate_answer(state, "不太清楚")     # idx0 评分
    evaluate_answer(state, "没什么可说的")       # idx1 追问
    r2 = evaluate_answer(state, "真的没做啥")    # idx1 评分
    assert r1["dimension_scores"] is not None
    assert r2["dimension_scores"] is not None
    assert r1["score"] is not None


def test_information_insufficient_answer_flags_vague_expression():
    state = start_interview(resume_text="测试", interview_mode="技术面")["agent_state"]
    # 有料（性能 + 量化）且超过 50 字，避免触发追问；用于验证空泛表达识别
    result = evaluate_answer(
        state,
        "在上一个项目中，我负责前端性能优化，做了一些接口联调，差不多都完成了核心模块，"
        "性能提升 30%，整体感觉比较好，后续会继续打磨细节。",
    )
    scores = result["dimension_scores"]
    assert scores is not None
    assert "一些" in scores["vague_flags"]
    assert "差不多" in scores["vague_flags"]
    assert scores["biased_flags"] == []


# ── 空泛 / 夸大表达识别（需求 #15）────────────────────────────────────
def test_vague_phrase_detection():
    vague, biased = _detect_expression_risks("我做了一些工作，感觉比较好，差不多都行。")
    assert "一些" in vague
    assert "比较好" in vague


def test_biased_phrase_not_false_positive_on_normal_words():
    # “第一轮回答”不应被误判为夸大（曾误命中“第一”）
    vague, biased = _detect_expression_risks("第一轮回答还行吧")
    assert biased == []


def test_biased_phrase_detection():
    vague, biased = _detect_expression_risks("我绝对是唯一的完美人选，没有缺点。")
    assert "绝对" in biased
    assert "唯一" in biased
    assert "完美" in biased


# ── 结构化评分反馈字段 ───────────────────────────────────────────────
def test_score_result_has_required_fields():
    state = start_interview(resume_text="测试", interview_mode="技术面")["agent_state"]
    result = _answer_until_finished(state, "我使用 React 负责前端开发，性能提升 30%，通过单元测试保证质量。")
    assert result["score"] is not None
    assert result["strengths"] != ""
    assert result["issues"] != ""
    assert result["improvement_suggestions"] != ""


# ── 评分校准汇总（进阶 #2）─────────────────────────────────────────
def test_finish_interview_returns_calibration_summary():
    state = start_interview(
        resume_text="熟悉 React 与 Python。", target_position="前端", interview_mode="技术面"
    )["agent_state"]
    for _ in range(len(state["questions"]) + 2):
        res = evaluate_answer(state, "我使用 React 负责前端组件开发，性能提升 30%，通过单元测试保证质量。")
        if res.get("session_status") == "ready_to_finish":
            break
    report = finish_interview(state, session_id="test-session")
    assert "calibration_summary" in report
    cal = report["calibration_summary"]
    assert "agent_avg_score" in cal
    assert "rule_avg_score" in cal


# ── Prompt 去 Markdown（任务书要求不输出 Markdown 符号）────────────────
def test_strip_markdown_removes_symbols():
    assert _strip_markdown("**重点** 内容") == "重点 内容"
    assert _strip_markdown("# 标题") == "标题"
    assert _strip_markdown("`code`") == "code"


def test_score_result_has_no_markdown_in_feedback():
    state = start_interview(resume_text="测试", interview_mode="技术面")["agent_state"]
    result = _answer_until_finished(state, "我使用 React 负责前端开发，性能提升 30%。")
    assert "**" not in result["strengths"]
    assert "**" not in result["issues"]
