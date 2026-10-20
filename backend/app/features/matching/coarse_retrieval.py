from langchain_core.embeddings import Embeddings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CV as CVModel
from app.domain.cv import CandidateCV
from app.domain.tdr import ExpertPosition

# Zero LLM calls in this node -- pure embedding similarity + a small
# structured boost, per docs/03-agent-pipeline.md "Coarse retrieval".
_DEFAULT_K = 10
# Retrieve a wider pool by raw embedding distance before re-ranking with
# the structured boosts below, so a candidate that's a strong sector/years
# fit but a slightly weaker pure-skill-embedding match still has a chance
# to surface into the final top-K.
_CANDIDATE_POOL_MULTIPLIER = 3
_SECTOR_BOOST = 0.15
_YEARS_PROXIMITY_WEIGHT = 0.05
_YEARS_SHORTFALL_PENALTY = 0.15


def _build_position_query_text(position: ExpertPosition) -> str:
    parts = [position.position_title, *position.required_skills]
    if position.required_sector_experience:
        parts.append(position.required_sector_experience)
    return " ".join(parts)


def _sector_overlap_boost(cv: CandidateCV, position: ExpertPosition) -> float:
    if not position.required_sector_experience:
        return 0.0
    required = position.required_sector_experience.strip().lower()
    for experience in cv.experience:
        if not experience.sector:
            continue
        sector = experience.sector.strip().lower()
        if sector in required or required in sector:
            return _SECTOR_BOOST
    return 0.0


def _years_proximity_boost(cv: CandidateCV, position: ExpertPosition) -> float:
    """Rough proximity signal, not a hard cutoff -- ADQ-15's hard filter is
    what actually rejects under-experienced candidates. This just ranks
    comfortably-qualified candidates a bit above barely-qualified ones,
    without excluding anyone from the shortlist outright (a slightly
    under-experienced candidate might still be the best available option
    and should still reach the reviewer).
    """
    if position.minimum_years_experience is None:
        return 0.0
    surplus = cv.total_years_experience - position.minimum_years_experience
    if surplus < 0:
        return -_YEARS_SHORTFALL_PENALTY
    return min(surplus * _YEARS_PROXIMITY_WEIGHT, _SECTOR_BOOST)


def rerank_shortlist_pool(
    pool: list[tuple[CVModel, float]], position: ExpertPosition
) -> list[tuple[CVModel, float]]:
    """pool: (CV row, cosine similarity) pairs, already ordered by raw
    embedding distance. Adds the structured boosts and re-sorts.
    """

    def _score(entry: tuple[CVModel, float]) -> float:
        cv_row, similarity = entry
        cv = CandidateCV.model_validate(cv_row.extracted_json)
        return (
            similarity + _sector_overlap_boost(cv, position) + _years_proximity_boost(cv, position)
        )

    return sorted(pool, key=_score, reverse=True)


async def shortlist_candidates(
    position: ExpertPosition,
    *,
    session: AsyncSession,
    embeddings: Embeddings,
    k: int = _DEFAULT_K,
) -> list[CVModel]:
    """Coarse retrieval pre-filter (ADQ-11) -- shortlists ~k plausible
    candidates from the full CV pool for one TDR position, before the
    expensive per-candidate matching pipeline runs. See
    docs/01-architecture.md "Two-phase matching".
    """
    query_vector = embeddings.embed_query(_build_position_query_text(position))
    stmt = (
        select(CVModel, CVModel.embedding.cosine_distance(query_vector).label("distance"))
        .where(CVModel.embedding.is_not(None))
        .order_by("distance")
        .limit(k * _CANDIDATE_POOL_MULTIPLIER)
    )
    rows = (await session.execute(stmt)).all()
    pool = [(row[0], 1.0 - row[1]) for row in rows]
    ranked = rerank_shortlist_pool(pool, position)
    return [cv_row for cv_row, _ in ranked[:k]]
