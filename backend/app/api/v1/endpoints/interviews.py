"""
面试 API 端点
"""
import logging

from fastapi import APIRouter, HTTPException

from app.schemas.interview import (
    InterviewAnswerRequest,
    InterviewAnswerResult,
    InterviewStartRequest,
)
from app.services.interview_agent import (
    evaluate_answer,
    start_interview,
    get_session_history,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/start")
async def start(payload: InterviewStartRequest):
    """开始一场新的模拟面试"""
    try:
        result = start_interview(
            resume_text=payload.resume_text,
            target_position=payload.target_position,
            target_job_id=payload.target_job_id,
        )
        return {
            "id": result["session_id"],
            "session_id": result["session_id"],
            "status": "started",
            "question": result["question"],
            "messages": [{"role": "interviewer", "content": result["question"]}],
        }
    except Exception as e:
        logger.error("Failed to start interview: %s", e)
        raise HTTPException(status_code=500, detail=f"启动面试失败: {str(e)}")


@router.post("/{session_id}/answer", response_model=InterviewAnswerResult)
async def answer(session_id: str, payload: InterviewAnswerRequest):
    """提交回答并获取评分和下一题"""
    try:
        result = evaluate_answer(
            session_id=session_id,
            answer=payload.answer,
        )
        return result
    except Exception as e:
        logger.error("Failed to evaluate answer: %s", e)
        raise HTTPException(status_code=500, detail=f"评估回答失败: {str(e)}")


@router.get("/{session_id}/history")
async def history(session_id: str):
    """获取会话历史记录"""
    try:
        messages = get_session_history(session_id)
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史失败: {str(e)}")
