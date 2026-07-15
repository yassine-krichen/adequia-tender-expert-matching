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
    mcp_server_url: str

    groq_api_keys: str
    gemini_api_keys: str
    ollama_base_url: str

    # No shared model name across providers — Groq/Gemini/Ollama each use
    # their own naming scheme, so the fallback chain needs one model per
    # provider per tier, not one string reused everywhere.
    groq_extraction_model: str
    groq_reasoning_model: str
    gemini_extraction_model: str
    gemini_reasoning_model: str
    ollama_extraction_model: str
    ollama_reasoning_model: str

    embedding_model: str
    embedding_dimension: int = 768

    langsmith_api_key: str | None = None
    langsmith_project: str = "adequia"
    # Only needed for EU-region LangSmith accounts (e.g.
    # https://eu.api.smith.langchain.com) — a US key against the default US
    # endpoint needs nothing here. Getting this wrong for an EU account is
    # the most common cause of a 403 Forbidden on trace ingestion.
    langsmith_endpoint: str | None = None

    environment: str = "development"
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values loaded from .env by pydantic-settings
