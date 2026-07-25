"""真实岗位数据加载与岗位感知派生。

读取 ``data/processed/jobs_clean.jsonl``（24 条已清洗岗位，6 大类），
为简历审核 Agent 与面试 Agent 提供：

  * 按岗位桶（前端/后端/产品/运营/数媒/算法）聚合的真实岗位列表；
  * 自动派生的岗位关键词库（基于真实岗位的 skills / requirements / responsibilities）；
  * 可引用的真实职责与要求摘要（用于面试出题与岗位要求分析）。

所有函数均为离线可用、无 LLM 依赖；数据缺失时回退到内置兜底词库，保证 Agent 不崩。
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 数据中的岗位大类 -> 标准岗位桶（与 interview_agent.DEFAULT_POSITIONS 1:1 对应）
CATEGORY_TO_POSITION: Dict[str, str] = {
    "前端开发": "前端",
    "后端开发": "后端",
    "产品经理": "产品",
    "运营": "运营",
    "数字媒体/内容": "数媒",
    "算法/机器学习": "算法",
}
POSITION_TO_CATEGORY: Dict[str, str] = {v: k for k, v in CATEGORY_TO_POSITION.items()}

# 标准岗位桶顺序
POSITION_BUCKETS: List[str] = ["前端", "后端", "产品", "运营", "数媒", "算法"]

# 数据文件位置：本文件位于 backend/app/services/，向上三级到项目根再进入 data/processed
_JOBS_PATH = Path(__file__).resolve().parents[3] / "data" / "processed" / "jobs_clean.jsonl"

# 兜底关键词库（仅在真实数据不可用时使用，与历史硬编码语义保持一致）
FALLBACK_KEYWORDS: Dict[str, List[str]] = {
    "前端": ["JavaScript", "TypeScript", "React", "Vue", "CSS", "HTML", "Webpack", "工程化", "浏览器", "响应式"],
    "后端": ["Python", "Java", "Go", "数据库", "MySQL", "Redis", "接口", "微服务", "并发", "事务"],
    "产品": ["需求", "原型", "PRD", "用户", "数据分析", "优先级", "竞品", "埋点", "B端", "C端"],
    "运营": ["增长", "转化率", "留存", "活动", "内容", "社群", "ROI", "漏斗", "渠道", "用户画像"],
    "算法": ["Python", "机器学习", "深度学习", "模型", "特征", "训练", "评估", "调参", "NLP", "推荐"],
    "数媒": ["剪辑", "PR", "AE", "摄影", "排版", "交互", "动效", "Figma", "设计", "新媒体"],
}

_JOBS_CACHE: Optional[List[Dict[str, Any]]] = None


def load_jobs() -> List[Dict[str, Any]]:
    """加载 24 条清洗岗位数据（带内存缓存）。"""
    global _JOBS_CACHE
    if _JOBS_CACHE is not None:
        return _JOBS_CACHE
    jobs: List[Dict[str, Any]] = []
    try:
        raw = _JOBS_PATH.read_text(encoding="utf-8")
    except Exception as exc:  # 文件缺失/编码异常等均回退
        logger.warning("未能加载岗位数据 (%s)：%s", _JOBS_PATH, exc)
        _JOBS_CACHE = jobs
        return jobs
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            jobs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    logger.info("已加载 %d 条岗位数据：%s", len(jobs), _JOBS_PATH)
    _JOBS_CACHE = jobs
    return jobs


def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    """按 source_id（真实岗位数据中的岗位编号）精确取一条真实岗位。"""
    if not job_id:
        return None
    for j in load_jobs():
        if j.get("source_id") == job_id:
            return j
    return None


def get_position_jobs(position_bucket: str) -> List[Dict[str, Any]]:
    """返回某岗位桶下的真实岗位列表（空字符串/未知桶返回空）。"""
    category = POSITION_TO_CATEGORY.get(position_bucket)
    if not category:
        return []
    return [j for j in load_jobs() if j.get("category") == category]


def _category_jobs(category: str) -> List[Dict[str, Any]]:
    return [j for j in load_jobs() if j.get("category") == category]


def derive_position_keywords(position_bucket: str, top_n: int = 12) -> List[str]:
    """基于真实岗位数据自动派生某岗位桶的关键词库。

    使用岗位 ``skills`` 字段（已清洗、可解释）按出现频次排序取 Top-N；
    ``skills`` 缺失/为空时回退到 ``FALLBACK_KEYWORDS``。
    """
    category = POSITION_TO_CATEGORY.get(position_bucket)
    jobs = _category_jobs(category) if category else []
    if not jobs:
        return list(FALLBACK_KEYWORDS.get(position_bucket, []))

    counter: Counter = Counter()
    for j in jobs:
        for kw in j.get("skills", []) or []:
            if isinstance(kw, str) and kw.strip():
                counter[kw.strip()] += 1
    derived = [k for k, _ in counter.most_common(top_n)]
    return derived if derived else list(FALLBACK_KEYWORDS.get(position_bucket, []))


def derive_all_position_keywords() -> Dict[str, List[str]]:
    """派生全部 6 个岗位桶的关键词库（真实数据优先，缺桶回退）。"""
    return {pos: derive_position_keywords(pos) for pos in POSITION_BUCKETS}


def get_position_responsibilities(position_bucket: str, job_id: Optional[str] = None, max_n: int = 6) -> List[str]:
    """返回该岗位桶/指定岗位的真实职责片段，用于面试出题与岗位要求分析。"""
    target: Optional[Dict[str, Any]] = get_job_by_id(job_id) if job_id else None
    jobs = [target] if target is not None else get_position_jobs(position_bucket)
    out: List[str] = []
    for j in jobs:
        resp = j.get("responsibilities")
        items = resp if isinstance(resp, list) else ([resp] if isinstance(resp, str) else [])
        for item in items:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        if len(out) >= max_n:
            break
    return out[:max_n]


def get_position_job_summary(position_bucket: str, job_id: Optional[str] = None) -> str:
    """生成可引用的真实岗位摘要（用于面试出题 / 岗位要求分析）。

    若给定 job_id 且命中，则聚焦该条岗位；否则聚合该岗位桶下所有真实岗位。
    """
    target: Optional[Dict[str, Any]] = get_job_by_id(job_id) if job_id else None
    if target is None:
        jobs = get_position_jobs(position_bucket)
        if not jobs:
            return f"暂无'{position_bucket}'方向真实岗位数据，按通用能力评估。"
        category = POSITION_TO_CATEGORY.get(position_bucket, position_bucket)
        label = f"{category}方向"
    else:
        jobs = [target]
        label = f"岗位「{target.get('title', target.get('source_id', ''))}」"

    responsibilities: List[str] = []
    requirements: List[str] = []
    skills: List[str] = []
    for j in jobs:
        resp = j.get("responsibilities")
        if isinstance(resp, list):
            responsibilities.extend(resp)
        elif isinstance(resp, str):
            responsibilities.append(resp)
        reqs = j.get("requirements")
        if isinstance(reqs, list):
            requirements.extend(reqs)
        elif isinstance(reqs, str):
            requirements.append(reqs)
        skills.extend([s for s in (j.get("skills", []) or []) if isinstance(s, str)])

    parts: List[str] = [f"【{label}真实岗位画像】"]
    if responsibilities:
        sample = responsibilities[:4]
        parts.append("典型职责：" + "；".join(sample))
    if requirements:
        sample = requirements[:4]
        parts.append("典型要求：" + "；".join(sample))
    if skills:
        uniq = list(dict.fromkeys(skills))[:12]
        parts.append("高频技能：" + "、".join(uniq))
    return "\n".join(parts)


if __name__ == "__main__":
    for bucket in POSITION_BUCKETS:
        print(f"\n=== {bucket} ===")
        print("关键词：", derive_position_keywords(bucket))
        print(get_position_job_summary(bucket))
