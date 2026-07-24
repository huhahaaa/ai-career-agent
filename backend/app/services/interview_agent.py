"""
面试 Agent - 基于规则的模拟面试引擎
"""
from typing import Dict, List
from uuid import uuid4

# 内存中的会话状态（生产环境应换 Redis/DB）
_sessions: Dict[str, Dict] = {}

# 多阶段面试题库
STAGE_QUESTIONS = {
    "intro": [
        "请简单介绍一下你自己，包括你的技术背景和主要技术栈。",
        "能说说你为什么选择这个方向吗？",
    ],
    "technical": [
        "能详细说说你在项目中用到的核心技术吗？为什么选择这些技术？",
        "说说你对前端/后端架构的理解，你在实际项目中是如何应用的？",
        "如果让你从零搭建一个项目，你会如何规划技术栈和架构？",
    ],
    "project": [
        "请详细介绍一个你最有成就感的项目。遇到了哪些难题，如何解决的？",
        "你简历中的项目里，哪个让你学到了最多东西？具体说说。",
    ],
    "architecture": [
        "假设要设计一个高并发系统，你会从哪些方面考虑？",
        "你了解哪些设计模式？在实际项目中用过哪些？",
    ],
    "behavioral": [
        "在团队协作中，当你和同事有技术分歧时怎么处理？",
        "你最近在学习什么新技术？为什么选择它？",
        "你未来的职业规划是怎样的？",
    ],
    "closing": [
        "感谢你的分享，面试到这里基本结束了。你有什么想问我的吗？",
    ],
}

FEEDBACKS = {
    "intro": ["自我介绍很清晰。"],
    "technical": ["技术理解不错。"],
    "project": ["项目经验丰富，描述有条理。"],
    "architecture": ["对架构有一定理解。"],
    "behavioral": ["沟通表达清晰。"],
    "closing": ["感谢参与。"],
}


def _get_session(session_id: str) -> Dict:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "history": [],
            "resume_text": "",
            "target_position": "",
            "stage": "intro",
            "turn_count": 0,
            "total_score": 0,
        }
    return _sessions[session_id]


def start_interview(
    resume_text: str = "",
    target_position: str = "",
    target_job_id: str = "",
) -> Dict:
    """开始一轮新面试"""
    session_id = str(uuid4())
    position = target_position or "目标岗位"
    session = _get_session(session_id)
    session["resume_text"] = resume_text
    session["target_position"] = position

    q = f"你好！欢迎参加本次AI模拟面试。首先请结合你的经历，简单介绍一下自己，并说明你为什么适合{position}？"
    session["history"].append({"role": "interviewer", "content": q})
    session["turn_count"] = 1

    return {
        "session_id": session_id,
        "question": q,
        "tools_used": ["template"],
    }


def evaluate_answer(session_id: str, answer: str) -> Dict:
    """评估用户回答并生成下一题"""
    session = _get_session(session_id)
    session["history"].append({"role": "candidate", "content": answer})
    session["turn_count"] += 1

    # 简单评分：根据回答长度
    score = min(90, 50 + len(answer) // 10)
    feedback = FEEDBACKS.get(session["stage"], ["回答已记录。"])[0]
    session["total_score"] += score

    # 切换阶段
    stages = ["intro", "technical", "technical", "project", "project", "architecture", "behavioral", "closing"]
    idx = min(session["turn_count"] - 2, len(stages) - 1)
    session["stage"] = stages[idx]

    questions = STAGE_QUESTIONS.get(session["stage"], STAGE_QUESTIONS["closing"])
    q_idx = (session["turn_count"] - 1) % len(questions)
    next_q = questions[q_idx]

    if session["turn_count"] >= 10:
        next_q = "面试到此结束，感谢你的参与！有什么想问我们的吗？"
        _cleanup_session(session_id)

    session["history"].append({"role": "interviewer", "content": next_q})

    return {
        "score": score,
        "feedback": feedback,
        "next_question": next_q,
    }


def chat_message(session_id: str, message: str) -> Dict:
    """通用聊天接口"""
    return evaluate_answer(session_id, message)


def get_session_history(session_id: str) -> List[Dict]:
    """获取会话历史"""
    session = _sessions.get(session_id, {})
    return session.get("history", [])


def _cleanup_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]
