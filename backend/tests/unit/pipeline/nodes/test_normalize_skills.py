from uuid import uuid4

from app.database.models import SkillTaxonomy
from app.features.pipeline.nodes.normalize_skills import (
    _rerank_taxonomy_candidates,
    _rewrite_query,
)


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
