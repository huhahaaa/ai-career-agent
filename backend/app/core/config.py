import os
from typing import List


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "AI Career Agent")
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./career_agent.db")
        self.vector_store_path = os.getenv("VECTOR_STORE_PATH", "./data/vector_store")
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock")
        self.llm_api_key = os.getenv("LLM_API_KEY", "")

    @property
    def cors_origins(self) -> List[str]:
        raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        return [item.strip() for item in raw.split(",") if item.strip()]


settings = Settings()

