import json
from pathlib import Path

from app.features.metrics.schemas import MetricsSnapshot

_SNAPSHOT_PATH = Path(__file__).parent / "current_snapshot.json"


class MetricsService:
    """Surfaces the eval harness output — see docs/04-evaluation-metrics.md."""

    async def get_current_metrics(self) -> MetricsSnapshot:
        # A static, hand-populated local file — a synchronous read is fine
        # here, no async I/O ceremony needed for something this small.
        raw = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        return MetricsSnapshot.model_validate(raw)
