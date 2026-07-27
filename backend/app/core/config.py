import os
from typing import List

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience dependency
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "AI Career Agent")
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./career_agent.db")
        self.secret_key = os.getenv(
            "SECRET_KEY",
            "development-only-change-this-secret-key",
        )
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120")
        )
        self.vector_store_path = os.getenv("VECTOR_STORE_PATH", "./data/vector_store")
        self.vector_model_name = os.getenv(
            "VECTOR_MODEL_NAME",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        self.vector_collection_name = os.getenv(
            "VECTOR_COLLECTION_NAME",
            "approved_jobs",
        )
        self.knowledge_collection_name = os.getenv(
            "KNOWLEDGE_COLLECTION_NAME",
            "knowledge_base",
        )
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock")
        self.llm_api_key = os.getenv("LLM_API_KEY", "")
        self.llm_base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.llm_model = os.getenv("LLM_MODEL", "deepseek-chat")
        self.tts_provider = os.getenv("TTS_PROVIDER", "browser")
        self.tts_api_key = os.getenv("TTS_API_KEY", "")
        self.tts_base_url = os.getenv("TTS_BASE_URL", "")
        self.tts_model = os.getenv("TTS_MODEL", "tts-1")
        self.tts_voice = os.getenv("TTS_VOICE", "alloy")
        self.tts_response_format = os.getenv("TTS_RESPONSE_FORMAT", "mp3")
        self.tts_max_chars = int(os.getenv("TTS_MAX_CHARS", "180"))
        self.volc_tts_api_key = os.getenv(
            "VOLC_TTS_API_KEY",
            os.getenv("TTS_VOLC_API_KEY", ""),
        )
        self.volc_tts_resource_id = os.getenv(
            "VOLC_TTS_RESOURCE_ID",
            os.getenv("TTS_VOLC_RESOURCE_ID", "seed-tts-2.0"),
        )
        self.volc_tts_voice_type = os.getenv(
            "VOLC_TTS_VOICE_TYPE",
            os.getenv("TTS_VOLC_VOICE_TYPE", ""),
        )
        self.volc_tts_uid = os.getenv("VOLC_TTS_UID", "ai-career-agent")
        self.volc_tts_v3_endpoint = os.getenv(
            "VOLC_TTS_V3_ENDPOINT",
            "https://openspeech.bytedance.com/api/v3/tts/unidirectional",
        )
        self.volc_tts_sample_rate = int(os.getenv("VOLC_TTS_SAMPLE_RATE", "24000"))
        self.volc_tts_speed_ratio = float(os.getenv("VOLC_TTS_SPEED_RATIO", "1.0"))
        self.volc_tts_volume_ratio = float(os.getenv("VOLC_TTS_VOLUME_RATIO", "1.0"))
        self.volc_tts_pitch_ratio = float(os.getenv("VOLC_TTS_PITCH_RATIO", "1.0"))

    @property
    def cors_origins(self) -> List[str]:
        raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        return [item.strip() for item in raw.split(",") if item.strip()]


settings = Settings()
