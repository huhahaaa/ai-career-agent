"""
简历审核服务 - 基于规则的本地分析
"""
from typing import Dict, List

VAGUE_PHRASES = ["熟悉", "了解", "参与", "负责相关", "具有一定"]


def _find_vague_phrases(resume_text: str) -> List[str]:
    return [phrase for phrase in VAGUE_PHRASES if phrase in resume_text]


def audit_resume_text(resume_text: str, target_position: str = "") -> Dict:
    """审核简历文本，返回评分和建议"""
    vague_flags = _find_vague_phrases(resume_text)
    score = max(60, 90 - len(vague_flags) * 5)
    suggestions = [
        "补充项目背景、个人职责、技术动作和量化结果",
        "把笼统描述改为 STAR 结构（情境-任务-行动-结果）",
        "根据目标岗位补充关键词",
    ]
    if target_position:
        suggestions.append(f"围绕「{target_position}」调整项目排序和技能展示")
    return {
        "score": score,
        "risk_flags": vague_flags,
        "suggestions": suggestions,
        "missing_keywords": [],
    }


def parse_resume_text(resume_text: str) -> Dict:
    """解析简历，提取结构化信息（简单规则版）"""
    return {
        "name": "未识别",
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "summary": "请手动完善简历信息",
    }
