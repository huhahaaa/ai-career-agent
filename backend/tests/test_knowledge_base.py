from app.services.knowledge_base import (
    knowledge_overview,
    role_profile_context,
    role_profile_gap,
)


def test_text_knowledge_base_loads_role_profiles_and_cases():
    overview = knowledge_overview()

    assert overview["role_profiles"]["count"] >= 6
    assert "后端开发" in overview["role_profiles"]["roles"]
    assert overview["failure_cases"]["count"] >= 6
    assert overview["data_quality_cases"]["count"] >= 10
    assert overview["clean_jobs"]["count"] == 24
    assert overview["chinese_jobs"]["count"] == 100
    assert overview["chinese_jobs"]["unique_source_id_count"] == 100
    assert "resume_audit" in overview["role_profiles"]["used_by"]


def test_role_profile_gap_uses_must_have_and_evidence_signals():
    gap = role_profile_gap(
        "Python FastAPI REST API SQL 项目，负责接口开发和数据库设计。",
        "Python 后端实习生",
    )

    assert gap["role"] == "后端开发"
    assert "REST API" not in gap["missing_must_have"]
    assert "异常处理" in gap["missing_must_have"]
    assert "测试覆盖" in gap["evidence_signals"]
    assert "必备能力" in role_profile_context("Python 后端实习生")
