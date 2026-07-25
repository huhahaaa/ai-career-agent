import re
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.vector_store import search_similar_jobs

router = APIRouter()


class MatchRequest(BaseModel):
    resume_text: str
    target_position: str = ""
    top_k: int = 5


def extract_skills_from_text(text: str) -> list:
    """从文本中提取关键词（简单版本：用逗号/空格/换行切分，再匹配常见技能）"""
    # 一份常见技能列表（你可以自己扩充）
    common_skills = ["Python", "Java", "C++", "JavaScript", "TypeScript", "Go", "Rust",
                     "Spring", "Spring Boot", "Django", "Flask", "FastAPI", "React", "Vue",
                     "Angular", "Node.js", "MySQL", "PostgreSQL", "MongoDB", "Redis",
                     "Elasticsearch", "Docker", "Kubernetes", "AWS", "PyTorch", "TensorFlow",
                     "Hadoop", "Spark", "Kafka", "Git", "Linux", "Nginx", "项目管理",
                     "敏捷开发", "Scrum", "团队管理", "微服务", "Redis", "MySQL"]

    found = []
    for skill in common_skills:
        # 用正则匹配，防止 "Java" 匹配到 "JavaScript" 里的 "Java"
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            found.append(skill)
    return found


def enrich_match_results(resume_text: str, matches: list) -> list:
    """为匹配结果增加技能缺口分析"""
    resume_skills = extract_skills_from_text(resume_text)
    print(f"📋 从简历中提取的技能: {resume_skills}")

    enriched = []
    for idx, match in enumerate(matches):
        # 从 metadatas 里拿 skills（注意：ChromaDB 存的是列表，拿出来可能变成字符串）
        job_skills = match.get('skills', [])
        print(f"🔧 岗位 {idx+1} ({match.get('title')}) 的 skills 字段: {job_skills}, 类型: {type(job_skills)}")
        # 如果 job_skills 是字符串（比如 "Python, Django"），拆成列表
        if isinstance(job_skills, str):
            job_skills = [s.strip() for s in job_skills.split(',') if s.strip()]

        # 计算匹配和缺失的技能
        matched = [s for s in job_skills if s in resume_skills]
        missing = [s for s in job_skills if s not in resume_skills]

        # 生成缺口分析
        if missing:
            gap = f"缺少 {len(missing)} 项技能：{', '.join(missing)}"
            suggestion = f"建议补充：{', '.join(missing)}"
        else:
            gap = "技能匹配良好 ✅"
            suggestion = "继续保持"

        # 构造增强后的结果
        enriched.append({
            "job_id": match.get("job_id"),
            "title": match.get("title"),
            "company": match.get("company"),
            "source_link": match.get("source_link"),
            "score": match.get("score"),
            "matched_skills": matched,
            "missing_skills": missing,
            "gap_analysis": gap,
            "suggestion": suggestion,
            "reason": match.get("reason"),
        })

    return enriched


@router.post("/run")
def run_matching(payload: MatchRequest):
    if not payload.resume_text.strip():
        raise HTTPException(status_code=400, detail="简历文本不能为空")

    # 1. 先执行向量检索
    results = search_similar_jobs(payload.resume_text, top_k=payload.top_k)
    print("🔍 原始匹配结果:", results)
    # 2. 再增加技能缺口分析
    enriched = enrich_match_results(payload.resume_text, results)

    return {"matches": enriched}



@router.get("/skill-taxonomy", response_model=List[str])
def skill_taxonomy():
    return ["Python", "FastAPI", "React", "SQL", "LLM", "RAG", "数据清洗", "岗位审核"]
