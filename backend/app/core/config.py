import os
from typing import List


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
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock")
        self.llm_api_key = os.getenv("LLM_API_KEY", "")

    @property
    def cors_origins(self) -> List[str]:
        raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        return [item.strip() for item in raw.split(",") if item.strip()]


settings = Settings()
