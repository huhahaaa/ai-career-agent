from typing import Dict, List


COMMON_SKILLS = [
    "Python",
    "Java",
    "JavaScript",
    "React",
    "Vue",
    "FastAPI",
    "Django",
    "SQL",
    "MySQL",
    "LLM",
    "RAG",
]


def extract_skills(text: str) -> List[str]:
    text_upper = text.upper()
    return [skill for skill in COMMON_SKILLS if skill.upper() in text_upper]


def normalize_job(raw_job: Dict) -> Dict:
    skills = raw_job.get("skills") or []
    if isinstance(skills, str):
        skills = extract_skills(skills)
    return {
        "title": raw_job.get("title", "").strip(),
        "company": raw_job.get("company", "").strip(),
        "location": raw_job.get("location", "").strip(),
        "salary_range": raw_job.get("salary_range", "").strip(),
        "education": raw_job.get("education", "").strip(),
        "experience": raw_job.get("experience", "").strip(),
        "responsibilities": raw_job.get("responsibilities", "").strip(),
        "requirements": raw_job.get("requirements", "").strip(),
        "publish_time": raw_job.get("publish_time", "").strip(),
        "skills": skills,
        "source_site": raw_job.get("source_site", "").strip(),
        "source_link": str(raw_job.get("source_link", "")).strip(),
    }
