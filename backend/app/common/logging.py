import logging
import sys


def configure_logging(level: str) -> None:
    """Structured logging setup. Never log secrets, tokens, or raw CV/TDR payloads."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
