from typing import Any
from uuid import uuid4

from app.database.models import SkillTaxonomy
from app.domain.cv import CandidateCV
from app.features.pipeline.nodes.normalize_skills import (
    _rerank_taxonomy_candidates,
    _rewrite_query,
    make_normalize_skills_node,
)
from app.features.pipeline.state import PipelineState


def _taxonomy_row(canonical_name: str, aliases: list[str] | None = None) -> SkillTaxonomy:
    return SkillTaxonomy(skill_id=uuid4(), canonical_name=canonical_name, aliases=aliases or [])


def test_rerank_prefers_exact_canonical_name_match_over_higher_raw_similarity() -> None:
    exact = _taxonomy_row("Gestion de projet")
    looser = _taxonomy_row("Gestion des risques")

    ranked = _rerank_taxonomy_candidates(
        "gestion de projet", [(looser, 0.72), (exact, 0.70)]
    )

    assert ranked[0][0] is exact


def test_rerank_prefers_exact_alias_match() -> None:
    exact_alias = _taxonomy_row("Business Intelligence", aliases=["BI", "Décisionnel"])
    looser = _taxonomy_row("Analyse de données")

    ranked = _rerank_taxonomy_candidates("bi", [(looser, 0.71), (exact_alias, 0.68)])

    assert ranked[0][0] is exact_alias


def test_rerank_is_case_insensitive() -> None:
    exact = _taxonomy_row("Scrum Master", aliases=["CSM"])
    other = _taxonomy_row("Scrum")

    ranked = _rerank_taxonomy_candidates("CSM", [(other, 0.7), (exact, 0.65)])

    assert ranked[0][0] is exact


def test_rewrite_query_expands_known_abbreviation() -> None:
    assert _rewrite_query("GP") == "gestion de projet"


def test_rewrite_query_handles_the_pilotage_vs_gestion_example() -> None:
    # The exact FR synonym mismatch cited in docs/01-architecture.md.
    assert _rewrite_query("Pilotage de projet") == "gestion de projet"


def test_rewrite_query_returns_none_for_unknown_term() -> None:
    assert _rewrite_query("some completely unrelated term") is None


class _FakeEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0] if text.strip().lower() == "python" else [0.0, 1.0]


class _FakeExecuteResult:
    def __init__(self, rows: list[tuple[SkillTaxonomy, float]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[SkillTaxonomy, float]]:
        return self._rows


class _FakeSession:
    """Fakes just enough of AsyncSession.execute for
    _retrieve_top_k_taxonomy's `(await session.execute(stmt)).all()` -- the
    same convention as test_score.py's fake embeddings, minimal surface only.
    """

    def __init__(self, rows: list[tuple[SkillTaxonomy, float]]) -> None:
        self._rows = rows

    async def execute(self, stmt: Any) -> _FakeExecuteResult:
        return _FakeExecuteResult(self._rows)


def _cv(raw_skills: list[str]) -> CandidateCV:
    return CandidateCV(
        candidate_id="c1",
        full_name="Test Candidate",
        education=[],
        certifications=[],
        experience=[],
        languages=[],
        raw_skills=raw_skills,
        total_years_experience=1.0,
        raw_text="raw",
        source_file_path="cv.pdf",
    )


def _state(cv: CandidateCV) -> PipelineState:
    return {
        "cv_raw_text": "raw cv",
        "tdr_raw_text": "raw tdr",
        "position": None,  # type: ignore[typeddict-item]
        "cv_extracted": cv,
        "normalized_skills": None,
        "normalized_position_skills": [],
        "required_sector_vector": None,
        "sector": None,
        "hard_filter_passed": None,
        "hard_filter_failures": [],
        "sub_scores": None,
        "compatibility_score": None,
        "qualitative_fit_reasoning": None,
        "sector_match_source_span": None,
        "anomalies": [],
        "rationale": None,
        "citations": [],
        "needs_human_review": False,
    }


async def test_make_normalize_skills_node_delegates_to_normalize_cv_skills_and_returns_the_result() -> None:
    """No mock of normalize_cv_skills itself -- runs the real
    retrieval/rerank logic against a fake session/embeddings, so this both
    proves the node wires cv_extracted.raw_skills through correctly and
    exercises normalize_cv_skills end-to-end (previously untested anywhere).
    """
    python_row = _taxonomy_row("Python")
    session = _FakeSession(rows=[(python_row, 0.0)])  # distance=0.0 -> similarity=1.0
    node = make_normalize_skills_node(session=session, embeddings=_FakeEmbeddings())  # type: ignore[arg-type]
    state = _state(_cv(raw_skills=["Python"]))

    result = await node(state)

    assert set(result.keys()) == {"normalized_skills"}
    normalized_skills = result["normalized_skills"]
    assert len(normalized_skills) == 1
    assert normalized_skills[0].raw_term == "Python"
    assert normalized_skills[0].canonical_id == str(python_row.skill_id)
    assert normalized_skills[0].matched_via == "direct"
