"""面试相关 API 路由：开始面试、提交回答、结束面试。"""

import logging

from fastapi import APIRouter, HTTPException

from app.schemas.common import MessageResponse
from app.schemas.interview import (
    InterviewAnswerRequest,
    InterviewAnswerResult,
    InterviewFinishResult,
    InterviewQuestion,
    InterviewStartRequest,
)
from app.services.interview_agent import evaluate_answer, finish_interview, start_interview

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start", response_model=InterviewQuestion)
def start(payload: InterviewStartRequest):
    """开始一场模拟面试：解析简历 → 分析岗位 → 生成 8 道题 → 返回第 1 题。"""
    try:
        result = start_interview(
            resume_text=payload.resume_text,
            target_position=payload.target_position,
            target_job_id=payload.target_job_id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("开始面试失败")
        raise HTTPException(status_code=500, detail=f"面试启动失败: {exc}")


@router.post("/{session_id}/answer", response_model=InterviewAnswerResult)
def answer(session_id: str, payload: InterviewAnswerRequest):
    """提交当前题目的回答，返回追问、评分或下一题。"""
    try:
        result = evaluate_answer(session_id=session_id, answer=payload.answer)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("处理回答失败: session_id=%s", session_id)
        raise HTTPException(status_code=500, detail=f"评分失败: {exc}")


@router.post("/{session_id}/finish", response_model=InterviewFinishResult)
def finish(session_id: str):
    """结束面试：汇总评分 → STAR 改写 → 生成练习计划 → 返回完整报告。"""
    try:
        result = finish_interview(session_id=session_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("结束面试失败: session_id=%s", session_id)
        raise HTTPException(status_code=500, detail=f"生成报告失败: {exc}")
