from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse, success_response
from app.schemas.speech import TtsRequest, TtsResult
from app.services.speech_synthesis import synthesize_interviewer_speech

router = APIRouter()


@router.post("/tts", response_model=ApiResponse[TtsResult])
def create_tts_audio(
    payload: TtsRequest,
    _: User = Depends(get_current_user),
) -> ApiResponse[TtsResult]:
    result = synthesize_interviewer_speech(payload.text)
    return success_response(TtsResult(**result.__dict__))
