from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.models import SkillTaxonomy, SkillTaxonomyCandidate
from app.features.taxonomy_admin.schemas import SkillCandidateSummary

_DEFAULT_STATUS = "pending"


class TaxonomyAdminService:
    """Human-review workflow for skill_taxonomy_candidates -- terms
    normalize_skills.py's match_skill_to_taxonomy left genuinely unmatched
    (canonical_id is None), harvested by
    record_unmatched_skill_candidates.

    No auth on this router, consistent with the rest of this app's
    explicit no-auth-in-scope design -- internal admin surface only.
    """

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router or ModelRouter(get_settings())

    async def list_candidates(
        self, session: AsyncSession, *, status: str = _DEFAULT_STATUS
    ) -> list[SkillCandidateSummary]:
        stmt = (
            select(SkillTaxonomyCandidate)
            .where(SkillTaxonomyCandidate.status == status)
            .order_by(SkillTaxonomyCandidate.occurrence_count.desc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [
            SkillCandidateSummary(
                candidate_id=str(row.candidate_id),
                raw_term=row.raw_term,
                occurrence_count=row.occurrence_count,
                best_similarity=row.best_similarity,
                suggested_canonical_name=row.suggested_canonical_name,
                suggested_aliases=row.suggested_aliases or [],
                first_seen_at=row.first_seen_at,
            )
            for row in rows
        ]

    async def approve(
        self,
        candidate_id: UUID,
        canonical_name: str,
        aliases: list[str],
        session: AsyncSession,
    ) -> None:
        """Directly creates the real SkillTaxonomy row -- the human
        reviewer's exact decision (canonical_name/aliases from the request
        body) is embedded via the real Ollama-only path (Class A
        persisted-vector write, same as seed_skill_taxonomy.py's bootstrap
        script -- no fallback, see ModelRouter.get_embedding_model).

        This is simpler than round-tripping through the seed JSON file:
        the admin API already has a live session and the human's exact
        decision, so the DB and the bootstrap JSON file are allowed to
        diverge over time -- the JSON file remains the bootstrap source
        for the original seed entries only (see seed_skill_taxonomy.py).
        """
        candidate = await session.get(SkillTaxonomyCandidate, candidate_id)
        if candidate is None:
            raise NotFoundError(f"No skill candidate found for id {candidate_id}")

        embedding = self._router.get_embedding_model().embed_query(canonical_name)
        session.add(
            SkillTaxonomy(canonical_name=canonical_name, aliases=aliases, embedding=embedding)
        )

        candidate.status = "merged"
        candidate.reviewed_at = datetime.now(UTC)
        await session.commit()

    async def reject(self, candidate_id: UUID, note: str | None, session: AsyncSession) -> None:
        candidate = await session.get(SkillTaxonomyCandidate, candidate_id)
        if candidate is None:
            raise NotFoundError(f"No skill candidate found for id {candidate_id}")

        candidate.status = "rejected"
        candidate.reviewed_at = datetime.now(UTC)
        candidate.reviewer_note = note
        await session.commit()
