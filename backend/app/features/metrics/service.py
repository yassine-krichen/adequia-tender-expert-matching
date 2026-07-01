from typing import Any


class MetricsService:
    """Surfaces the eval harness output — see docs/04-evaluation-metrics.md."""

    async def get_current_metrics(self) -> dict[str, Any]:
        raise NotImplementedError
