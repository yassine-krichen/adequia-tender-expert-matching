from redis import Redis
from rq import Worker

from app.common.logging import configure_logging
from app.common.tracing import configure_langsmith_tracing
from app.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    # Every real pipeline node call (extraction, matching, review resume)
    # actually executes here, in the worker process -- not in app/main.py's
    # FastAPI process. Without this, LangSmith tracing silently does
    # nothing for the work that matters (ADQ-31).
    configure_langsmith_tracing(settings)
    connection = Redis.from_url(settings.redis_url)
    worker = Worker(["default"], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
