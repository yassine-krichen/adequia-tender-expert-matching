import logging
from collections.abc import Callable, Sequence
from typing import Any, Protocol

import httpx
from google.genai.errors import ClientError as GeminiClientError
from google.genai.errors import ServerError as GeminiServerError
from groq import BadRequestError as GroqBadRequestError
from groq import InternalServerError as GroqInternalServerError
from groq import RateLimitError as GroqRateLimitError
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.embeddings import Embeddings
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama, OllamaEmbeddings
from pydantic import SecretStr, ValidationError

from app.common.exceptions import EmbeddingBackendUnavailableError
from app.common.llm.key_pool import KeyPool, parse_key_pool
from app.config.settings import Settings

logger = logging.getLogger(__name__)

_POOL_EXHAUSTED = object()

# A key/provider is skipped in favor of the next one for any of these:
# genuine rate limits, AND the provider's own structured-output validation
# rejecting the generated arguments (observed live: Groq's tool_use_failed
# on a nested schema, and — separately — Gemini/local parsing failures).
# Without treating these as retryable-via-rotation too, a single provider's
# unreliable JSON generation permanently blocks ever trying the next
# provider, defeating the whole point of having more than one.
#
# ChatGoogleGenerativeAIError: langchain_google_genai catches the raw
# GeminiClientError (429, quota, ...) internally and re-raises this wrapper
# instead — observed live with Gemini's very low free-tier daily quota (20
# req/day for gemini-2.5-flash-lite). Without this, quota exhaustion never
# triggered a rotation to Ollama, it just crashed the whole extraction.
#
# GeminiServerError/GroqInternalServerError (5xx): observed live — Gemini
# returned a 503 "model currently experiencing high demand" mid-eval-run.
# That's the provider being temporarily down, same class of problem as a
# rate limit from this router's point of view: try the next provider/key
# rather than crash the whole extraction. Groq's 5xx equivalent is included
# for the same reason even though only Gemini's has been seen live so far.
#
# httpx.TransportError: observed live — a raw ConnectTimeout reaching
# Gemini's endpoint (both Groq's and Gemini's SDKs are httpx-based). A
# connection that can't even be established is the same "this provider is
# unreachable right now" situation as a 503, so it gets the same treatment
# rather than crashing the extraction on what's often a transient blip.
_RETRYABLE_ERRORS = (
    GroqRateLimitError,
    GroqBadRequestError,
    GroqInternalServerError,
    GeminiClientError,
    GeminiServerError,
    ChatGoogleGenerativeAIError,
    httpx.TransportError,
    ValidationError,
    OutputParserException,
)


def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, _RETRYABLE_ERRORS)


def _build_chat_model(provider: str, model_name: str, api_key: str) -> BaseChatModel:
    # temperature=0: this router only ever calls structured-output
    # extraction/scoring, never open-ended generation — determinism helps
    # reliability and costs nothing here.
    if provider == "groq":
        return ChatGroq(model=model_name, api_key=SecretStr(api_key), temperature=0)
    return ChatGoogleGenerativeAI(model=model_name, api_key=SecretStr(api_key), temperature=0)


def _invoke_model(
    model: BaseChatModel,
    messages: Sequence[BaseMessage],
    structured_output: type[Any] | None,
    config: RunnableConfig,
) -> Any:
    if structured_output is not None:
        return model.with_structured_output(structured_output).invoke(messages, config=config)
    return model.invoke(messages, config=config)


class _OllamaOnlyEmbeddings(Embeddings):
    """Class A/B (persisted-vector) embedding wrapper -- CV/skill-taxonomy
    embeddings, coarse retrieval, skill normalization. Deliberately has NO
    fallback: a Gemini-produced vector would be numerically valid but
    semantically incomparable against an Ollama-produced vector already
    stored in Postgres (different, non-aligned vector spaces), which is
    silent corruption -- worse than a hard failure. Wraps the real
    OllamaEmbeddings' connectivity failures into a typed
    EmbeddingBackendUnavailableError instead of a raw httpx/ollama
    exception, so callers get a clear typed failure.
    """

    def __init__(self, embeddings: Embeddings) -> None:
        self._embeddings = embeddings

    def embed_query(self, text: str) -> list[float]:
        try:
            return self._embeddings.embed_query(text)
        except (httpx.TransportError, ConnectionError) as exc:
            raise EmbeddingBackendUnavailableError(
                "Ollama embedding backend is unreachable"
            ) from exc

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._embeddings.embed_documents(texts)
        except (httpx.TransportError, ConnectionError) as exc:
            raise EmbeddingBackendUnavailableError(
                "Ollama embedding backend is unreachable"
            ) from exc


class _FallbackEmbeddings(Embeddings):
    """Class C (fully transient) embedding wrapper -- TDR chunk retrieval
    (extract.py's _retrieve_relevant_chunks): the query vector and every
    chunk vector it's ranked against are computed together in the same
    call and never persisted or compared against anything from a
    different call, so self-consistency within one call is all that's
    required. Safe to fall back to Gemini here, unlike
    _OllamaOnlyEmbeddings' persisted-vector call sites.

    Tries Ollama first; on a connectivity-shaped failure, falls back to
    Gemini and STAYS on Gemini for the rest of this instance's lifetime
    (sticky) -- never re-attempts Ollama on a later call, and never lets
    the query embed via one backend while document embeds happen via the
    other.
    """

    def __init__(self, ollama_embeddings: Embeddings, gemini_embeddings: Embeddings) -> None:
        self._ollama = ollama_embeddings
        self._gemini = gemini_embeddings
        self._use_gemini = False

    def embed_query(self, text: str) -> list[float]:
        result: list[float] = self._call(lambda embeddings: embeddings.embed_query(text))
        return result

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = self._call(lambda embeddings: embeddings.embed_documents(texts))
        return result

    def _call(self, fn: Callable[[Embeddings], Any]) -> Any:
        if not self._use_gemini:
            try:
                return fn(self._ollama)
            except (httpx.TransportError, ConnectionError) as exc:
                logger.warning("embeddings.fallback_to_gemini error=%s", type(exc).__name__)
                self._use_gemini = True
        return fn(self._gemini)


class ExtractionRouter(Protocol):
    """What extraction nodes need from a router — lets tests substitute a
    fake without depending on ModelRouter's concrete key-pool/provider wiring.
    """

    def invoke_extraction(
        self, messages: Sequence[BaseMessage], structured_output: type[Any] | None = None
    ) -> Any: ...

    def invoke_reasoning(
        self, messages: Sequence[BaseMessage], structured_output: type[Any] | None = None
    ) -> Any: ...


class ModelRouter:
    """Rotates across the Groq and Gemini free-tier key pools, falling back
    to local Ollama once every key in both pools is exhausted — either
    rate-limited, or the provider rejected the structured output it
    generated (see _RETRYABLE_ERRORS). Free-tier LLMs are unreliable at
    emitting valid structured output for a nested schema often enough that
    treating only rate limits as retryable left Gemini's pool never
    actually exercised as a real fallback.

    See docs/01-architecture.md "Model routing" and docs/scrum/sprint-1-plan.md
    (ADQ-2) — there is no paid API access, so headroom comes entirely from
    spreading calls across multiple free-tier keys per provider.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pools = {
            "groq": KeyPool("groq", parse_key_pool(settings.groq_api_keys)),
            "gemini": KeyPool("gemini", parse_key_pool(settings.gemini_api_keys)),
        }
        # Explicit per-(provider, tier) map, not a dynamic getattr lookup —
        # keeps every entry mypy-checkable against Settings' real fields.
        self._models: dict[tuple[str, str], str] = {
            ("groq", "extraction"): settings.groq_extraction_model,
            ("groq", "reasoning"): settings.groq_reasoning_model,
            ("gemini", "extraction"): settings.gemini_extraction_model,
            ("gemini", "reasoning"): settings.gemini_reasoning_model,
            ("ollama", "extraction"): settings.ollama_extraction_model,
            ("ollama", "reasoning"): settings.ollama_reasoning_model,
        }
        # Built once, accumulates across this router's whole lifetime —
        # every _invoke_model call forwards this via config={"callbacks":
        # [...]} so real chat model integrations (ChatGroq/ChatGoogleGenerativeAI/
        # ChatOllama) populate it via their own internal callback machinery.
        # See docs/04-evaluation-metrics.md's known-gaps section: without
        # forwarding config, this handler never saw anything.
        self._usage_handler = UsageMetadataCallbackHandler()

    def invoke_extraction(
        self, messages: Sequence[BaseMessage], structured_output: type[Any] | None = None
    ) -> Any:
        return self._invoke("extraction", messages, structured_output)

    def invoke_reasoning(
        self, messages: Sequence[BaseMessage], structured_output: type[Any] | None = None
    ) -> Any:
        return self._invoke("reasoning", messages, structured_output)

    def get_embedding_model(self) -> Embeddings:
        """Class A/B (persisted-vector) embeddings -- CV/skill-taxonomy
        embeddings, coarse retrieval, skill normalization. Ollama-only,
        deliberately no fallback -- see _OllamaOnlyEmbeddings.
        """
        ollama = OllamaEmbeddings(
            model=self._settings.embedding_model, base_url=self._settings.ollama_base_url
        )
        return _OllamaOnlyEmbeddings(ollama)

    def get_transient_embedding_model(self) -> Embeddings:
        """Class C (fully transient) embeddings -- TDR chunk retrieval only
        (extract_tdr's _retrieve_relevant_chunks). Safe to fall back to
        Gemini here since nothing is persisted or compared across calls --
        see _FallbackEmbeddings.
        """
        ollama = OllamaEmbeddings(
            model=self._settings.embedding_model, base_url=self._settings.ollama_base_url
        )
        gemini_key = self._pools["gemini"].next_available_key()
        gemini = GoogleGenerativeAIEmbeddings(
            model=self._settings.gemini_embedding_model,
            api_key=SecretStr(gemini_key) if gemini_key else None,
        )
        return _FallbackEmbeddings(ollama, gemini)

    @property
    def usage_totals(self) -> dict[str, Any]:
        """Accumulated token usage across this router's whole lifetime,
        keyed by model name -- for future measurement scripts to read
        in-process (see docs/04-evaluation-metrics.md).
        """
        return self._usage_handler.usage_metadata

    def _log_usage(self, provider: str, tier: str, model_name: str) -> None:
        usage = self._usage_handler.usage_metadata.get(model_name)
        if usage is None:
            return
        logger.info(
            "llm.usage provider=%s tier=%s model=%s input_tokens=%s output_tokens=%s total_tokens=%s",
            provider,
            tier,
            model_name,
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            usage.get("total_tokens"),
        )

    def _invoke(
        self,
        tier: str,
        messages: Sequence[BaseMessage],
        structured_output: type[Any] | None,
    ) -> Any:
        for provider, pool in self._pools.items():
            model_name = self._models[(provider, tier)]
            result = self._try_pool(provider, tier, pool, model_name, messages, structured_output)
            if result is not _POOL_EXHAUSTED:
                return result

        model_name = self._models[("ollama", tier)]
        logger.warning("llm.fallback_to_ollama model=%s", model_name)
        ollama_model = ChatOllama(
            model=model_name, base_url=self._settings.ollama_base_url, temperature=0
        )
        config: RunnableConfig = {"callbacks": [self._usage_handler]}
        result = _invoke_model(ollama_model, messages, structured_output, config)
        self._log_usage("ollama", tier, model_name)
        return result

    def _try_pool(
        self,
        provider: str,
        tier: str,
        pool: KeyPool,
        model_name: str,
        messages: Sequence[BaseMessage],
        structured_output: type[Any] | None,
    ) -> Any:
        for _ in range(len(pool.keys)):
            key = pool.next_available_key()
            if key is None:
                return _POOL_EXHAUSTED
            model = _build_chat_model(provider, model_name, key)
            try:
                config: RunnableConfig = {"callbacks": [self._usage_handler]}
                result = _invoke_model(model, messages, structured_output, config)
                self._log_usage(provider, tier, model_name)
                return result
            except Exception as exc:
                if not _is_retryable(exc):
                    raise
                logger.warning(
                    "llm.call_failed_rotating provider=%s error=%s", provider, type(exc).__name__
                )
                pool.mark_rate_limited(key)
        return _POOL_EXHAUSTED
