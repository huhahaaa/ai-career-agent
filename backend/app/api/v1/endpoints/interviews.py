from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.interview import (
    InterviewAnswerRequest,
    InterviewAnswerResult,
    InterviewQuestion,
    InterviewStartRequest,
)
from app.services.interview_agent import evaluate_answer, start_interview

router = APIRouter()


@router.post("/start", response_model=ApiResponse[InterviewQuestion])
def start(
    payload: InterviewStartRequest,
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[InterviewQuestion]:
    result = start_interview(
        resume_text=payload.resume_text,
        target_position=payload.target_position,
        target_job_id=payload.target_job_id,
    )
    return success_response(InterviewQuestion.model_validate(result))


@router.post(
    "/{session_id}/answer",
    response_model=ApiResponse[InterviewAnswerResult],
)
def answer(
    session_id: str,
    payload: InterviewAnswerRequest,
    _current_user: User = Depends(get_current_user),
) -> ApiResponse[InterviewAnswerResult]:
    result = evaluate_answer(session_id=session_id, answer=payload.answer)
    return success_response(InterviewAnswerResult.model_validate(result))
