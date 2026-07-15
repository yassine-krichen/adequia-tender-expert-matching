from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.embeddings import Embeddings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SkillTaxonomy
from app.domain.cv import CandidateCV, NormalizedSkill
from app.domain.tdr import ExpertPosition
from app.features.pipeline.state import PipelineState

# Cosine similarity threshold to accept a taxonomy match without a retry.
_CONFIDENCE_THRESHOLD = 0.75
_TAXONOMY_TOP_K = 5
# Added to cosine similarity when the term is a literal (case-insensitive)
# match of the taxonomy row's canonical_name or one of its aliases --
# embedding similarity alone sometimes ranks a looser semantic neighbor
# above an exact alias match.
_EXACT_MATCH_BONUS = 0.15

# ADQ-14 agentic retry: rewrite a low-confidence term (abbreviation
# expansion / FR<->EN) and retry retrieval once, rather than calling an
# LLM -- keeps normalize_skills fully LLM-free this sprint (LLM judgment
# is deferred to Sprint 3). "pilotage de projet"/"conduite de projet" is
# the exact example from docs/01-architecture.md.
_REWRITE_MAP: dict[str, str] = {
    "gp": "gestion de projet",
    "pm": "gestion de projet",
    "pilotage de projet": "gestion de projet",
    "conduite de projet": "gestion de projet",
    "dev": "génie logiciel",
    "développement logiciel": "génie logiciel",
    "ia": "intelligence artificielle",
    "ai": "intelligence artificielle",
    "ml": "machine learning",
    "bi": "business intelligence",
    "informatique décisionnelle": "business intelligence",
    "qa": "assurance qualité",
    "cybersec": "cybersécurité",
    "sécurité informatique": "cybersécurité",
    "k8s": "kubernetes",
    "j2ee": "java",
    "si": "systèmes d'information",
    "réseau": "réseaux informatiques",
}


def _rerank_taxonomy_candidates(
    term: str, candidates: list[tuple[SkillTaxonomy, float]]
) -> list[tuple[SkillTaxonomy, float]]:
    normalized_term = term.strip().lower()

    def _score(entry: tuple[SkillTaxonomy, float]) -> float:
        taxonomy_row, similarity = entry
        names = [taxonomy_row.canonical_name, *(taxonomy_row.aliases or [])]
        exact_bonus = _EXACT_MATCH_BONUS if normalized_term in (n.lower() for n in names) else 0.0
        return similarity + exact_bonus

    return sorted(candidates, key=_score, reverse=True)


def _rewrite_query(term: str) -> str | None:
    return _REWRITE_MAP.get(term.strip().lower())


async def _retrieve_top_k_taxonomy(
    term: str, *, session: AsyncSession, embeddings: Embeddings, k: int = _TAXONOMY_TOP_K
) -> list[tuple[SkillTaxonomy, float]]:
    query_vector = embeddings.embed_query(term)
    stmt = (
        select(SkillTaxonomy, SkillTaxonomy.embedding.cosine_distance(query_vector).label("distance"))
        .order_by("distance")
        .limit(k)
    )
    rows = (await session.execute(stmt)).all()
    return [(row[0], 1.0 - row[1]) for row in rows]


async def match_skill_to_taxonomy(
    term: str, *, session: AsyncSession, embeddings: Embeddings
) -> NormalizedSkill:
    """ADQ-12 (embedding retrieval) + ADQ-13 (rerank) + ADQ-14 (retry on
    low confidence). No llm_fallback tier this sprint -- that path is
    deferred along with the rest of score's LLM judgment step.
    """
    candidates = await _retrieve_top_k_taxonomy(term, session=session, embeddings=embeddings)
    if not candidates:
        return NormalizedSkill(raw_term=term, canonical_id=None, confidence=0.0, matched_via="direct")

    ranked = _rerank_taxonomy_candidates(term, candidates)
    best_row, best_similarity = ranked[0]

    if best_similarity >= _CONFIDENCE_THRESHOLD:
        return NormalizedSkill(
            raw_term=term,
            canonical_id=str(best_row.skill_id),
            confidence=best_similarity,
            matched_via="direct",
        )

    rewritten = _rewrite_query(term)
    if rewritten is not None:
        retry_candidates = await _retrieve_top_k_taxonomy(rewritten, session=session, embeddings=embeddings)
        if retry_candidates:
            retry_row, retry_similarity = _rerank_taxonomy_candidates(rewritten, retry_candidates)[0]
            if retry_similarity > best_similarity:
                matched = retry_similarity >= _CONFIDENCE_THRESHOLD
                return NormalizedSkill(
                    raw_term=term,
                    canonical_id=str(retry_row.skill_id) if matched else None,
                    confidence=retry_similarity,
                    matched_via="rag_retry",
                )

    # Unresolved even after retry -- leave canonical_id unset, keep the
    # best-effort confidence for visibility. Label reflects whether a
    # retry was actually attempted, so a debugger doesn't read "direct"
    # and assume no rewrite was tried.
    return NormalizedSkill(
        raw_term=term,
        canonical_id=None,
        confidence=best_similarity,
        matched_via="rag_retry" if rewritten is not None else "direct",
    )


async def normalize_cv_skills(
    cv: CandidateCV, *, session: AsyncSession, embeddings: Embeddings
) -> list[NormalizedSkill]:
    """Normalizes a CV's raw_skills against the taxonomy for one matching
    run (not persisted back onto the CV row).
    """
    return [
        await match_skill_to_taxonomy(term, session=session, embeddings=embeddings)
        for term in cv.raw_skills
    ]


async def normalize_position_skills(
    position: ExpertPosition, *, session: AsyncSession, embeddings: Embeddings
) -> list[NormalizedSkill]:
    """Normalizes a TDR position's required_skills against the taxonomy.

    Computed once per position by the matching worker (not once per
    candidate) -- the result is candidate-independent, so score.py's
    skill_score reuses this same list across every candidate in a
    position's shortlist instead of re-querying the taxonomy per
    candidate. ExpertPosition has no normalized_skills field in the
    schema, so this is transient, not persisted.
    """
    return [
        await match_skill_to_taxonomy(term, session=session, embeddings=embeddings)
        for term in position.required_skills
    ]


def make_normalize_skills_node(
    *, session: AsyncSession, embeddings: Embeddings
) -> Callable[[PipelineState], Awaitable[dict[str, Any]]]:
    """ADQ-19 node factory -- also what makes the graph's entry node real
    (the graph starts here now, not at ingest/extract). Thin wrapper: all
    the actual retrieval/rerank/retry logic stays in normalize_cv_skills
    above, untouched.
    """

    async def _normalize_skills_node(state: PipelineState) -> dict[str, Any]:
        cv = state["cv_extracted"]
        assert cv is not None
        result = await normalize_cv_skills(cv, session=session, embeddings=embeddings)
        return {"normalized_skills": result}

    return _normalize_skills_node
