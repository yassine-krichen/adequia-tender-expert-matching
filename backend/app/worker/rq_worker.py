from redis import Redis
from rq import Worker

from app.common.logging import configure_logging
from app.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    connection = Redis.from_url(settings.redis_url)
    worker = Worker(["default"], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
