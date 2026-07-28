import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.common.exceptions import NotFoundError
from app.database.models import SkillTaxonomy, SkillTaxonomyCandidate
from app.features.taxonomy_admin.service import TaxonomyAdminService


class _FakeEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class _FakeRouter:
    def get_embedding_model(self) -> _FakeEmbeddings:
        return _FakeEmbeddings()


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """Fakes just enough of AsyncSession for TaxonomyAdminService --
    .get() for approve/reject's candidate_id lookup, .execute() for
    list_candidates' status-filtered/ordered select.

    Filtering is done by extracting the real compiled statement's bound
    `status` parameter (not hardcoded) -- a regression that filtered on
    the wrong column/value would show up as a KeyError here rather than
    silently passing. Ordering (occurrence_count desc) is replicated in
    Python, same "minimal surface, not a real predicate/order engine"
    convention as test_normalize_skills.py's _FakeSession.
    """

    def __init__(self, candidates: list[SkillTaxonomyCandidate] | None = None) -> None:
        self._candidates = {c.candidate_id: c for c in (candidates or [])}
        self.added: list[Any] = []
        self.committed = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def get(self, model_cls: type[Any], pk: Any) -> Any | None:
        if model_cls is SkillTaxonomyCandidate:
            return self._candidates.get(pk)
        return None

    async def execute(self, stmt: Any) -> _FakeResult:
        status = stmt.compile().params["status_1"]
        rows = [c for c in self._candidates.values() if c.status == status]
        rows.sort(key=lambda c: c.occurrence_count, reverse=True)
        return _FakeResult(rows)


def _candidate(
    raw_term: str, *, occurrence_count: int = 1, status: str = "pending"
) -> SkillTaxonomyCandidate:
    return SkillTaxonomyCandidate(
        candidate_id=uuid.uuid4(),
        raw_term=raw_term,
        normalized_term=raw_term.strip().lower(),
        occurrence_count=occurrence_count,
        best_similarity=0.5,
        status=status,
        first_seen_at=datetime.now(UTC),
    )


async def test_list_candidates_filters_to_the_requested_status() -> None:
    pending = _candidate("Terraform", status="pending")
    rejected = _candidate("Some Noise", status="rejected")
    session = _FakeSession([pending, rejected])
    service = TaxonomyAdminService(router=_FakeRouter())  # type: ignore[arg-type]

    result = await service.list_candidates(session, status="pending")  # type: ignore[arg-type]

    assert [r.raw_term for r in result] == ["Terraform"]


async def test_list_candidates_orders_by_occurrence_count_descending() -> None:
    low = _candidate("Rare Term", occurrence_count=1)
    high = _candidate("Common Term", occurrence_count=9)
    session = _FakeSession([low, high])
    service = TaxonomyAdminService(router=_FakeRouter())  # type: ignore[arg-type]

    result = await service.list_candidates(session, status="pending")  # type: ignore[arg-type]

    assert [r.raw_term for r in result] == ["Common Term", "Rare Term"]


async def test_approve_creates_a_real_skill_taxonomy_row_with_an_embedded_vector_and_marks_merged() -> (
    None
):
    candidate = _candidate("Terraform")
    session = _FakeSession([candidate])
    service = TaxonomyAdminService(router=_FakeRouter())  # type: ignore[arg-type]

    await service.approve(
        candidate.candidate_id, "Terraform (IaC)", ["Terraform", "IaC"], session  # type: ignore[arg-type]
    )

    taxonomy_rows = [row for row in session.added if isinstance(row, SkillTaxonomy)]
    assert len(taxonomy_rows) == 1
    assert taxonomy_rows[0].canonical_name == "Terraform (IaC)"
    assert taxonomy_rows[0].aliases == ["Terraform", "IaC"]
    assert taxonomy_rows[0].embedding == [1.0, 0.0]
    assert candidate.status == "merged"
    assert candidate.reviewed_at is not None
    assert session.committed is True


async def test_approve_raises_not_found_for_an_unknown_candidate_id() -> None:
    session = _FakeSession([])
    service = TaxonomyAdminService(router=_FakeRouter())  # type: ignore[arg-type]

    with pytest.raises(NotFoundError):
        await service.approve(uuid.uuid4(), "Some Name", [], session)  # type: ignore[arg-type]


async def test_reject_marks_rejected_and_creates_no_taxonomy_row() -> None:
    candidate = _candidate("Some Noise")
    session = _FakeSession([candidate])
    service = TaxonomyAdminService(router=_FakeRouter())  # type: ignore[arg-type]

    await service.reject(candidate.candidate_id, "not a real skill", session)  # type: ignore[arg-type]

    assert candidate.status == "rejected"
    assert candidate.reviewer_note == "not a real skill"
    assert candidate.reviewed_at is not None
    assert session.added == []
    assert session.committed is True


async def test_reject_raises_not_found_for_an_unknown_candidate_id() -> None:
    session = _FakeSession([])
    service = TaxonomyAdminService(router=_FakeRouter())  # type: ignore[arg-type]

    with pytest.raises(NotFoundError):
        await service.reject(uuid.uuid4(), None, session)  # type: ignore[arg-type]
