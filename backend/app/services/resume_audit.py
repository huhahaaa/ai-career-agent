from typing import Dict, List


VAGUE_PHRASES = ["熟悉", "了解", "参与", "负责相关", "具有一定"]


def _find_vague_phrases(resume_text: str) -> List[str]:
    return [phrase for phrase in VAGUE_PHRASES if phrase in resume_text]


def audit_resume_text(resume_text: str, target_position: str = "") -> Dict:
    vague_flags = _find_vague_phrases(resume_text)
    score = max(60, 90 - len(vague_flags) * 5)
    suggestions = [
        "补充项目背景、个人职责、技术动作和量化结果",
        "把笼统描述改为 STAR 结构",
        "根据目标岗位补充关键词",
    ]
    if target_position:
        suggestions.append("围绕 %s 调整项目排序和技能展示" % target_position)
    return {
        "score": score,
        "risk_flags": vague_flags,
        "suggestions": suggestions,
        "missing_keywords": [],
    }

