import base64

from app.core.config import settings
from app.services.speech_synthesis import normalize_interviewer_speech_text, synthesize_interviewer_speech


def _auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "speech-user",
            "email": "speech@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "speech-user", "password": "password123"},
    )
    return {"Authorization": "Bearer %s" % response.json()["data"]["access_token"]}


def test_tts_endpoint_returns_browser_fallback_when_server_tts_is_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "browser")

    response = client.post(
        "/api/v1/speech/tts",
        headers=_auth_headers(client),
        json={
            "text": (
                "反馈：回答结构清晰。\n\n"
                "第 2/8 题：请说明你如何设计岗位匹配算法？"
            )
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["available"] is False
    assert data["provider"] == "browser"
    assert data["audio_base64"] == ""
    assert data["text"] == "请说明你如何设计岗位匹配算法？"


def test_interviewer_speech_text_only_keeps_followup_or_question():
    assert normalize_interviewer_speech_text("追问：请补充量化结果。") == "请补充量化结果。"
    assert normalize_interviewer_speech_text(
        "反馈：建议补充细节。\n\n第 3/8 题：请讲一个联调 bug。"
    ) == "请讲一个联调 bug。"


def test_volcengine_tts_reports_missing_config(monkeypatch):
    monkeypatch.setattr(settings, "tts_provider", "volcengine")
    monkeypatch.setattr(settings, "volc_tts_api_key", "")
    monkeypatch.setattr(settings, "volc_tts_resource_id", "")
    monkeypatch.setattr(settings, "volc_tts_voice_type", "")

    result = synthesize_interviewer_speech("第 1/8 题：请做一个自我介绍。")

    assert result.available is False
    assert result.provider == "volcengine"
    assert result.text == "请做一个自我介绍。"
    assert "VOLC_TTS_API_KEY" in result.fallback_reason
    assert "VOLC_TTS_RESOURCE_ID" in result.fallback_reason
    assert "VOLC_TTS_VOICE_TYPE" in result.fallback_reason


def test_volcengine_tts_success_response(monkeypatch):
    class FakeResponse:
        headers = {"content-type": "application/json"}
        content = b""

        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 3000, "data": base64.b64encode(b"fake-mp3").decode("ascii")}

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(settings, "tts_provider", "doubao")
    monkeypatch.setattr(settings, "tts_response_format", "mp3")
    monkeypatch.setattr(settings, "volc_tts_v3_endpoint", "https://example.com/tts")
    monkeypatch.setattr(settings, "volc_tts_api_key", "api-key-123")
    monkeypatch.setattr(settings, "volc_tts_resource_id", "seed-tts-2.0")
    monkeypatch.setattr(settings, "volc_tts_voice_type", "zh_male_demo")
    monkeypatch.setattr(settings, "volc_tts_uid", "tester")
    monkeypatch.setattr(settings, "volc_tts_sample_rate", 24000)
    monkeypatch.setattr(settings, "volc_tts_speed_ratio", 1.0)
    monkeypatch.setattr(settings, "volc_tts_volume_ratio", 1.0)
    monkeypatch.setattr(settings, "volc_tts_pitch_ratio", 1.0)

    monkeypatch.setattr("app.services.speech_synthesis.httpx.post", fake_post)

    result = synthesize_interviewer_speech("追问：请补充项目中的量化指标。")

    assert result.available is True
    assert result.provider == "doubao"
    assert result.voice == "zh_male_demo"
    assert result.media_type == "audio/mpeg"
    assert result.audio_base64 == base64.b64encode(b"fake-mp3").decode("ascii")
    assert result.text == "请补充项目中的量化指标。"
    assert captured["url"] == "https://example.com/tts"
    assert captured["headers"]["X-Api-Key"] == "api-key-123"
    assert captured["headers"]["X-Api-Resource-Id"] == "seed-tts-2.0"
    assert captured["json"]["req_params"]["speaker"] == "zh_male_demo"
    assert captured["json"]["req_params"]["text"] == "请补充项目中的量化指标。"
    assert captured["json"]["req_params"]["audio_params"]["sample_rate"] == 24000
