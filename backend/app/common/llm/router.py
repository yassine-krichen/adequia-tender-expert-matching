import logging
from collections.abc import Sequence
from typing import Any, Protocol

from google.genai.errors import ClientError as GeminiClientError
from groq import RateLimitError as GroqRateLimitError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama, OllamaEmbeddings
from pydantic import SecretStr

from app.common.llm.key_pool import KeyPool, parse_key_pool
from app.config.settings import Settings

logger = logging.getLogger(__name__)

_POOL_EXHAUSTED = object()


def _is_rate_limited(exc: Exception) -> bool:
    if isinstance(exc, GroqRateLimitError):
        return True
    return isinstance(exc, GeminiClientError) and exc.code == 429


def _build_chat_model(provider: str, model_name: str, api_key: str) -> BaseChatModel:
    if provider == "groq":
        return ChatGroq(model=model_name, api_key=SecretStr(api_key))
    return ChatGoogleGenerativeAI(model=model_name, api_key=SecretStr(api_key))


def _invoke_model(
    model: BaseChatModel, messages: Sequence[BaseMessage], structured_output: type[Any] | None
) -> Any:
    if structured_output is not None:
        return model.with_structured_output(structured_output).invoke(messages)
    return model.invoke(messages)


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
    to local Ollama once every key in both pools is rate-limited.

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

    def invoke_extraction(
        self, messages: Sequence[BaseMessage], structured_output: type[Any] | None = None
    ) -> Any:
        return self._invoke("extraction", messages, structured_output)

    def invoke_reasoning(
        self, messages: Sequence[BaseMessage], structured_output: type[Any] | None = None
    ) -> Any:
        return self._invoke("reasoning", messages, structured_output)

    def get_embedding_model(self) -> OllamaEmbeddings:
        return OllamaEmbeddings(
            model=self._settings.embedding_model, base_url=self._settings.ollama_base_url
        )

    def _invoke(
        self,
        tier: str,
        messages: Sequence[BaseMessage],
        structured_output: type[Any] | None,
    ) -> Any:
        for provider, pool in self._pools.items():
            model_name = self._models[(provider, tier)]
            result = self._try_pool(provider, pool, model_name, messages, structured_output)
            if result is not _POOL_EXHAUSTED:
                return result

        model_name = self._models[("ollama", tier)]
        logger.warning("llm.fallback_to_ollama model=%s", model_name)
        ollama_model = ChatOllama(model=model_name, base_url=self._settings.ollama_base_url)
        return _invoke_model(ollama_model, messages, structured_output)

    def _try_pool(
        self,
        provider: str,
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
                return _invoke_model(model, messages, structured_output)
            except Exception as exc:
                if not _is_rate_limited(exc):
                    raise
                logger.warning("llm.rate_limited provider=%s", provider)
                pool.mark_rate_limited(key)
        return _POOL_EXHAUSTED
