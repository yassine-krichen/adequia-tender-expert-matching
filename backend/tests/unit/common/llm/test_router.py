from collections.abc import Sequence
from typing import Any

import httpx
import pytest
from google.genai.errors import ClientError as GeminiClientError
from google.genai.errors import ServerError as GeminiServerError
from groq import BadRequestError as GroqBadRequestError
from groq import InternalServerError as GroqInternalServerError
from groq import RateLimitError as GroqRateLimitError
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

from app.common.llm.router import ModelRouter, _is_retryable
from app.config.settings import Settings


def _make_settings(**overrides: str) -> Settings:
    defaults: dict[str, str] = {
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "redis_url": "redis://localhost",
        "groq_api_keys": "groq-key-1,groq-key-2",
        "gemini_api_keys": "gemini-key-1",
        "ollama_base_url": "http://localhost:11434",
        "groq_extraction_model": "test-groq-extraction-model",
        "groq_reasoning_model": "test-groq-reasoning-model",
        "gemini_extraction_model": "test-gemini-extraction-model",
        "gemini_reasoning_model": "test-gemini-reasoning-model",
        "ollama_extraction_model": "test-ollama-extraction-model",
        "ollama_reasoning_model": "test-ollama-reasoning-model",
        "embedding_model": "nomic-embed-text",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def _rate_limit_error() -> GroqRateLimitError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return GroqRateLimitError("rate limited", response=response, body=None)


def _bad_request_error() -> GroqBadRequestError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(400, request=request)
    return GroqBadRequestError("tool_use_failed", response=response, body=None)


class _AlwaysRateLimitedModel:
    def invoke(self, messages: Sequence[Any]) -> Any:
        raise _rate_limit_error()


class _AlwaysBadRequestModel:
    def invoke(self, messages: Sequence[Any]) -> Any:
        raise _bad_request_error()


class _FakeOllamaModel:
    last_model_name: str | None = None

    def __init__(self, model: str, base_url: str, temperature: float = 0) -> None:
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
    assert _FakeOllamaModel.last_model_name == "test-ollama-extraction-model"


def test_invoke_uses_each_providers_own_model_name_not_a_shared_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: Groq/Gemini/Ollama don't share a model-naming scheme, so
    each attempt in the fallback chain must resolve its own model string,
    not reuse whichever one the first provider was given.
    """
    seen_model_names: dict[str, str] = {}

    def _fake_build(provider: str, model_name: str, api_key: str) -> Any:
        seen_model_names[provider] = model_name
        return _AlwaysRateLimitedModel()

    monkeypatch.setattr("app.common.llm.router._build_chat_model", _fake_build)
    monkeypatch.setattr("app.common.llm.router.ChatOllama", _FakeOllamaModel)

    router = ModelRouter(_make_settings())
    router.invoke_reasoning([])

    assert seen_model_names["groq"] == "test-groq-reasoning-model"
    assert seen_model_names["gemini"] == "test-gemini-reasoning-model"
    assert _FakeOllamaModel.last_model_name == "test-ollama-reasoning-model"


def test_router_rotates_to_the_next_provider_on_a_content_rejection_not_just_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: Groq's tool_use_failed (a plain 400, not a 429) must
    also trigger rotation to Gemini/Ollama — verified live that treating
    only rate limits as retryable meant Gemini's pool never actually got
    exercised when Groq's structured output was simply unreliable.
    """
    monkeypatch.setattr(
        "app.common.llm.router._build_chat_model",
        lambda provider, model_name, api_key: _AlwaysBadRequestModel(),
    )
    monkeypatch.setattr("app.common.llm.router.ChatOllama", _FakeOllamaModel)

    router = ModelRouter(_make_settings())

    result = router.invoke_extraction([])

    assert result == "ollama-response"


def test_is_retryable_detects_groq_429() -> None:
    assert _is_retryable(_rate_limit_error()) is True


def test_is_retryable_detects_groq_bad_request() -> None:
    assert _is_retryable(_bad_request_error()) is True


def test_is_retryable_detects_gemini_429() -> None:
    error = GeminiClientError(429, {"error": {"message": "quota exceeded"}})
    assert _is_retryable(error) is True


def test_is_retryable_detects_gemini_non_429_client_error() -> None:
    error = GeminiClientError(400, {"error": {"message": "invalid argument"}})
    assert _is_retryable(error) is True


def test_is_retryable_detects_gemini_wrapped_error() -> None:
    """Regression: langchain_google_genai catches the raw GeminiClientError
    (e.g. a 429 quota exhaustion) and re-raises this wrapper instead —
    observed live against Gemini's real free-tier quota. Without this,
    Gemini quota exhaustion crashed the whole extraction instead of
    rotating to Ollama.
    """
    assert _is_retryable(ChatGoogleGenerativeAIError("quota exceeded")) is True


def test_is_retryable_detects_gemini_server_error() -> None:
    """Regression: Gemini returned a plain 503 "experiencing high demand"
    mid-eval-run (tests/eval/) — a transient server-side outage, not a rate
    limit or a content rejection. Without this, that 503 crashed the whole
    extraction instead of rotating to the next provider/Ollama.
    """
    error = GeminiServerError(503, {"error": {"message": "high demand"}})
    assert _is_retryable(error) is True


def test_is_retryable_detects_groq_internal_server_error() -> None:
    """Groq's 5xx equivalent of the Gemini case above — not observed live
    yet, but the same class of transient-outage problem, so handled the
    same way for symmetry rather than waiting to hit it in production.
    """
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(500, request=request)
    error = GroqInternalServerError("internal server error", response=response, body=None)
    assert _is_retryable(error) is True


def test_is_retryable_detects_a_raw_connection_timeout() -> None:
    """Regression: a raw httpx.ConnectTimeout reaching Gemini's endpoint
    (observed live, tests/eval/) crashed the whole extraction instead of
    rotating — a connection that can't be established is the same class of
    "provider unreachable" problem as a 503, not a code bug to fail loud on.
    """
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta")
    assert _is_retryable(httpx.ConnectTimeout("connect timeout", request=request)) is True


def test_is_retryable_ignores_unrelated_errors() -> None:
    assert _is_retryable(ValueError("boom")) is False
