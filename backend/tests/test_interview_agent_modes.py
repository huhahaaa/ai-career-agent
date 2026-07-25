from app.services import interview_agent as agent
from app.services.interview_agent import (
    _detect_expression_risks,
    _strip_markdown,
    evaluate_answer,
    finish_interview,
    load_question_bank,
    start_interview,
)


def test_question_bank_loads_expected_data():
    questions = load_question_bank()

    assert len(questions) == 30
    assert len(agent._POSITION_QUESTIONS) == 6
    assert agent.get_question_bank_summary()["position_bank_count"] == 6


def test_interview_modes_generate_distinct_first_questions():
    first_questions = {
        mode: start_interview(
            resume_text="熟悉 Python、FastAPI、React 和项目协作。",
            target_position="Python 后端工程师",
            interview_mode=mode,
        )["question"]
        for mode in ["HR面", "技术面", "压力面", "反馈教练"]
    }

    assert len(set(first_questions.values())) == 4


def test_structured_answer_feedback_and_calibration_summary():
    state = start_interview(
        resume_text="熟悉 Python、FastAPI、SQLAlchemy、pytest 和接口性能优化。",
        target_position="Python 后端工程师",
        interview_mode="技术面",
    )["agent_state"]

    result = evaluate_answer(
        state,
        (
            "我负责 FastAPI 接口开发、SQLAlchemy 数据模型和 pytest 自动化测试，"
            "通过慢查询分析和接口缓存把核心接口响应时间减少 30%，并补充日志方便排查问题。"
        ),
    )
    report = finish_interview(state, session_id="test-session")

    assert result["score"] is not None
    assert result["strengths"]
    assert result["issues"]
    assert result["improvement_suggestions"]
    assert "calibration_summary" in report
    assert report["question_bank_summary"]["total"] == 30


def test_expression_risk_and_markdown_cleanup_helpers():
    vague, biased = _detect_expression_risks("我做了一些工作，效果比较好，绝对没有问题。")

    assert "一些" in vague
    assert "比较好" in vague
    assert "绝对" in biased
    assert _strip_markdown("**重点** `FastAPI`") == "重点 FastAPI"
