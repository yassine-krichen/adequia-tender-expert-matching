from typing import Literal

from pydantic import BaseModel


class MetricGroup(BaseModel):
    """One entry in the metrics dashboard — one per eval area.

    Shared shape across every group so the frontend never special-cases a
    metric: status="available" carries the real numbers, status="pending"
    carries only pending_reason. See docs/04-evaluation-metrics.md's status
    box for where each number comes from and what's still outstanding.
    """

    status: Literal["available", "pending"]
    values: dict[str, float | int | str] | None = None
    dataset: str | None = None
    sample_size: int | None = None
    computed_at: str | None = None
    note: str | None = None
    pending_reason: str | None = None


class MetricsSnapshot(BaseModel):
    """GET /metrics response — see backend/app/features/metrics/current_snapshot.json
    for the hand-populated values this loads, and docs/04-evaluation-metrics.md
    for methodology and what's still pending.
    """

    extraction: MetricGroup
    retrieval: MetricGroup
    anomaly_detection: MetricGroup
    guardrails: MetricGroup
    scoring_agreement: MetricGroup
    report_quality: MetricGroup
    efficiency: MetricGroup
