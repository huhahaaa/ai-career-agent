"""简历审核 Agent 单元测试（无需 LLM / 无需数据库）。

使用 --noconftest 运行：
    python -m pytest tests/test_resume_audit.py -q --noconftest
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import app.services.resume_audit as ra
from app.services.resume_audit import (
    audit_resume_text,
    _detect_resume_fields,
    _missing_keywords,
    _normalize_position,
    _score_resume_dimensions,
)

# 强制离线：保证测试稳定、无网络依赖（llm_score 应为 None）
ra._llm_enabled = lambda: False

STRONG_RESUME = (
    "张三\n"
    "邮箱: zhangsan@example.com 电话: 13800001111\n"
    "教育背景：清华大学 计算机科学 本科\n"
    "工作经历：在某科技公司任前端开发，负责 React 组件库建设\n"
    "项目经历一：电商平台前端，主导用 React+Redux 搭建，使页面加载时间从 3.2s 降到 1.1s，转化率提升 18%\n"
    "技能：JavaScript、TypeScript、React、Vue、Webpack、CSS\n"
    "作品集：github.com/zhangsan\n"
)

WEAK_RESUME = "我叫小明，参与过一些项目，负责过相关工作，熟悉一些技术，能力比较强，大概完成了任务。"

BIASED_RESUME = (
    "李四 邮箱 a@b.com 电话 13900002222\n"
    "本科 计算机\n"
    "项目：我独立负责了完美的系统，是业界最优秀的方案，提升了100%效率，绝对没有问题。\n"
)


def test_position_normalization():
    assert _normalize_position("Python 后端工程师") == "后端"
    assert _normalize_position("前端开发") == "前端"
    assert _normalize_position("数据媒体设计") == "数媒"
    assert _normalize_position("") == ""


def test_field_detection_strong():
    fields = _detect_resume_fields(STRONG_RESUME)
    assert fields["email"] is True
    assert fields["phone"] is True
    assert fields["portfolio"] is True
    assert fields["projects"] is True


def test_dimension_scores_present_and_sum():
    dim = _score_resume_dimensions(STRONG_RESUME, "前端")
    scores = dim["dimension_scores"]
    assert set(scores.keys()) == {"completeness", "position_match", "quantification", "clarity", "project_quality"}
    assert sum(scores.values()) == dim["total"]
    for v in scores.values():
        assert 0 <= v <= 25


def test_strong_resume_low_risk():
    result = audit_resume_text(STRONG_RESUME, "前端")
    assert result["risk_level"] == "低"
    assert result["score"] >= 50
    assert result["position_bucket"] == "前端"


def test_weak_resume_high_risk():
    result = audit_resume_text(WEAK_RESUME, "前端")
    assert result["risk_level"] == "高"
    assert result["score"] < 50


def test_position_match_higher_with_keywords():
    strong = audit_resume_text(STRONG_RESUME, "前端")
    weak = audit_resume_text(WEAK_RESUME, "前端")
    assert strong["dimension_scores"]["position_match"] > weak["dimension_scores"]["position_match"]


def test_missing_keywords_frontend():
    result = audit_resume_text(WEAK_RESUME, "前端")
    missing = result["missing_keywords"]
    assert isinstance(missing, list)
    assert len(missing) > 0
    for kw in missing:
        assert kw in ra.POSITION_REQUIRED_KEYWORDS["前端"]


def test_vague_expression_flagged():
    result = audit_resume_text(WEAK_RESUME, "前端")
    assert any("模糊表达" in flag for flag in result["risk_flags"])


def test_biased_expression_flagged():
    result = audit_resume_text(BIASED_RESUME, "算法")
    assert any("夸大风险" in flag for flag in result["risk_flags"])


def test_calibration_fields_present():
    result = audit_resume_text(STRONG_RESUME, "前端")
    assert isinstance(result["rule_score"], int)
    assert 0 <= result["rule_score"] <= 100
    # 离线环境下 LLM 深度审核未启用，llm_score 应为 None
    assert result["llm_score"] is None
    # 维度评分总数应与校准基线一致
    assert sum(result["dimension_scores"].values()) == result["rule_score"]


def test_detected_fields_keys():
    result = audit_resume_text(STRONG_RESUME, "前端")
    for key in ("email", "phone", "education", "experience", "projects", "skills", "portfolio"):
        assert key in result["detected_fields"]


def test_project_quality_low_without_quant():
    weak = audit_resume_text(WEAK_RESUME, "前端")
    assert weak["dimension_scores"]["project_quality"] <= 8
    strong = audit_resume_text(STRONG_RESUME, "前端")
    assert strong["dimension_scores"]["project_quality"] >= 10


def test_suggestions_generated():
    result = audit_resume_text(WEAK_RESUME, "前端")
    assert len(result["suggestions"]) > 0
