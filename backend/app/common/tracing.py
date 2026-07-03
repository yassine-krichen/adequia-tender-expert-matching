import os

from app.config.settings import Settings


def configure_langsmith_tracing(settings: Settings) -> None:
    """Enables LangSmith tracing for every LangChain call in this process.

    LangChain reads these as OS environment variables, not from our own
    Settings object, so this must run before any chat model is
    constructed. No-op if no API key is configured — tracing stays off.
    """
    if not settings.langsmith_api_key:
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
