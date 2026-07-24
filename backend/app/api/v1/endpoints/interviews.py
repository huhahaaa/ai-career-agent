from fastapi import APIRouter

from app.schemas.interview import (
    InterviewAnswerRequest,
    InterviewAnswerResult,
    InterviewQuestion,
    InterviewStartRequest,
)
from app.services.interview_agent import evaluate_answer, start_interview

router = APIRouter()


@router.post("/start", response_model=InterviewQuestion)
def start(payload: InterviewStartRequest):
    return start_interview(
        resume_text=payload.resume_text,
        target_position=payload.target_position,
        target_job_id=payload.target_job_id,
    )


@router.post("/{session_id}/answer", response_model=InterviewAnswerResult)
def answer(session_id: str, payload: InterviewAnswerRequest):
    return evaluate_answer(session_id=session_id, answer=payload.answer)

