from collections.abc import Sequence
from typing import Any

import httpx
import pytest
from google.genai.errors import ClientError as GeminiClientError
from groq import RateLimitError as GroqRateLimitError

from app.common.llm.router import ModelRouter, _is_rate_limited
from app.config.settings import Settings


def _make_settings(**overrides: str) -> Settings:
    defaults: dict[str, str] = {
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "redis_url": "redis://localhost",
        "groq_api_keys": "groq-key-1,groq-key-2",
        "gemini_api_keys": "gemini-key-1",
        "ollama_base_url": "http://localhost:11434",
        "llm_extraction_model": "test-extraction-model",
        "llm_reasoning_model": "test-reasoning-model",
        "embedding_model": "nomic-embed-text",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def _rate_limit_error() -> GroqRateLimitError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return GroqRateLimitError("rate limited", response=response, body=None)


class _AlwaysRateLimitedModel:
    def invoke(self, messages: Sequence[Any]) -> Any:
        raise _rate_limit_error()


class _FakeOllamaModel:
    last_model_name: str | None = None

    def __init__(self, model: str, base_url: str) -> None:
        _FakeOllamaModel.last_model_name = model

    def invoke(self, messages: Sequence[Any]) -> str:
        return "ollama-response"


def test_router_falls_back_to_ollama_once_every_key_in_both_pools_is_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADQ-2 acceptance criterion: simulate full exhaustion, assert Ollama fires."""
    monkeypatch.setattr(
        "app.common.llm.router._build_chat_model",
        lambda provider, model_name, api_key: _AlwaysRateLimitedModel(),
    )
    monkeypatch.setattr("app.common.llm.router.ChatOllama", _FakeOllamaModel)

    router = ModelRouter(_make_settings())

    result = router.invoke_extraction([])

    assert result == "ollama-response"
    assert _FakeOllamaModel.last_model_name == "test-extraction-model"


def test_is_rate_limited_detects_groq_429() -> None:
    assert _is_rate_limited(_rate_limit_error()) is True


def test_is_rate_limited_detects_gemini_429() -> None:
    error = GeminiClientError(429, {"error": {"message": "quota exceeded"}})
    assert _is_rate_limited(error) is True


def test_is_rate_limited_ignores_unrelated_errors() -> None:
    assert _is_rate_limited(ValueError("boom")) is False
