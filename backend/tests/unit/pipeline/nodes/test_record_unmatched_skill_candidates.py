"""record_unmatched_skill_candidates (Item 5's harvest function).

Uses a fake AsyncSession that compiles the real ON CONFLICT DO UPDATE
statement (via the postgresql dialect) to extract its bound literal values,
then simulates the upsert against an in-memory dict keyed by
normalized_term -- proves the real upsert statement is built correctly
without needing a live Postgres connection (postgresql.insert(...)
.on_conflict_do_update(...) is Postgres-specific SQL that a SQLite fixture
can't compile).
"""

import copy
from types import TracebackType
from typing import Any, Self

from sqlalchemy.dialects import postgresql

from app.domain.cv import NormalizedSkill
from app.features.pipeline.nodes.normalize_skills import record_unmatched_skill_candidates

_PG_DIALECT = postgresql.dialect()  # type: ignore[no-untyped-call]


class _FakeNestedTransaction:
    """Simulates the SAVEPOINT semantics of AsyncSession.begin_nested(): on
    a clean exit, whatever changed inside the block stays; on an exception,
    only the changes made inside THIS block are reverted -- state that
    already existed on the session before entering is untouched, mirroring
    a real SAVEPOINT rolling back without touching the outer transaction.
    """

    def __init__(self, session: "_FakeUpsertSession") -> None:
        self._session = session
        self._rows_snapshot: dict[str, dict[str, Any]] | None = None

    async def __aenter__(self) -> Self:
        self._rows_snapshot = copy.deepcopy(self._session.rows)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc_type is not None:
            assert self._rows_snapshot is not None
            self._session.rows = self._rows_snapshot
        return False


class _FakeUpsertSession:
    """Simulates skill_taxonomy_candidates' real ON CONFLICT DO UPDATE
    behavior: an insert whose normalized_term already exists increments
    occurrence_count instead of creating a second row.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        # Stands in for OTHER candidates' already-flushed-but-not-committed
        # state on this same shared session (e.g. MatchResultModel/
        # AnomalyModel rows added earlier in run_matching_job's candidate
        # loop) -- must survive a failure inside this harvest call.
        self.other_pending_state: list[str] = []
        self.rolled_back = False
        self._fail = fail

    async def execute(self, stmt: Any) -> None:
        if self._fail:
            raise RuntimeError("simulated DB failure")
        params = stmt.compile(dialect=_PG_DIALECT).params
        normalized_term = params["normalized_term"]
        existing = self.rows.get(normalized_term)
        if existing is None:
            self.rows[normalized_term] = {
                "raw_term": params["raw_term"],
                "normalized_term": normalized_term,
                "occurrence_count": params["occurrence_count"],
                "best_similarity": params["best_similarity"],
            }
        else:
            existing["occurrence_count"] += 1
            existing["best_similarity"] = params["best_similarity"]

    def begin_nested(self) -> _FakeNestedTransaction:
        return _FakeNestedTransaction(self)

    async def rollback(self) -> None:
        self.rolled_back = True


def _skill(raw_term: str, canonical_id: str | None, confidence: float = 0.5) -> NormalizedSkill:
    return NormalizedSkill(
        raw_term=raw_term, canonical_id=canonical_id, confidence=confidence, matched_via="direct"
    )


async def test_only_unmatched_skills_are_upserted_matched_ones_are_ignored() -> None:
    session = _FakeUpsertSession()
    skills = [
        _skill("Python", canonical_id="skill-1"),  # matched -- must be ignored
        _skill("Some Obscure Tool", canonical_id=None),
    ]

    await record_unmatched_skill_candidates(skills, session=session)  # type: ignore[arg-type]

    assert set(session.rows) == {"some obscure tool"}


async def test_repeat_harvest_of_the_same_normalized_term_increments_occurrence_count_not_a_new_row() -> (
    None
):
    session = _FakeUpsertSession()
    first_call = [_skill("Kubernetes", canonical_id=None)]
    second_call = [_skill("kubernetes", canonical_id=None)]  # same term, different casing

    await record_unmatched_skill_candidates(first_call, session=session)  # type: ignore[arg-type]
    await record_unmatched_skill_candidates(second_call, session=session)  # type: ignore[arg-type]

    assert len(session.rows) == 1
    assert session.rows["kubernetes"]["occurrence_count"] == 2


async def test_harvest_never_raises_even_when_the_session_call_fails() -> None:
    session = _FakeUpsertSession(fail=True)
    skills = [_skill("Rust", canonical_id=None)]

    await record_unmatched_skill_candidates(skills, session=session)  # type: ignore[arg-type]

    # The harvest must never call rollback() on the shared outer session --
    # doing so would wipe out other candidates' pending state in the same
    # transaction (see the SAVEPOINT-isolation test below). Isolation is via
    # begin_nested(), not an outer rollback.
    assert session.rolled_back is False


async def test_harvest_failure_does_not_wipe_other_pending_state_on_the_shared_session() -> None:
    """Regression: record_unmatched_skill_candidates shares the SAME
    AsyncSession as the rest of run_matching_job's candidate loop, which
    only commits once per position -- after every candidate in that
    position's shortlist has run. A bare `except: await session.rollback()`
    here would roll back the entire outer transaction, silently wiping out
    OTHER candidates' already-flushed-but-not-yet-committed
    MatchResultModel/AnomalyModel rows too. The harvest's own upsert must be
    isolated in its own SAVEPOINT (session.begin_nested()) so a failure only
    undoes its own statement, never anything else on the shared session.
    """
    session = _FakeUpsertSession(fail=True)
    # Simulates another candidate's already-flushed match result sitting on
    # the same shared session before this harvest call runs.
    session.other_pending_state.append("match-result-for-candidate-1")
    skills = [_skill("Rust", canonical_id=None)]

    await record_unmatched_skill_candidates(skills, session=session)  # type: ignore[arg-type]

    assert session.other_pending_state == ["match-result-for-candidate-1"]
    assert session.rolled_back is False


async def test_harvest_is_a_no_op_when_every_skill_is_already_matched() -> None:
    session = _FakeUpsertSession()
    skills = [_skill("Python", canonical_id="skill-1")]

    await record_unmatched_skill_candidates(skills, session=session)  # type: ignore[arg-type]

    assert session.rows == {}
