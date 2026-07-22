import os

import pytest

from app.common.tracing import configure_langsmith_tracing
from app.config.settings import Settings


def _make_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "redis_url": "redis://localhost",
        "groq_api_keys": "",
        "gemini_api_keys": "",
        "ollama_base_url": "http://localhost:11434",
        "groq_extraction_model": "m",
        "groq_reasoning_model": "m",
        "gemini_extraction_model": "m",
        "gemini_reasoning_model": "m",
        "ollama_extraction_model": "m",
        "ollama_reasoning_model": "m",
        "embedding_model": "nomic-embed-text",
        "langsmith_project": "adequia-test",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def _pop_langsmith_env() -> None:
    for key in ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT", "LANGSMITH_ENDPOINT"):
        os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def _clean_langsmith_env() -> None:
    # Teardown (after yield) matters just as much as setup here: without
    # it, whatever env vars the last test in this module sets (a fake
    # LANGSMITH_API_KEY="test-key" with LANGSMITH_TRACING=true) leak into
    # every test file collected after this one in the same pytest session
    # -- e.g. extract_cv/extract_tdr's @traceable decorators (ADQ-31) would
    # then attempt real (failing) network calls under a fake key.
    _pop_langsmith_env()
    yield
    _pop_langsmith_env()


def test_configure_langsmith_tracing_sets_env_vars_when_key_present() -> None:
    settings = _make_settings(langsmith_api_key="test-key")

    configure_langsmith_tracing(settings)

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "test-key"
    assert os.environ["LANGSMITH_PROJECT"] == "adequia-test"


def test_configure_langsmith_tracing_is_a_noop_without_a_key() -> None:
    settings = _make_settings(langsmith_api_key=None)

    configure_langsmith_tracing(settings)

    assert "LANGSMITH_TRACING" not in os.environ


def test_configure_langsmith_tracing_sets_endpoint_when_configured() -> None:
    """Regression: a 403 Forbidden on trace ingestion for an EU-region
    LangSmith account is fixed by pointing at the EU endpoint instead of
    the (US-only) default.
    """
    settings = _make_settings(
        langsmith_api_key="test-key", langsmith_endpoint="https://eu.api.smith.langchain.com"
    )

    configure_langsmith_tracing(settings)

    assert os.environ["LANGSMITH_ENDPOINT"] == "https://eu.api.smith.langchain.com"


def test_configure_langsmith_tracing_leaves_endpoint_unset_by_default() -> None:
    settings = _make_settings(langsmith_api_key="test-key", langsmith_endpoint=None)

    configure_langsmith_tracing(settings)

    assert "LANGSMITH_ENDPOINT" not in os.environ
