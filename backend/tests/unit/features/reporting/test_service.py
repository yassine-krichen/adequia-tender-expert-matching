import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Interrupt, StateSnapshot
from sqlalchemy import inspect as sa_inspect

from app.common.exceptions import (
    AlreadyReviewedError,
    NoPendingReviewError,
    NotFoundError,
    ReviewPersistenceFailedError,
    ValidationFailedError,
)
from app.database.models import CV as CVModel
from app.database.models import TDR as TDRModel
from app.database.models import Anomaly as AnomalyModel
from app.database.models import Candidate as CandidateModel
from app.database.models import ExpertPosition as ExpertPositionModel
from app.database.models import HistoricalDecision as HistoricalDecisionModel
from app.database.models import MatchResult as MatchResultModel
from app.domain.matching import ReviewDecision
from app.features.reporting import service as reporting_service_module
from app.features.reporting.service import ReportingService


class _FakeEmbeddings:
    pass


class _FakeRouter:
    """Only get_embedding_model is exercised at construction time -- the
    router itself is never invoked by get_match/submit_review's own logic,
    only threaded through to build_matching_graph, which every test here
    that reaches the graph-building step replaces with a fake."""

    def get_embedding_model(self) -> _FakeEmbeddings:
        return _FakeEmbeddings()


class _FakeScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _FakeExecuteResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeSession:
    """Mirrors tests/unit/features/tdrs/test_service.py's fake-session
    convention: session.get looks up a pre-seeded row by the model's real
    primary-key column (via sqlalchemy inspection, so it works for both
    MatchResultModel.match_id and CVModel.cv_id without hardcoding either),
    session.execute always returns whatever anomaly rows were pre-seeded
    (parsing the actual `select(...).where(...)` statement isn't attempted,
    same simplification the existing fakes already make).
    """

    def __init__(self, rows: list[Any] | None = None, anomalies: list[Any] | None = None) -> None:
        self.added: list[Any] = [*(rows or [])]
        self._anomalies = anomalies or []
        self.committed = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def get(self, model_cls: type[Any], pk: Any) -> Any | None:
        pk_attr = sa_inspect(model_cls).primary_key[0].name
        for obj in self.added:
            if isinstance(obj, model_cls) and getattr(obj, pk_attr, None) == pk:
                return obj
        return None

    async def execute(self, _stmt: Any) -> _FakeExecuteResult:
        return _FakeExecuteResult(self._anomalies)


class _FailingCommitSession(_FakeSession):
    """Simulates a commit that fails after the checkpoint has already been
    resumed -- e.g. a dropped DB connection or a constraint violation."""

    async def commit(self) -> None:
        raise RuntimeError("connection dropped during commit")


class _FakeCompiledGraph:
    """Stands in for CompiledStateGraph.compile(checkpointer=...)'s return
    value -- only aget_state/ainvoke are ever called by submit_review."""

    def __init__(self, snapshot: StateSnapshot) -> None:
        self._snapshot = snapshot
        self.ainvoke_calls: list[tuple[Any, Any]] = []

    async def aget_state(self, config: Any) -> StateSnapshot:
        return self._snapshot

    async def ainvoke(self, command: Any, config: Any) -> dict[str, Any]:
        self.ainvoke_calls.append((command, config))
        return {}


class _FakeGraphBuilder:
    def __init__(self, compiled: _FakeCompiledGraph) -> None:
        self._compiled = compiled

    def compile(self, checkpointer: Any) -> _FakeCompiledGraph:
        return self._compiled


def _pending_snapshot() -> StateSnapshot:
    return StateSnapshot(
        values={},
        next=("human_review",),
        config={},
        metadata=None,
        created_at=None,
        parent_config=None,
        tasks=(),
        interrupts=(Interrupt(value={"compatibility_score": 0.8}),),
    )


def _no_interrupt_snapshot() -> StateSnapshot:
    return StateSnapshot(
        values={},
        next=(),
        config={},
        metadata=None,
        created_at=None,
        parent_config=None,
        tasks=(),
        interrupts=(),
    )


def _stranded_snapshot(reviewer_decision: str) -> StateSnapshot:
    """A graph that already fully completed a resume in a prior call --
    values carries the decision that was actually recorded in the
    checkpoint -- but (per the still-NULL match_row we control in the test)
    the DB write-back that should have followed never landed."""
    return StateSnapshot(
        values={"reviewer_decision": reviewer_decision},
        next=(),
        config={},
        metadata=None,
        created_at=None,
        parent_config=None,
        tasks=(),
        interrupts=(),
    )


def _patch_graph(monkeypatch: pytest.MonkeyPatch, compiled: _FakeCompiledGraph) -> None:
    """Patches the two seams submit_review builds inline per call: the
    Postgres checkpointer context manager and build_matching_graph itself
    (both constructed inline in service.py, per the confirmed design --
    there's no constructor injection point to substitute instead)."""

    @asynccontextmanager
    async def _fake_from_conn_string(conn_string: str, **kwargs: Any) -> Any:
        yield object()

    monkeypatch.setattr(AsyncPostgresSaver, "from_conn_string", _fake_from_conn_string)
    monkeypatch.setattr(
        reporting_service_module,
        "build_matching_graph",
        lambda **kwargs: _FakeGraphBuilder(compiled),
    )


def _explode_if_graph_touched(monkeypatch: pytest.MonkeyPatch, label: str) -> None:
    """Patches the same two seams to raise if ever reached -- used to prove
    an error path short-circuits before any LangGraph/checkpointer work."""

    @asynccontextmanager
    async def _exploding_from_conn_string(conn_string: str, **kwargs: Any) -> Any:
        raise AssertionError(f"checkpointer must not be constructed: {label}")
        yield  # pragma: no cover -- unreachable, keeps this an async generator

    def _exploding_build_matching_graph(**kwargs: Any) -> Any:
        raise AssertionError(f"build_matching_graph must not be called: {label}")

    monkeypatch.setattr(AsyncPostgresSaver, "from_conn_string", _exploding_from_conn_string)
    monkeypatch.setattr(
        reporting_service_module, "build_matching_graph", _exploding_build_matching_graph
    )


def _match_row(match_id: UUID, cv_id: UUID, **overrides: Any) -> MatchResultModel:
    defaults: dict[str, Any] = dict(
        match_id=match_id,
        cv_id=cv_id,
        tdr_id=uuid4(),
        position_id=uuid4(),
        hard_filter_passed=True,
        hard_filter_failures_json=[],
        compatibility_score=0.8,
        sub_scores_json=None,
        rationale="Solid fit.",
        citations_json=[],
        reviewer_decision=None,
        reviewer_id=None,
        reviewer_note=None,
        decided_at=None,
    )
    defaults.update(overrides)
    return MatchResultModel(**defaults)


def _report_context_rows(
    match_row: MatchResultModel,
    *,
    cv_row: CVModel | None = None,
    candidate_full_name: str = "Test Candidate",
    position_title: str = "Test Position",
    tdr_mission_title: str = "Test Mission",
) -> list[Any]:
    """Seeds the FK-guaranteed rows get_match now joins across (CV ->
    Candidate, ExpertPosition, TDR) so tests hit real rows instead of the
    new assert-not-None guards. Pass cv_row when a test already needs a
    specific candidate_id (e.g. for historical_decision assertions) --
    otherwise one is created here.
    """
    if cv_row is None:
        cv_row = CVModel(
            cv_id=match_row.cv_id, candidate_id=uuid4(), raw_text="raw", extracted_json={}
        )
    candidate_row = CandidateModel(candidate_id=cv_row.candidate_id, full_name=candidate_full_name)
    position_row = ExpertPositionModel(
        position_id=match_row.position_id, position_title=position_title, requirements_json={}
    )
    tdr_row = TDRModel(tdr_id=match_row.tdr_id, mission_title=tdr_mission_title)
    return [cv_row, candidate_row, position_row, tdr_row]


def _service() -> ReportingService:
    return ReportingService(router=_FakeRouter())  # type: ignore[arg-type]


# --- get_match -----------------------------------------------------------


async def test_get_match_raises_not_found_error_for_an_unknown_match_id() -> None:
    service = _service()
    session = _FakeSession()

    with pytest.raises(NotFoundError):
        await service.get_match(uuid4(), session)  # type: ignore[arg-type]


async def test_get_match_assembles_anomalies_citations_and_sub_scores_from_stored_json() -> None:
    match_id, cv_id = uuid4(), uuid4()
    row = _match_row(
        match_id,
        cv_id,
        citations_json=[
            {"claim": "5 years experience", "source_doc": "cv", "source_span": "5 ans d'expérience"}
        ],
        sub_scores_json={"sector_score": 0.9, "skill_score": 0.7},
        reviewer_decision="approved",
        reviewer_id="anonymous",
        reviewer_note="Looks solid.",
        decided_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    anomaly_row = AnomalyModel(
        match_id=match_id,
        type="employment_gap",
        severity="warning",
        description="120-day gap",
        source_citation="span-a",
    )
    session = _FakeSession(
        rows=[
            row,
            *_report_context_rows(
                row,
                candidate_full_name="Nadia Ben Salah",
                position_title="Senior Consultant",
                tdr_mission_title="Digital Transformation Mission",
            ),
        ],
        anomalies=[anomaly_row],
    )
    service = _service()

    result = await service.get_match(match_id, session)  # type: ignore[arg-type]

    assert len(result.anomalies) == 1
    assert result.anomalies[0].description == "120-day gap"
    assert result.anomalies[0].source_citation == "span-a"
    assert len(result.citations) == 1
    assert result.citations[0].claim == "5 years experience"
    assert result.sub_scores is not None
    assert result.sub_scores.sector_score == 0.9
    assert result.sub_scores.skill_score == 0.7
    assert result.reviewer_decision == "approved"
    assert result.reviewer_id == "anonymous"
    assert result.reviewer_note == "Looks solid."
    assert result.decided_at == datetime(2026, 1, 1, 12, 0, 0)
    assert result.candidate_full_name == "Nadia Ben Salah"
    assert result.position_title == "Senior Consultant"
    assert result.tdr_mission_title == "Digital Transformation Mission"


async def test_get_match_sub_scores_is_none_when_sub_scores_json_column_is_none() -> None:
    match_id, cv_id = uuid4(), uuid4()
    row = _match_row(match_id, cv_id, sub_scores_json=None)
    session = _FakeSession(rows=[row, *_report_context_rows(row)])
    service = _service()

    result = await service.get_match(match_id, session)  # type: ignore[arg-type]

    assert result.sub_scores is None


# --- submit_review: not found / already reviewed / note validation ------


async def test_submit_review_raises_not_found_error_for_an_unknown_match_id() -> None:
    service = _service()
    session = _FakeSession()

    with pytest.raises(NotFoundError):
        await service.submit_review(uuid4(), ReviewDecision.approved, None, session)  # type: ignore[arg-type]


async def test_submit_review_raises_already_reviewed_error_without_touching_the_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    match_id, cv_id = uuid4(), uuid4()
    row = _match_row(match_id, cv_id, reviewer_decision="approved")
    session = _FakeSession(rows=[row])
    service = _service()
    _explode_if_graph_touched(monkeypatch, "already-reviewed check must run first")

    with pytest.raises(AlreadyReviewedError):
        await service.submit_review(match_id, ReviewDecision.rejected, None, session)  # type: ignore[arg-type]

    assert session.committed is False


@pytest.mark.parametrize(
    "decision", [ReviewDecision.overridden_to_approve, ReviewDecision.overridden_to_reject]
)
@pytest.mark.parametrize("note", [None, "", "   "])
async def test_submit_review_raises_validation_failed_error_for_an_override_without_a_real_note(
    decision: ReviewDecision, note: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    match_id, cv_id = uuid4(), uuid4()
    row = _match_row(match_id, cv_id)
    session = _FakeSession(rows=[row])
    service = _service()
    _explode_if_graph_touched(monkeypatch, "note validation must run before graph work")

    with pytest.raises(ValidationFailedError):
        await service.submit_review(match_id, decision, note, session)  # type: ignore[arg-type]

    assert session.committed is False


@pytest.mark.parametrize("decision", [ReviewDecision.approved, ReviewDecision.rejected])
async def test_submit_review_does_not_require_a_note_for_a_plain_approve_or_reject(
    decision: ReviewDecision, monkeypatch: pytest.MonkeyPatch
) -> None:
    match_id, cv_id = uuid4(), uuid4()
    row = _match_row(match_id, cv_id)
    cv_row = CVModel(cv_id=cv_id, candidate_id=uuid4(), raw_text="raw", extracted_json={})
    session = _FakeSession(rows=[row, *_report_context_rows(row, cv_row=cv_row)])
    service = _service()
    _patch_graph(monkeypatch, _FakeCompiledGraph(_pending_snapshot()))

    # Must not raise ValidationFailedError even though note is None.
    result = await service.submit_review(match_id, decision, None, session)  # type: ignore[arg-type]

    assert result.reviewer_decision == decision.value


# --- submit_review: NoPendingReviewError ---------------------------------


async def test_submit_review_raises_no_pending_review_error_when_snapshot_has_no_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    match_id, cv_id = uuid4(), uuid4()
    row = _match_row(match_id, cv_id)
    session = _FakeSession(rows=[row])
    service = _service()
    compiled = _FakeCompiledGraph(_no_interrupt_snapshot())
    _patch_graph(monkeypatch, compiled)

    with pytest.raises(NoPendingReviewError):
        await service.submit_review(match_id, ReviewDecision.approved, None, session)  # type: ignore[arg-type]

    assert compiled.ainvoke_calls == []  # resume must never be attempted
    assert row.reviewer_decision is None  # match row left untouched
    assert session.committed is False


# --- submit_review: stranded resume recovery ------------------------------


async def test_submit_review_recovers_a_stranded_resume_without_calling_ainvoke_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulates a prior call whose ainvoke(Command(resume=...)) succeeded
    and durably completed the checkpoint thread, but whose DB write-back
    crashed before commit -- match_row.reviewer_decision is still None even
    though the checkpoint (per snapshot.values) already recorded a decision.
    A retry must recover by writing the current request's decision/note
    straight to the DB, without touching the (already fully consumed)
    graph again."""
    match_id, cv_id = uuid4(), uuid4()
    row = _match_row(match_id, cv_id)
    cv_row = CVModel(cv_id=cv_id, candidate_id=uuid4(), raw_text="raw", extracted_json={})
    session = _FakeSession(rows=[row, *_report_context_rows(row, cv_row=cv_row)])
    service = _service()
    compiled = _FakeCompiledGraph(_stranded_snapshot("approved"))
    _patch_graph(monkeypatch, compiled)

    note = "Retrying after a dropped connection on the first attempt."
    result = await service.submit_review(match_id, ReviewDecision.overridden_to_approve, note, session)  # type: ignore[arg-type]

    assert compiled.ainvoke_calls == []  # thread already fully consumed -- must not resume again
    assert row.reviewer_decision == "overridden_to_approve"  # this call's decision wins
    assert row.reviewer_id == "anonymous"
    assert row.reviewer_note == note
    assert row.decided_at is not None
    assert session.committed is True
    historical_rows = [obj for obj in session.added if isinstance(obj, HistoricalDecisionModel)]
    assert len(historical_rows) == 1
    assert historical_rows[0].was_selected is True
    assert historical_rows[0].outcome_note == note
    assert result.reviewer_decision == "overridden_to_approve"


async def test_submit_review_logs_a_warning_when_the_stranded_decision_differs_from_the_retry(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    match_id, cv_id = uuid4(), uuid4()
    row = _match_row(match_id, cv_id)
    cv_row = CVModel(cv_id=cv_id, candidate_id=uuid4(), raw_text="raw", extracted_json={})
    session = _FakeSession(rows=[row, *_report_context_rows(row, cv_row=cv_row)])
    service = _service()
    compiled = _FakeCompiledGraph(_stranded_snapshot("rejected"))
    _patch_graph(monkeypatch, compiled)

    with caplog.at_level(logging.WARNING):
        result = await service.submit_review(match_id, ReviewDecision.approved, None, session)  # type: ignore[arg-type]

    # Still proceeds with the request's own decision -- the reviewer is
    # asserting that's what they mean now -- just flags the discrepancy.
    assert result.reviewer_decision == "approved"
    assert any(
        record.levelno == logging.WARNING and str(match_id) in record.getMessage()
        for record in caplog.records
    )


# --- submit_review: write-back failure after a successful resume ---------


async def test_submit_review_raises_review_persistence_failed_error_when_the_db_write_back_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The checkpoint resume itself succeeds (ainvoke is called), but the
    subsequent DB commit fails -- this must not fail silently: it should
    raise a distinctly-named domain error and log at error level with the
    match_id, so an operator can grep for this exact stranded-resume
    scenario."""
    match_id, cv_id = uuid4(), uuid4()
    row = _match_row(match_id, cv_id)
    cv_row = CVModel(cv_id=cv_id, candidate_id=uuid4(), raw_text="raw", extracted_json={})
    session = _FailingCommitSession(rows=[row, cv_row])
    service = _service()
    compiled = _FakeCompiledGraph(_pending_snapshot())
    _patch_graph(monkeypatch, compiled)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(ReviewPersistenceFailedError):
            await service.submit_review(match_id, ReviewDecision.approved, None, session)  # type: ignore[arg-type]

    assert len(compiled.ainvoke_calls) == 1  # the checkpoint resume did already happen
    assert any(
        record.levelno == logging.ERROR and str(match_id) in record.getMessage()
        for record in caplog.records
    )


# --- submit_review: full success path + was_selected derivation ---------


@pytest.mark.parametrize(
    ("decision", "note", "expected_was_selected"),
    [
        (ReviewDecision.approved, None, True),
        (ReviewDecision.rejected, None, False),
        (ReviewDecision.overridden_to_approve, "Overriding a false-negative hard filter.", True),
        (ReviewDecision.overridden_to_reject, "Overriding a false-positive pass.", False),
    ],
)
async def test_submit_review_writes_a_historical_decision_with_was_selected_derived_from_the_decision(
    decision: ReviewDecision, note: str | None, expected_was_selected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    match_id, cv_id, candidate_id, tdr_id = uuid4(), uuid4(), uuid4(), uuid4()
    row = _match_row(match_id, cv_id, tdr_id=tdr_id)
    cv_row = CVModel(cv_id=cv_id, candidate_id=candidate_id, raw_text="raw", extracted_json={})
    session = _FakeSession(rows=[row, *_report_context_rows(row, cv_row=cv_row)])
    service = _service()
    _patch_graph(monkeypatch, _FakeCompiledGraph(_pending_snapshot()))

    await service.submit_review(match_id, decision, note, session)  # type: ignore[arg-type]

    historical_rows = [obj for obj in session.added if isinstance(obj, HistoricalDecisionModel)]
    assert len(historical_rows) == 1
    assert historical_rows[0].was_selected is expected_was_selected
    assert historical_rows[0].tdr_id == tdr_id
    assert historical_rows[0].candidate_id == candidate_id
    assert historical_rows[0].outcome_note == note
    assert session.committed is True


async def test_submit_review_updates_the_match_row_and_resumes_the_paused_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    match_id, cv_id = uuid4(), uuid4()
    row = _match_row(match_id, cv_id)
    cv_row = CVModel(cv_id=cv_id, candidate_id=uuid4(), raw_text="raw", extracted_json={})
    session = _FakeSession(rows=[row, *_report_context_rows(row, cv_row=cv_row)])
    service = _service()
    compiled = _FakeCompiledGraph(_pending_snapshot())
    _patch_graph(monkeypatch, compiled)

    note = "Strong sector fit despite hard-filter fail."
    result = await service.submit_review(match_id, ReviewDecision.overridden_to_approve, note, session)  # type: ignore[arg-type]

    assert row.reviewer_decision == "overridden_to_approve"
    assert row.reviewer_id == "anonymous"
    assert row.reviewer_note == "Strong sector fit despite hard-filter fail."
    assert row.decided_at is not None
    assert len(compiled.ainvoke_calls) == 1
    command, _config = compiled.ainvoke_calls[0]
    assert command.resume == {
        "decision": "overridden_to_approve",
        "note": "Strong sector fit despite hard-filter fail.",
    }
    # submit_review returns via get_match, so the response reflects the update too.
    assert result.reviewer_decision == "overridden_to_approve"
