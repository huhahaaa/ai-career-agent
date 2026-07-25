import re
from typing import Dict, Iterable, List

from app.services.vector_store import (
    search_similar_jobs,
    upsert_approved_job_embeddings,
    upsert_job_embedding,
)

SEMANTIC_SCORE_WEIGHT = 0.7
SKILL_COVERAGE_SCORE_WEIGHT = 0.3


def build_matching_query(resume_text: str, target_position: str = "") -> str:
    sections = [target_position.strip(), resume_text.strip()]
    return "\n".join(section for section in sections if section)


def _normalize_skill(skill: str) -> str:
    return re.sub(r"\s+", " ", str(skill).strip()).lower()


def _contains_skill(text: str, skill: str) -> bool:
    normalized_skill = _normalize_skill(skill)
    if not normalized_skill:
        return False
    if re.search(r"[a-z0-9+#.]", normalized_skill):
        pattern = r"(?<![a-z0-9+#.])%s(?![a-z0-9+#.])" % re.escape(normalized_skill)
        return re.search(pattern, text, re.IGNORECASE) is not None
    return normalized_skill in text.lower()


def _normalize_job_skills(value: object) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        raw_items = re.split(r"[,，/、\n]", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []

    seen = set()
    skills = []
    for item in raw_items:
        skill = str(item).strip()
        key = _normalize_skill(skill)
        if not skill or key in seen:
            continue
        seen.add(key)
        skills.append(skill)
    return skills


def _skill_coverage_score(matched_skills: List[str], job_skills: List[str]) -> float | None:
    if not job_skills:
        return None
    return round(len(matched_skills) / len(job_skills) * 100, 2)


def _semantic_component_score(raw_score: float) -> float:
    if raw_score <= 0:
        return 0
    return round(min(100, 50 + raw_score * 0.5), 2)


def _weighted_match_score(semantic_score: float, skill_score: float | None) -> float:
    if skill_score is None:
        return round(semantic_score, 2)
    return round(
        semantic_score * SEMANTIC_SCORE_WEIGHT
        + skill_score * SKILL_COVERAGE_SCORE_WEIGHT,
        2,
    )


def _weighted_reason(semantic_score: float, skill_score: float | None) -> str:
    if skill_score is None:
        return "简历与岗位描述的语义匹配分为 %.1f 分" % semantic_score
    return "综合匹配分由语义匹配分 %.1f 和技能覆盖率 %.1f%% 加权得到" % (
        semantic_score,
        skill_score,
    )


def enrich_match_results(resume_text: str, matches: List[Dict]) -> List[Dict]:
    enriched = []
    for match in matches:
        raw_semantic_score = round(float(match.get("score") or 0), 2)
        semantic_score = _semantic_component_score(raw_semantic_score)
        job_skills = _normalize_job_skills(match.get("skills"))
        matched_skills = [
            skill for skill in job_skills if _contains_skill(resume_text, skill)
        ]
        missing_skills = [
            skill for skill in job_skills if skill not in matched_skills
        ]
        skill_score = _skill_coverage_score(matched_skills, job_skills)
        score = _weighted_match_score(semantic_score, skill_score)

        if not job_skills:
            gap_analysis = "岗位技能字段不足，暂无法计算技能缺口。"
            suggestion = "建议先补充岗位技能词，再重新运行匹配。"
        elif missing_skills:
            gap_analysis = "已命中 %s/%s 项技能，缺少：%s。" % (
                len(matched_skills),
                len(job_skills),
                "、".join(missing_skills),
            )
            suggestion = "建议在简历项目或技能栏补充：%s。" % "、".join(missing_skills)
        else:
            gap_analysis = "岗位技能要求已全部命中。"
            suggestion = "可以继续强化项目量化结果和岗位相关经历。"

        enriched.append(
            {
                **match,
                "score": score,
                "semantic_score": semantic_score,
                "skill_coverage_score": skill_score,
                "reason": _weighted_reason(semantic_score, skill_score),
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "gap_analysis": gap_analysis,
                "suggestion": suggestion,
            }
        )
    enriched.sort(key=lambda item: item.get("score", 0), reverse=True)
    return enriched


def match_resume_to_jobs(
    resume_text: str,
    target_position: str = "",
    top_k: int = 5,
) -> List[Dict]:
    query = build_matching_query(resume_text, target_position)
    matches = search_similar_jobs(query=query, top_k=top_k)
    return enrich_match_results(resume_text, matches)


def index_approved_job(job: Dict) -> Dict:
    return upsert_job_embedding(job)


def index_approved_jobs(jobs: Iterable[Dict]) -> Dict:
    return upsert_approved_job_embeddings(jobs)
