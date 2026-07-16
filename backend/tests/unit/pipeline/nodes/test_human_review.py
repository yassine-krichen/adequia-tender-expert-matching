import inspect
from typing import Any

import pytest

from app.domain.matching import Anomaly, AnomalySeverity, AnomalyType, ReviewDecision
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes import human_review as human_review_module
from app.features.pipeline.nodes.human_review import human_review
from app.features.pipeline.state import PipelineState


def _position() -> ExpertPosition:
    return ExpertPosition(position_id="p1", position_title="Chef de projet", source_span="span")


def _state(
    *,
    compatibility_score: float | None = 0.8,
    hard_filter_passed: bool = True,
    hard_filter_failures: list[str] | None = None,
    rationale: str | None = "Solid fit.",
    anomalies: list[Anomaly] | None = None,
) -> PipelineState:
    return {
        "cv_raw_text": "raw cv",
        "tdr_raw_text": "raw tdr",
        "position": _position(),
        "cv_extracted": None,
        "normalized_skills": [],
        "normalized_position_skills": [],
        "required_sector_vector": None,
        "sector": None,
        "hard_filter_passed": hard_filter_passed,
        "hard_filter_failures": hard_filter_failures or [],
        "sub_scores": None,
        "compatibility_score": compatibility_score,
        "qualitative_fit_reasoning": None,
        "sector_match_source_span": None,
        "anomalies": anomalies or [],
        "rationale": rationale,
        "citations": [],
        "needs_human_review": False,
        "reviewer_decision": None,
    }


def test_human_review_is_an_async_callable_with_the_expected_node_signature() -> None:
    # interrupt() itself can't be meaningfully exercised outside a real
    # running graph -- it's designed to pause the whole run, not return a
    # value, until a later ainvoke(Command(resume=...)) resumes it. The
    # realistic unit-testable surface is the node's shape, plus its
    # post-resume mapping logic (below), with interrupt() mocked.
    assert inspect.iscoroutinefunction(human_review)
    signature = inspect.signature(human_review)
    assert list(signature.parameters) == ["state"]


async def test_human_review_maps_a_mocked_resume_value_into_reviewer_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payload: dict[str, Any] = {}

    def _fake_interrupt(payload: dict[str, Any]) -> dict[str, Any]:
        captured_payload.update(payload)
        return {"decision": "overridden_to_approve", "note": "Overriding a false-negative."}

    monkeypatch.setattr(human_review_module, "interrupt", _fake_interrupt)
    anomaly = Anomaly(
        type=AnomalyType.employment_gap,
        severity=AnomalySeverity.warning,
        description="120-day gap",
        source_citation="span-a",
    )
    state = _state(
        compatibility_score=0.42,
        hard_filter_passed=False,
        hard_filter_failures=["Missing mandatory diploma: Bac+5"],
        rationale="Rejected on hard filter.",
        anomalies=[anomaly],
    )

    result = await human_review(state)

    assert result == {"reviewer_decision": ReviewDecision.overridden_to_approve}
    # The interrupt payload carries hard_filter_passed/hard_filter_failures
    # (beyond a bare score) so a reviewer sees *why* a candidate failed --
    # see human_review's docstring.
    assert captured_payload["compatibility_score"] == 0.42
    assert captured_payload["hard_filter_passed"] is False
    assert captured_payload["hard_filter_failures"] == ["Missing mandatory diploma: Bac+5"]
    assert captured_payload["rationale"] == "Rejected on hard filter."
    assert captured_payload["anomalies"] == [
        {
            "type": "employment_gap",
            "severity": "warning",
            "description": "120-day gap",
            "source_citation": "span-a",
        }
    ]


@pytest.mark.parametrize(
    "decision_value",
    ["approved", "rejected", "overridden_to_approve", "overridden_to_reject"],
)
async def test_human_review_maps_every_review_decision_value_from_the_resume_payload(
    decision_value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        human_review_module, "interrupt", lambda payload: {"decision": decision_value, "note": None}
    )

    result = await human_review(_state())

    assert result == {"reviewer_decision": ReviewDecision(decision_value)}
