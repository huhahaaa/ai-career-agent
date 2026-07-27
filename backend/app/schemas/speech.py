from pydantic import BaseModel, Field


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)


class TtsResult(BaseModel):
    available: bool = False
    text: str = ""
    provider: str = "browser"
    voice: str = ""
    media_type: str = ""
    audio_base64: str = ""
    fallback_reason: str = ""
