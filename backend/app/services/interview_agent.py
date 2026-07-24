from typing import Dict, Optional
from uuid import uuid4


def start_interview(
    resume_text: str,
    target_position: str = "",
    target_job_id: Optional[int] = None,
) -> Dict:
    tools_used = ["resume_analyzer", "job_matcher", "question_generator"]
    position = target_position or "目标岗位"
    return {
        "session_id": str(uuid4()),
        "question": "请结合一个项目经历，说明你为什么适合%s？" % position,
        "tools_used": tools_used,
    }


def evaluate_answer(session_id: str, answer: str) -> Dict:
    score = 80 if len(answer.strip()) >= 80 else 65
    return {
        "score": score,
        "feedback": "回答已记录。建议补充具体场景、行动和量化结果。",
        "next_question": "如果项目上线后出现性能问题，你会如何定位并优化？",
    }
