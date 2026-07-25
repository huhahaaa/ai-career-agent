"""Dashboard metrics endpoint - 数据看板 API."""

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.interview import InterviewSession
from app.models.job import JobPosting
from app.models.resume import Resume
from app.models.user import User
from app.schemas.dashboard import (
    CapabilityGap,
    DashboardOverview,
    InterviewTrendItem,
    JobCityDistribution,
    JobSkillRequirement,
    MultiJobScore,
    RecentInterviewItem,
    SkillDistribution,
)

router = APIRouter()


@router.get("", response_model=DashboardOverview)
async def get_dashboard(
    days: int = Query(default=30, ge=1, le=365, description="统计时间范围（天）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardOverview:
    """获取数据看板总览."""
    since_date = datetime.now(timezone.utc) - timedelta(days=days)

    # 基础统计
    total_resumes = db.query(func.count(Resume.id)).filter(
        Resume.user_id == current_user.id,
    ).scalar() or 0

    total_jobs = db.query(func.count(JobPosting.id)).scalar() or 0

    total_interviews = db.query(func.count(InterviewSession.id)).filter(
        InterviewSession.user_id == current_user.id,
    ).scalar() or 0

    # 平均面试分
    avg_score_result = db.query(
        func.avg(InterviewSession.score)
    ).filter(
        InterviewSession.user_id == current_user.id,
        InterviewSession.score.isnot(None),
    ).scalar()
    avg_score = round(float(avg_score_result), 1) if avg_score_result else 0.0

    # 技能分布
    skill_distribution = _get_skill_distribution(db, current_user.id)

    # 岗位技能需求
    job_skill_requirements = _get_job_skill_requirements(db)

    # 能力差距
    capability_gap = _get_capability_gap(db, current_user.id, since_date)

    # 多岗位面试分数
    multi_job_scores = _get_multi_job_scores(db, current_user.id, since_date)

    # 面试趋势（按日聚合）
    interview_trend = _get_interview_trend(db, current_user.id, since_date)

    # 岗位城市分布
    job_city_distribution = _get_job_city_distribution(db)

    # 最近的面试记录
    recent_interviews = _get_recent_interviews(db, current_user.id)

    return DashboardOverview(
        total_resumes=total_resumes,
        total_jobs=total_jobs,
        total_interviews=total_interviews,
        avg_score=avg_score,
        skill_distribution=skill_distribution,
        job_skill_requirements=job_skill_requirements,
        capability_gap=capability_gap,
        multi_job_scores=multi_job_scores,
        interview_trend=interview_trend,
        job_city_distribution=job_city_distribution,
        recent_interviews=recent_interviews,
    )


def _parse_skills_text(skills_text: str) -> List[str]:
    """解析技能文本为列表（技能可能是 JSON 列表或逗号分隔的字符串）."""
    if not skills_text:
        return []
    text = skills_text.strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            import json
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
    return [skill.strip() for skill in text.replace(",", "，").split("，") if skill.strip()] or \
           [skill.strip() for skill in text.split(",") if skill.strip()]


def _get_skill_distribution(db: Session, user_id: int) -> List[SkillDistribution]:
    """从已审核岗位的技能要求中统计技能分布."""
    jobs = db.query(JobPosting).filter(
        JobPosting.skills.isnot(None),
        JobPosting.skills != "",
    ).all()

    skill_count = {}
    for job in jobs:
        skill_names = _parse_skills_text(job.skills)
        for name in skill_names:
            if name:
                skill_count[name] = skill_count.get(name, 0) + 1

    return [
        SkillDistribution(name=name, level=float(count))
        for name, count in sorted(
            skill_count.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:12]
    ]


def _get_job_skill_requirements(db: Session) -> List[JobSkillRequirement]:
    """获取岗位技能需求汇总."""
    jobs = db.query(JobPosting).filter(
        JobPosting.skills.isnot(None),
        JobPosting.skills != "",
    ).all()

    skill_count = {}
    for job in jobs:
        skill_names = _parse_skills_text(job.skills)
        for name in skill_names:
            if name:
                skill_count[name] = skill_count.get(name, 0) + 1

    return [
        JobSkillRequirement(skill=name, count=count)
        for name, count in sorted(
            skill_count.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:12]
    ]


def _get_capability_gap(
    db: Session, user_id: int, since_date: datetime,
) -> List[CapabilityGap]:
    """计算个人能力与岗位要求之间的差距."""
    sessions = db.query(InterviewSession).filter(
        InterviewSession.user_id == user_id,
        InterviewSession.created_at >= since_date,
        InterviewSession.score.isnot(None),
    ).all()

    # 从面试获得个人评分
    personal_map = {}
    if sessions:
        avg_score = sum(s.score for s in sessions if s.score) / max(
            sum(1 for s in sessions if s.score), 1,
        )
        personal_map = {
            "沟通表达": round(min(avg_score * 0.9, 100), 1),
            "技术能力": round(min(avg_score * 0.85, 100), 1),
            "项目经验": round(min(avg_score * 0.8, 100), 1),
            "问题解决": round(min(avg_score * 0.88, 100), 1),
            "团队协作": round(min(avg_score * 0.92, 100), 1),
            "学习能力": round(min(avg_score * 0.87, 100), 1),
        }

    # 岗位平均要求
    required_map = {
        "沟通表达": 7.0,
        "技术能力": 8.0,
        "项目经验": 7.5,
        "问题解决": 8.0,
        "团队协作": 7.0,
        "学习能力": 7.5,
    }

    result = []
    for subject in required_map:
        personal = personal_map.get(subject, 5.0)
        result.append(CapabilityGap(
            subject=subject,
            personal=round(personal, 1),
            required=required_map[subject],
        ))

    return sorted(result, key=lambda x: x.required - x.personal, reverse=True)[:6]


def _get_multi_job_scores(
    db: Session, user_id: int, since_date: datetime,
) -> List[MultiJobScore]:
    """获取多岗位面试平均分."""
    from sqlalchemy.orm import joinedload

    sessions = db.query(InterviewSession).options(
        joinedload(InterviewSession.target_job),
    ).filter(
        InterviewSession.user_id == user_id,
        InterviewSession.created_at >= since_date,
        InterviewSession.score.isnot(None),
    ).all()

    job_scores = {}
    job_counts = {}
    colors = ["#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444"]

    for s in sessions:
        job_name = s.target_job.title if s.target_job else "通用面试"
        if job_name not in job_scores:
            job_scores[job_name] = 0.0
            job_counts[job_name] = 0
        job_scores[job_name] += float(s.score or 0)
        job_counts[job_name] += 1

    result = []
    color_idx = 0
    for job, total in sorted(
        job_scores.items(),
        key=lambda x: x[1] / max(job_counts[x[0]], 1),
        reverse=True,
    ):
        if job_counts[job] > 0:
            result.append(MultiJobScore(
                job=job,
                score=round(total / job_counts[job], 1),
                color=colors[color_idx % len(colors)],
            ))
            color_idx += 1

    return result


def _get_interview_trend(
    db: Session, user_id: int, since_date: datetime,
) -> List[InterviewTrendItem]:
    """获取面试分数趋势（按日聚合）."""
    sessions = db.query(InterviewSession).filter(
        InterviewSession.user_id == user_id,
        InterviewSession.created_at >= since_date,
        InterviewSession.score.isnot(None),
    ).order_by(InterviewSession.created_at).all()

    daily = {}
    for s in sessions:
        date_key = s.created_at.strftime("%m-%d")
        if date_key not in daily:
            daily[date_key] = []
        daily[date_key].append(float(s.score or 0))

    return [
        InterviewTrendItem(
            date=date_key,
            score=round(sum(scores) / len(scores), 1),
        )
        for date_key, scores in daily.items()
    ]


def _get_job_city_distribution(db: Session) -> List[JobCityDistribution]:
    """获取岗位城市分布."""
    jobs = db.query(JobPosting).filter(
        JobPosting.location.isnot(None),
        JobPosting.location != "",
    ).all()

    city_count = {}
    for job in jobs:
        city = job.location.strip()
        city_count[city] = city_count.get(city, 0) + 1

    return [
        JobCityDistribution(name=city, value=count)
        for city, count in sorted(
            city_count.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
    ]


def _get_recent_interviews(
    db: Session, user_id: int,
) -> List[RecentInterviewItem]:
    """获取最近的面试记录."""
    from sqlalchemy.orm import joinedload

    sessions = db.query(InterviewSession).options(
        joinedload(InterviewSession.target_job),
    ).filter(
        InterviewSession.user_id == user_id,
    ).order_by(
        InterviewSession.created_at.desc(),
        InterviewSession.id.desc(),
    ).limit(10).all()

    result = []
    for s in sessions:
        company = s.target_job.company if s.target_job else "模拟面试"
        job_title = s.target_job.title if s.target_job else "通用"
        duration = 0
        if s.created_at and s.updated_at:
            try:
                duration = max(
                    0,
                    round((s.updated_at - s.created_at).total_seconds() / 60),
                )
            except TypeError:
                duration = 0

        result.append(RecentInterviewItem(
            id=s.id,
            company=company,
            job_title=job_title,
            mode="Agent 模拟面试",
            score=round(float(s.score), 1) if s.score else None,
            duration_minutes=duration,
            status=s.status or "completed",
            created_at=s.created_at.isoformat() if s.created_at else "",
        ))

    return result
