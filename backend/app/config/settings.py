from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, validated at startup.

    Fails immediately on missing or malformed env vars instead of at the
    point of first use — see docs/01-architecture.md security posture.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str

    groq_api_keys: str
    gemini_api_keys: str
    ollama_base_url: str
    llm_extraction_model: str
    llm_reasoning_model: str

    embedding_model: str
    embedding_dimension: int = 768

    langsmith_api_key: str | None = None
    langsmith_project: str = "adequia"

    environment: str = "development"
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values loaded from .env by pydantic-settings
