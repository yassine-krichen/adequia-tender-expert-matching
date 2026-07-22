import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.features.metrics.schemas import MetricsSnapshot
from app.features.metrics.service import MetricsService

_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[4] / "app" / "features" / "metrics" / "current_snapshot.json"
)

_AVAILABLE_GROUPS = (
    "extraction",
    "retrieval",
    "anomaly_detection",
    "guardrails",
    "scoring_agreement",
    "report_quality",
    "efficiency",
)
# All 7 groups are now available as of ADQ-33's final metrics pass -- kept
# as an explicit empty tuple (rather than deleting the parametrized test
# below) so a future group added back in "pending" status is still covered
# by the same test without needing new test code.
_PENDING_GROUPS: tuple[str, ...] = ()


def _raw_snapshot() -> dict:
    return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))


# --- get_current_metrics against the real snapshot file ------------------


async def test_get_current_metrics_returns_a_snapshot_that_validates_against_the_schema() -> None:
    service = MetricsService()

    snapshot = await service.get_current_metrics()

    assert isinstance(snapshot, MetricsSnapshot)


@pytest.mark.parametrize("group_name", _AVAILABLE_GROUPS)
async def test_get_current_metrics_reports_available_status_for_eval_covered_groups(
    group_name: str,
) -> None:
    service = MetricsService()

    snapshot = await service.get_current_metrics()

    group = getattr(snapshot, group_name)
    assert group.status == "available"
    assert group.values is not None
    assert group.dataset is not None


@pytest.mark.parametrize("group_name", _PENDING_GROUPS)
async def test_get_current_metrics_reports_pending_status_for_groups_not_yet_evaluated(
    group_name: str,
) -> None:
    service = MetricsService()

    snapshot = await service.get_current_metrics()

    group = getattr(snapshot, group_name)
    assert group.status == "pending"
    assert group.pending_reason is not None
    assert group.values is None


async def test_get_current_metrics_reads_the_real_values_recorded_for_extraction() -> None:
    """Pins the actual hand-populated numbers so an accidental edit to
    current_snapshot.json that silently drops a value is caught."""
    service = MetricsService()

    snapshot = await service.get_current_metrics()

    assert snapshot.extraction.values == {
        "tdr_pass_rate": 0.923,
        "tdr_passed": 12,
        "tdr_total": 13,
        "cv_pass_rate": 1.0,
        "cv_passed": 11,
        "cv_total": 11,
    }
    assert snapshot.extraction.sample_size == 24


async def test_get_current_metrics_reads_the_real_values_recorded_for_scoring_agreement() -> None:
    """Pins the real Cohen's kappa/n computed by scripts/measure_scoring_agreement.py
    against live match_results.reviewer_decision data (ADQ-33) -- n=2 is a
    small real sample (only 2 reviewed match_results exist so far), not a
    placeholder."""
    service = MetricsService()

    snapshot = await service.get_current_metrics()

    assert snapshot.scoring_agreement.values == {"cohens_kappa": 1.0, "n": 2}
    assert snapshot.scoring_agreement.sample_size == 2


async def test_get_current_metrics_reads_the_real_values_recorded_for_report_quality() -> None:
    """Pins the real faithfulness/citation_coverage computed by
    test_report_faithfulness_quality.py (ADQ-29) against live LLM judge
    calls."""
    service = MetricsService()

    snapshot = await service.get_current_metrics()

    assert snapshot.report_quality.values == {"faithfulness": 0.91, "citation_coverage": 1.0}
    assert snapshot.report_quality.sample_size == 11


async def test_get_current_metrics_reads_the_real_values_recorded_for_efficiency() -> None:
    """Pins the real per-node latency computed by scripts/measure_efficiency.py
    (ADQ-33) against real pipeline node calls -- cost_usd is a hard $0 fact
    (free-tier-only architecture), not a measurement."""
    service = MetricsService()

    snapshot = await service.get_current_metrics()

    assert snapshot.efficiency.values == {
        "overall_per_match_p50_s": 3.52,
        "overall_per_match_p95_s": 4.65,
        "extract_tdr_p50_s": 838.65,
        "extract_cv_p50_s": 195.42,
        "cost_usd": 0.0,
    }
    assert snapshot.efficiency.sample_size == 28


# --- MetricsSnapshot schema validation ------------------------------------


def test_metrics_snapshot_raises_validation_error_when_a_group_is_missing_entirely() -> None:
    raw = _raw_snapshot()
    del raw["extraction"]

    with pytest.raises(ValidationError):
        MetricsSnapshot.model_validate(raw)


def test_metrics_snapshot_raises_validation_error_when_a_groups_status_field_is_missing() -> None:
    raw = copy.deepcopy(_raw_snapshot())
    del raw["extraction"]["status"]

    with pytest.raises(ValidationError):
        MetricsSnapshot.model_validate(raw)


def test_metrics_snapshot_raises_validation_error_when_status_is_not_a_string() -> None:
    raw = copy.deepcopy(_raw_snapshot())
    raw["extraction"]["status"] = 123

    with pytest.raises(ValidationError):
        MetricsSnapshot.model_validate(raw)


def test_metrics_snapshot_raises_validation_error_when_values_is_not_a_mapping() -> None:
    raw = copy.deepcopy(_raw_snapshot())
    raw["extraction"]["values"] = "not-a-dict"

    with pytest.raises(ValidationError):
        MetricsSnapshot.model_validate(raw)
