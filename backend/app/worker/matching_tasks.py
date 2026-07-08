import asyncio
import logging
from collections.abc import Callable
from uuid import UUID

from langchain_core.embeddings import Embeddings
from redis import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.models import TDR as TDRModel
from app.database.models import ExpertPosition as ExpertPositionModel
from app.database.models import MatchResult as MatchResultModel
from app.database.session import async_session_factory
from app.domain.cv import CandidateCV
from app.domain.tdr import ExpertPosition
from app.features.matching.coarse_retrieval import shortlist_candidates
from app.features.pipeline.nodes.normalize_skills import normalize_cv_skills, normalize_position_skills
from app.features.pipeline.nodes.score import check_hard_filters, score_soft_criteria

logger = logging.getLogger(__name__)

# Only needed for the lifetime of one matching run -- same TTL rationale as
# app/worker/tasks.py's extraction progress key.
_PROGRESS_TTL_SECONDS = 3600

MatchingProgressCallback = Callable[[str, int, int], None]


def matching_progress_key(tdr_id: str) -> str:
    return f"tdr:{tdr_id}:matching_progress"


def make_redis_matching_progress_reporter(
    redis_client: Redis, tdr_id: str
) -> MatchingProgressCallback:
    def report(status: str, positions_done: int, positions_total: int) -> None:
        redis_client.hset(
            matching_progress_key(tdr_id),
            mapping={"status": status, "positions_done": positions_done, "positions_total": positions_total},
        )
        redis_client.expire(matching_progress_key(tdr_id), _PROGRESS_TTL_SECONDS)

    return report


async def run_matching_job(
    tdr_id: str,
    *,
    session: AsyncSession,
    embeddings: Embeddings,
    on_progress: MatchingProgressCallback,
) -> None:
    """Runs coarse retrieval -> normalize_skills -> score for every
    position on this TDR, against the full CV pool. The TDR row and its
    positions already exist (extraction already ran) -- this only ever
    inserts/replaces match_results rows, never touches the TDR itself.

    Re-run safe: existing match_results for a position are deleted before
    that position's fresh matches are inserted (no unique constraint to
    upsert against, same delete-then-insert idempotency as the taxonomy
    seed script).
    """
    tdr_row = await session.get(TDRModel, UUID(tdr_id))
    assert tdr_row is not None, f"TDR {tdr_id} must exist before matching is enqueued"

    positions = (
        (
            await session.execute(
                select(ExpertPositionModel).where(ExpertPositionModel.tdr_id == UUID(tdr_id))
            )
        )
        .scalars()
        .all()
    )

    try:
        on_progress("processing", 0, len(positions))
        for index, position_row in enumerate(positions):
            position = ExpertPosition.model_validate(position_row.requirements_json)
            shortlist = await shortlist_candidates(position, session=session, embeddings=embeddings)

            # Position-scoped, not candidate-scoped -- computed once here
            # and reused for every candidate below, instead of
            # re-querying the taxonomy / re-embedding the same position
            # text once per candidate (see score.py's _skill_score/
            # _sector_score docstrings).
            normalized_position_skills = await normalize_position_skills(
                position, session=session, embeddings=embeddings
            )
            required_sector_vector = (
                embeddings.embed_query(position.required_sector_experience)
                if position.required_sector_experience
                else None
            )

            await session.execute(
                delete(MatchResultModel).where(
                    MatchResultModel.position_id == position_row.position_id
                )
            )
            for cv_row in shortlist:
                cv = CandidateCV.model_validate(cv_row.extracted_json)
                normalized = await normalize_cv_skills(cv, session=session, embeddings=embeddings)
                hard_filter_passed, failures = check_hard_filters(cv, position)

                # Computed regardless of hard_filter_passed -- a candidate
                # who fails on e.g. years but has strong skill/sector fit
                # should still show that fit, not just a bare failure
                # string. compatibility_score (the ranking number) stays
                # gated below: a hard-filter failure is never ranked, only
                # visible.
                sub_scores, soft_compatibility_score = score_soft_criteria(
                    cv,
                    normalized,
                    normalized_position_skills,
                    required_sector_vector,
                    embeddings=embeddings,
                )
                sub_scores_json = sub_scores.model_dump(mode="json")
                compatibility_score = soft_compatibility_score if hard_filter_passed else None

                session.add(
                    MatchResultModel(
                        cv_id=cv_row.cv_id,
                        tdr_id=UUID(tdr_id),
                        position_id=position_row.position_id,
                        hard_filter_passed=hard_filter_passed,
                        hard_filter_failures_json=failures,
                        compatibility_score=compatibility_score,
                        sub_scores_json=sub_scores_json,
                    )
                )
            await session.commit()
            on_progress("processing", index + 1, len(positions))
    except Exception as exc:
        await session.rollback()
        on_progress("failed", 0, len(positions))
        logger.warning("matching.job_failed tdr_id=%s error=%s", tdr_id, type(exc).__name__)
        return

    on_progress("done", len(positions), len(positions))


async def _run(tdr_id: str) -> None:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    router = ModelRouter(settings)
    on_progress = make_redis_matching_progress_reporter(redis_client, tdr_id)

    async with async_session_factory() as session:
        await run_matching_job(
            tdr_id, session=session, embeddings=router.get_embedding_model(), on_progress=on_progress
        )


def run_matching(tdr_id: str) -> None:
    """RQ entry point. See app/worker/tasks.py's run_tdr_extraction for why
    this wraps in asyncio.run.
    """
    asyncio.run(_run(tdr_id))
