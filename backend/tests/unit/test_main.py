from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.main import create_app

_REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
    "REDIS_URL": "redis://localhost",
    "GROQ_API_KEYS": "",
    "GEMINI_API_KEYS": "",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "GROQ_EXTRACTION_MODEL": "m",
    "GROQ_REASONING_MODEL": "m",
    "GEMINI_EXTRACTION_MODEL": "m",
    "GEMINI_REASONING_MODEL": "m",
    "OLLAMA_EXTRACTION_MODEL": "m",
    "OLLAMA_REASONING_MODEL": "m",
    "EMBEDDING_MODEL": "nomic-embed-text",
    "ENVIRONMENT": "development",
}


@pytest.fixture
def _app_with_required_env(monkeypatch: pytest.MonkeyPatch) -> Generator[FastAPI, None, None]:
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        yield create_app()
    finally:
        get_settings.cache_clear()


def test_cors_allows_the_frontend_dev_origin(_app_with_required_env: FastAPI) -> None:
    """Regression: no CORSMiddleware meant every browser request from the
    Next.js dev server (localhost:3000) to the API (localhost:8000) was
    blocked outright — the frontend just saw a generic network error.
    """
    client = TestClient(_app_with_required_env)

    response = client.options(
        "/candidates/cv",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_an_unlisted_origin(_app_with_required_env: FastAPI) -> None:
    client = TestClient(_app_with_required_env)

    response = client.options(
        "/candidates/cv",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers
