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


def test_followup_points_out_missing_question_requirements():
    question = (
        "请简要介绍你自己，并说明为什么你对 Python 后端实习生岗位感兴趣？"
        "结合你的 FastAPI 和 AI 面试陪练项目经验，谈谈你如何理解后端在 AI 自动化平台中的价值。"
    )
    state = {
        "questions": [question],
        "current_index": 0,
        "answers": [{}],
        "target_position": "Python 后端实习生",
        "interview_mode": "技术面",
        "job_requirements": "",
    }

    result = evaluate_answer(
        state,
        "你好，我是本项目的后端负责人，主要负责 FastAPI 接口、数据库设计、用户认证和岗位匹配接口。",
    )

    assert result["is_followup"] is True
    assert result["score"] is None
    assert "题目要点覆盖不足" in result["feedback"]
    assert "感兴趣" in result["feedback"]
    assert "价值" in result["feedback"]


def test_missing_question_requirements_reduce_relevance_score(monkeypatch):
    monkeypatch.setattr(agent, "_llm_enabled", lambda: False)
    question = (
        "请说明为什么你对 Python 后端岗位感兴趣，并谈谈后端在 AI 自动化平台中的价值。"
    )

    scores = agent._score_answer(
        question=question,
        answer="我负责 FastAPI 接口、SQLAlchemy 数据模型和用户认证，也参与了岗位匹配接口开发。",
        target_position="Python 后端实习生",
        job_requirements="",
    )

    assert scores["content_relevance"] <= 12
    assert scores["missing_question_requirements"]
    assert "漏答" in scores["issues"]


def test_expression_risk_and_markdown_cleanup_helpers():
    vague, biased = _detect_expression_risks("我做了一些工作，效果比较好，绝对没有问题。")

    assert "一些" in vague
    assert "比较好" in vague
    assert "绝对" in biased
    assert _strip_markdown("**重点** `FastAPI`") == "重点 FastAPI"
