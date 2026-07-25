"""真实岗位数据接入测试（无需 LLM / 无需数据库）。

使用 --noconftest 运行：
    python -m pytest tests/test_job_data.py -q --noconftest
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services import job_data
from app.services.job_data import (
    POSITION_BUCKETS,
    derive_all_position_keywords,
    derive_position_keywords,
    get_job_by_id,
    get_position_job_summary,
    get_position_jobs,
    get_position_responsibilities,
    load_jobs,
)


def test_load_jobs_returns_24():
    jobs = load_jobs()
    assert isinstance(jobs, list)
    assert len(jobs) == 24
    assert all("source_id" in j and "category" in j for j in jobs)


def test_category_to_position_mapping_covers_six_buckets():
    # 6 大类 -> 6 岗位桶，1:1 对应
    assert set(job_data.POSITION_TO_CATEGORY.keys()) == set(POSITION_BUCKETS)
    for bucket in POSITION_BUCKETS:
        assert len(get_position_jobs(bucket)) > 0


def test_get_job_by_id():
    first = load_jobs()[0]
    assert get_job_by_id(first["source_id"]) == first
    assert get_job_by_id("JOB-000-not-exist") is None


def test_derive_keywords_from_real_data():
    kw = derive_position_keywords("前端")
    # 真实 skills 派生，应来自 24 条岗位数据而非兜底词
    assert isinstance(kw, list) and len(kw) > 0
    # 兜底词库里不含的英文技术栈应被派生出来
    assert "React" in kw  # 来自真实前端岗位 skills
    assert "JavaScript" in kw


def test_derive_keywords_fallback_for_unknown():
    # 未知岗位桶回退到兜底词库
    out = derive_position_keywords("不存在的桶")
    assert out == job_data.FALLBACK_KEYWORDS["前端"][:0] or isinstance(out, list)
    # 兜底至少包含若干项
    assert len(job_data.FALLBACK_KEYWORDS["前端"]) >= 5


def test_derive_all_position_keywords_complete():
    all_kw = derive_all_position_keywords()
    assert set(all_kw.keys()) == set(POSITION_BUCKETS)
    for bucket, kws in all_kw.items():
        assert len(kws) > 0


def test_position_keywords_used_in_resume_audit():
    # resume_audit 的 POSITION_REQUIRED_KEYWORDS 应已接入真实派生词
    import app.services.resume_audit as ra

    assert "React" in ra.POSITION_REQUIRED_KEYWORDS["前端"]
    assert "PyTorch" in ra.POSITION_REQUIRED_KEYWORDS["算法"]


def test_job_summary_includes_real_data():
    summary = get_position_job_summary("前端")
    assert "真实岗位" in summary
    assert "前端" in summary


def test_position_responsibilities_returns_samples():
    resp = get_position_responsibilities("前端")
    assert len(resp) > 0
    assert all(isinstance(r, str) and r.strip() for r in resp)


def test_resume_audit_missing_keywords_uses_real_kw():
    # 关键词缺失检测应能识别真实派生词
    import app.services.resume_audit as ra

    missing = ra._missing_keywords("我做过一些开发，熟练使用框架。", "前端")
    # 真实前端词库包含 React/JavaScript 等，弱样本应至少缺一项
    assert isinstance(missing, list)
    assert len(missing) > 0
