import itertools
import time
from collections.abc import Iterator


def parse_key_pool(raw: str) -> list[str]:
    """GROQ_API_KEYS/GEMINI_API_KEYS are comma-separated lists of free-tier keys."""
    return [key.strip() for key in raw.split(",") if key.strip()]


class KeyPool:
    """Round-robins a provider's API keys, cooling down keys that hit a
    rate limit instead of dropping them permanently — they retry once the
    cooldown elapses. An empty pool (no keys configured yet) always reports
    exhausted, which lets the router fall through to the next provider or
    Ollama rather than crashing.
    """

    def __init__(self, provider: str, keys: list[str], cooldown_seconds: float = 60.0) -> None:
        self.provider = provider
        self.keys = keys
        self.cooldown_seconds = cooldown_seconds
        self._cooldown_until: dict[str, float] = {}
        self._cycle: Iterator[str] = itertools.cycle(keys)

    def mark_rate_limited(self, key: str) -> None:
        self._cooldown_until[key] = time.monotonic() + self.cooldown_seconds

    def next_available_key(self) -> str | None:
        """Returns the next key not currently cooling down, or None if every
        key in the pool is on cooldown (or the pool is empty).
        """
        for _ in range(len(self.keys)):
            key = next(self._cycle)
            if time.monotonic() >= self._cooldown_until.get(key, 0.0):
                return key
        return None
