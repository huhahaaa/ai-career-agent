import base64
import asyncio
import re
import uuid
from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class SpeechSynthesisResult:
    available: bool
    text: str
    provider: str
    voice: str = ""
    media_type: str = ""
    audio_base64: str = ""
    fallback_reason: str = ""


def normalize_interviewer_speech_text(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    followup_match = re.search(r"追问[:：]\s*(.+)$", cleaned, flags=re.S)
    if followup_match:
        cleaned = followup_match.group(1)
    else:
        question_matches = list(
            re.finditer(r"第\s*\d+\s*/\s*\d+\s*题[:：]\s*(.+)$", cleaned, flags=re.S)
        )
        if question_matches:
            cleaned = question_matches[-1].group(1)
        elif "本轮题目已完成" in cleaned:
            cleaned = "本轮题目已完成，可以结束面试生成报告。"

    cleaned = re.sub(r"【[^】]+】", "", cleaned)
    cleaned = re.sub(r"^(追问|问题)[:：]\s*", "", cleaned)
    cleaned = re.sub(r"^第\s*\d+\s*/\s*\d+\s*题[:：]\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > settings.tts_max_chars:
        cleaned = cleaned[: settings.tts_max_chars].rstrip() + "..."
    return cleaned


def synthesize_interviewer_speech(text: str) -> SpeechSynthesisResult:
    cleaned = normalize_interviewer_speech_text(text)
    provider = settings.tts_provider.lower().strip()
    if not cleaned:
        return SpeechSynthesisResult(
            available=False,
            text="",
            provider=provider or "browser",
            fallback_reason="empty speech text",
        )

    if provider in {"", "browser", "mock", "none", "disabled"}:
        return SpeechSynthesisResult(
            available=False,
            text=cleaned,
            provider=provider or "browser",
            fallback_reason="server tts is not configured",
        )

    voice = _effective_voice(provider)

    if provider == "edge":
        return _synthesize_with_edge(cleaned, provider, voice)

    if provider in {"volcengine", "doubao", "volcano"}:
        return _synthesize_with_volcengine(cleaned, provider)

    if provider not in {"openai", "openai-compatible"}:
        return SpeechSynthesisResult(
            available=False,
            text=cleaned,
            provider=provider,
            voice=voice,
            fallback_reason=f"unsupported tts provider: {provider}",
        )

    if not settings.tts_api_key:
        return SpeechSynthesisResult(
            available=False,
            text=cleaned,
            provider=provider,
            voice=voice,
            fallback_reason="TTS_API_KEY is not configured",
        )

    try:
        from openai import OpenAI

        client_kwargs = {"api_key": settings.tts_api_key}
        if settings.tts_base_url:
            client_kwargs["base_url"] = settings.tts_base_url
        client = OpenAI(**client_kwargs)
        response = client.audio.speech.create(
            model=settings.tts_model,
            voice=voice,
            input=cleaned,
            response_format=settings.tts_response_format,
        )
        if hasattr(response, "read"):
            audio_bytes = response.read()
        else:
            audio_bytes = getattr(response, "content", b"")
        if not audio_bytes:
            return SpeechSynthesisResult(
                available=False,
                text=cleaned,
                provider=provider,
                voice=voice,
                fallback_reason="tts provider returned empty audio",
            )
        media_type = "audio/mpeg" if settings.tts_response_format == "mp3" else f"audio/{settings.tts_response_format}"
        return SpeechSynthesisResult(
            available=True,
            text=cleaned,
            provider=provider,
            voice=voice,
            media_type=media_type,
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
        )
    except Exception as exc:  # pragma: no cover - depends on external TTS service
        return SpeechSynthesisResult(
            available=False,
            text=cleaned,
            provider=provider,
            voice=voice,
            fallback_reason=f"tts request failed: {exc}",
        )


def _effective_voice(provider: str) -> str:
    if provider == "edge" and settings.tts_voice in {"", "alloy"}:
        return "zh-CN-YunxiNeural"
    return settings.tts_voice


def _synthesize_with_volcengine(text: str, provider: str) -> SpeechSynthesisResult:
    missing = []
    if not settings.volc_tts_api_key:
        missing.append("VOLC_TTS_API_KEY")
    if not settings.volc_tts_resource_id:
        missing.append("VOLC_TTS_RESOURCE_ID")
    if not settings.volc_tts_voice_type:
        missing.append("VOLC_TTS_VOICE_TYPE")
    if missing:
        return SpeechSynthesisResult(
            available=False,
            text=text,
            provider=provider,
            voice=settings.volc_tts_voice_type,
            fallback_reason=f"missing volcengine tts config: {', '.join(missing)}",
        )

    headers = _build_volcengine_v3_headers()
    payload = _build_volcengine_v3_payload(text)
    try:
        response = httpx.post(
            settings.volc_tts_v3_endpoint,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - depends on external TTS service
        return SpeechSynthesisResult(
            available=False,
            text=text,
            provider=provider,
            voice=settings.volc_tts_voice_type,
            fallback_reason=f"volcengine tts request failed: {exc}",
        )

    audio_base64, error_message = _extract_volcengine_v3_audio(response)
    if not audio_base64:
        return SpeechSynthesisResult(
            available=False,
            text=text,
            provider=provider,
            voice=settings.volc_tts_voice_type,
            fallback_reason=error_message or "volcengine returned empty audio",
        )

    return SpeechSynthesisResult(
        available=True,
        text=text,
        provider=provider,
        voice=settings.volc_tts_voice_type,
        media_type=_media_type_for_encoding(settings.tts_response_format),
        audio_base64=audio_base64,
    )


def _build_volcengine_v3_headers() -> dict:
    request_id = str(uuid.uuid4())
    headers = {
        "Content-Type": "application/json",
        "X-Api-Resource-Id": settings.volc_tts_resource_id,
        "X-Api-Request-Id": request_id,
        "X-Api-Key": settings.volc_tts_api_key,
    }
    return headers


def _build_volcengine_v3_payload(text: str) -> dict:
    return {
        "user": {
            "uid": settings.volc_tts_uid or "ai-career-agent",
        },
        "req_params": {
            "text": text,
            "speaker": settings.volc_tts_voice_type,
            "audio_params": {
                "format": settings.tts_response_format,
                "sample_rate": settings.volc_tts_sample_rate,
                "speech_rate": _ratio_to_rate(settings.volc_tts_speed_ratio),
                "loudness_rate": _ratio_to_rate(settings.volc_tts_volume_ratio),
                "enable_timestamp": False,
            },
        },
    }


def _extract_volcengine_v3_audio(response: httpx.Response) -> tuple[str, str]:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return _extract_audio_from_mapping(response.json())
        except ValueError:
            return "", "volcengine v3 returned invalid json"

    text = response.text.strip()
    if text:
        audio_base64 = _extract_audio_from_stream_text(text)
        if audio_base64:
            return audio_base64, ""

    content = response.content or b""
    if content.startswith(b"ID3") or content[:2] == b"\xff\xfb":
        return base64.b64encode(content).decode("ascii"), ""

    return "", text[:300] if text else "volcengine v3 returned unsupported response"


def _extract_audio_from_mapping(body: dict) -> tuple[str, str]:
    code = body.get("code")
    if code not in {None, 0, 20000000, 3000}:
        return "", body.get("message") or body.get("msg") or f"volcengine code {code}"

    data = body.get("data")
    if isinstance(data, str):
        return data, ""
    if isinstance(data, dict):
        for key in ("audio", "audio_base64", "audio_data"):
            if data.get(key):
                return str(data[key]), ""
        audio_url = data.get("audio_url") or data.get("url")
        if audio_url:
            return _download_audio_as_base64(str(audio_url))
    for key in ("audio", "audio_base64", "audio_data"):
        if body.get(key):
            return str(body[key]), ""
    return "", body.get("message") or body.get("msg") or "volcengine response has no audio"


def _extract_audio_from_stream_text(text: str) -> str:
    chunks = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        if line in {"[DONE]", "DONE"}:
            continue
        try:
            payload = httpx.Response(200, content=line.encode("utf-8")).json()
        except ValueError:
            continue
        audio_base64, _ = _extract_audio_from_mapping(payload)
        if audio_base64:
            chunks.append(audio_base64)
    return "".join(chunks)


def _download_audio_as_base64(url: str) -> tuple[str, str]:
    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        return base64.b64encode(response.content).decode("ascii"), ""
    except Exception as exc:  # pragma: no cover - depends on external TTS service
        return "", f"failed to download volcengine audio_url: {exc}"


def _ratio_to_rate(ratio: float) -> int:
    return max(-50, min(100, round((ratio - 1.0) * 100)))


def _media_type_for_encoding(encoding: str) -> str:
    normalized = (encoding or "mp3").lower()
    if normalized == "mp3":
        return "audio/mpeg"
    if normalized == "wav":
        return "audio/wav"
    if normalized == "ogg_opus":
        return "audio/ogg"
    return f"audio/{normalized}"


def _synthesize_with_edge(text: str, provider: str, voice: str) -> SpeechSynthesisResult:
    try:
        import edge_tts
    except ImportError:
        return SpeechSynthesisResult(
            available=False,
            text=text,
            provider=provider,
            voice=voice,
            fallback_reason="edge-tts is not installed",
        )

    try:
        audio_bytes = asyncio.run(_collect_edge_audio(edge_tts, text, voice))
        if not audio_bytes:
            return SpeechSynthesisResult(
                available=False,
                text=text,
                provider=provider,
                voice=voice,
                fallback_reason="edge-tts returned empty audio",
            )
        return SpeechSynthesisResult(
            available=True,
            text=text,
            provider=provider,
            voice=voice,
            media_type="audio/mpeg",
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
        )
    except Exception as exc:  # pragma: no cover - depends on external TTS service
        return SpeechSynthesisResult(
            available=False,
            text=text,
            provider=provider,
            voice=voice,
            fallback_reason=f"edge-tts request failed: {exc}",
        )


async def _collect_edge_audio(edge_tts_module, text: str, voice: str) -> bytes:
    communicate = edge_tts_module.Communicate(text, voice=voice, rate="+0%")
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)
