import logging
from collections.abc import Sequence
from typing import Any

import httpx
import pytest
from google.genai.errors import ClientError as GeminiClientError
from google.genai.errors import ServerError as GeminiServerError
from groq import BadRequestError as GroqBadRequestError
from groq import InternalServerError as GroqInternalServerError
from groq import RateLimitError as GroqRateLimitError
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

from app.common.exceptions import EmbeddingBackendUnavailableError
from app.common.llm.router import (
    ModelRouter,
    _FallbackEmbeddings,
    _is_retryable,
    _OllamaOnlyEmbeddings,
)
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
        "gemini_embedding_model": "test-gemini-embedding-model",
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
    def invoke(self, messages: Sequence[Any], config: Any = None) -> Any:
        raise _rate_limit_error()


class _AlwaysBadRequestModel:
    def invoke(self, messages: Sequence[Any], config: Any = None) -> Any:
        raise _bad_request_error()


class _FakeOllamaModel:
    last_model_name: str | None = None

    def __init__(self, model: str, base_url: str, temperature: float = 0) -> None:
        _FakeOllamaModel.last_model_name = model

    def invoke(self, messages: Sequence[Any], config: Any = None) -> str:
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


# --- get_embedding_model / get_transient_embedding_model (Item 1) ----------


class _AlwaysUnreachableEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        raise httpx.ConnectError("connection refused")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise httpx.ConnectError("connection refused")


class _AlwaysUnreachableEmbeddingsRealTranslation:
    """Reproduces what the real, installed ollama client (v0.6.2) actually
    raises -- Client._request_raw catches httpx.ConnectError internally and
    re-raises the builtin ConnectionError, NOT httpx.ConnectError itself and
    NOT an httpx.TransportError subclass. A wrapper that only catches
    httpx.TransportError never sees this and lets it leak straight through.
    """

    def embed_query(self, text: str) -> list[float]:
        raise ConnectionError("Failed to connect to Ollama")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise ConnectionError("Failed to connect to Ollama")


def test_ollama_only_embeddings_raises_typed_error_on_connectivity_failure() -> None:
    """Class A/B (persisted-vector) embeddings must never fall back to a
    different provider -- a Gemini vector isn't comparable against an
    Ollama vector already stored in Postgres. Instead callers get a typed
    EmbeddingBackendUnavailableError, not a raw httpx/ollama exception.
    """
    wrapper = _OllamaOnlyEmbeddings(_AlwaysUnreachableEmbeddings())  # type: ignore[arg-type]

    with pytest.raises(EmbeddingBackendUnavailableError):
        wrapper.embed_query("python")


def test_ollama_only_embeddings_raises_typed_error_on_the_real_ollama_client_translation() -> None:
    """Regression: the real ollama/langchain_ollama translation layer raises
    the builtin ConnectionError (not httpx.TransportError) when Ollama is
    unreachable -- see Client._request_raw in the installed ollama package.
    Catching only httpx.TransportError leaks this uncaught past the wrapper.
    """
    wrapper = _OllamaOnlyEmbeddings(_AlwaysUnreachableEmbeddingsRealTranslation())  # type: ignore[arg-type]

    with pytest.raises(EmbeddingBackendUnavailableError):
        wrapper.embed_query("python")


def test_ollama_only_embeddings_does_not_wrap_unrelated_exceptions() -> None:
    class _BrokenEmbeddings:
        def embed_query(self, text: str) -> list[float]:
            raise ValueError("boom")

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise ValueError("boom")

    wrapper = _OllamaOnlyEmbeddings(_BrokenEmbeddings())  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        wrapper.embed_query("python")


class _FakeOllamaEmbeddings:
    def __init__(self) -> None:
        self.calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        raise httpx.ConnectError("connection refused")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        raise httpx.ConnectError("connection refused")


class _FakeOllamaEmbeddingsRealTranslation:
    """Reproduces the real ollama client's translation of a connectivity
    failure into a builtin ConnectionError -- see
    _AlwaysUnreachableEmbeddingsRealTranslation's docstring above.
    """

    def __init__(self) -> None:
        self.calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        raise ConnectionError("Failed to connect to Ollama")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        raise ConnectionError("Failed to connect to Ollama")


class _FakeGeminiEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def test_fallback_embeddings_falls_back_to_gemini_on_ollama_connectivity_failure() -> None:
    """Class C (fully transient, e.g. TDR chunk retrieval) embeddings CAN
    safely fall back -- self-consistency within one call is all that's
    required.
    """
    fallback = _FallbackEmbeddings(_FakeOllamaEmbeddings(), _FakeGeminiEmbeddings())  # type: ignore[arg-type]

    result = fallback.embed_query("python")

    assert result == [1.0, 0.0]


def test_fallback_embeddings_falls_back_to_gemini_on_the_real_ollama_client_translation() -> None:
    """Regression: the real ollama client raises the builtin ConnectionError
    (not httpx.TransportError) on a connectivity failure -- without catching
    it too, this best-effort fallback crashes instead of degrading to Gemini.
    """
    ollama = _FakeOllamaEmbeddingsRealTranslation()
    fallback = _FallbackEmbeddings(ollama, _FakeGeminiEmbeddings())  # type: ignore[arg-type]

    result = fallback.embed_query("python")

    assert result == [1.0, 0.0]
    assert ollama.calls == 1


def test_fallback_embeddings_stays_on_gemini_for_a_second_call_sticky() -> None:
    """Regression guard: once Ollama has failed once, it must never be
    re-attempted on a later call on the same instance.
    """
    ollama = _FakeOllamaEmbeddings()
    fallback = _FallbackEmbeddings(ollama, _FakeGeminiEmbeddings())  # type: ignore[arg-type]

    fallback.embed_query("first")
    fallback.embed_query("second")

    assert ollama.calls == 1  # only the first call ever touched Ollama


def test_fallback_embeddings_does_not_fall_back_on_an_unrelated_exception() -> None:
    class _BrokenOllamaEmbeddings:
        def embed_query(self, text: str) -> list[float]:
            raise ValueError("boom")

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise ValueError("boom")

    fallback = _FallbackEmbeddings(_BrokenOllamaEmbeddings(), _FakeGeminiEmbeddings())  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        fallback.embed_query("python")


# --- token/cost usage capture (Item 2) --------------------------------------


class _FakeUsageTrackingModel:
    """Stands in for a real BaseChatModel (ChatGroq/ChatGoogleGenerativeAI/
    ChatOllama): a real chat model's internal callback machinery invokes
    on_llm_end on whatever callbacks were forwarded via config -- this fake
    reproduces just that behavior so the test can assert the router's
    usage-tracking wiring end to end without a live network call.
    """

    def __init__(self, model_name: str, usage_metadata: dict[str, int]) -> None:
        self._model_name = model_name
        self._usage_metadata = usage_metadata
        self.seen_config: Any = None

    def invoke(self, messages: Sequence[Any], config: Any = None) -> AIMessage:
        self.seen_config = config
        message = AIMessage(
            content="ok",
            usage_metadata=self._usage_metadata,
            response_metadata={"model_name": self._model_name},
        )
        for callback in config["callbacks"]:
            callback.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]))
        return message


def test_invoke_forwards_config_with_callbacks_to_the_underlying_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Core regression guard: without forwarding config, UsageMetadataCallbackHandler
    never sees anything (see docs/04-evaluation-metrics.md's known-gaps section).
    """
    usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    fake_model = _FakeUsageTrackingModel("test-groq-extraction-model", usage)
    monkeypatch.setattr(
        "app.common.llm.router._build_chat_model", lambda provider, model_name, api_key: fake_model
    )

    router = ModelRouter(_make_settings())
    router.invoke_extraction([])

    assert fake_model.seen_config is not None
    assert "callbacks" in fake_model.seen_config
    assert isinstance(fake_model.seen_config["callbacks"], list)


def test_usage_totals_accumulates_across_the_pool_path(monkeypatch: pytest.MonkeyPatch) -> None:
    usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    monkeypatch.setattr(
        "app.common.llm.router._build_chat_model",
        lambda provider, model_name, api_key: _FakeUsageTrackingModel(model_name, usage),
    )

    router = ModelRouter(_make_settings())
    router.invoke_extraction([])

    assert router.usage_totals["test-groq-extraction-model"]["total_tokens"] == 15


def test_llm_usage_log_line_fires_with_correct_fields_on_the_pool_path(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    monkeypatch.setattr(
        "app.common.llm.router._build_chat_model",
        lambda provider, model_name, api_key: _FakeUsageTrackingModel(model_name, usage),
    )

    router = ModelRouter(_make_settings())
    with caplog.at_level(logging.INFO, logger="app.common.llm.router"):
        router.invoke_extraction([])

    usage_records = [r for r in caplog.records if r.message.startswith("llm.usage")]
    assert len(usage_records) == 1
    message = usage_records[0].message
    assert "provider=groq" in message
    assert "tier=extraction" in message
    assert "model=test-groq-extraction-model" in message
    assert "input_tokens=10" in message
    assert "output_tokens=5" in message
    assert "total_tokens=15" in message


def test_llm_usage_log_line_fires_with_correct_fields_on_the_ollama_fallback_path(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    usage = {"input_tokens": 20, "output_tokens": 8, "total_tokens": 28}
    monkeypatch.setattr(
        "app.common.llm.router.ChatOllama",
        lambda model, base_url, temperature=0: _FakeUsageTrackingModel(model, usage),
    )
    # Empty key pools -- both providers report exhausted immediately, so
    # this always falls straight through to the Ollama fallback branch.
    router = ModelRouter(_make_settings(groq_api_keys="", gemini_api_keys=""))

    with caplog.at_level(logging.INFO, logger="app.common.llm.router"):
        router.invoke_extraction([])

    usage_records = [r for r in caplog.records if r.message.startswith("llm.usage")]
    assert len(usage_records) == 1
    message = usage_records[0].message
    assert "provider=ollama" in message
    assert "tier=extraction" in message
    assert "model=test-ollama-extraction-model" in message
    assert "input_tokens=20" in message
    assert "output_tokens=8" in message
    assert "total_tokens=28" in message
