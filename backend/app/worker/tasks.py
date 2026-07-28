import asyncio
import logging
from uuid import UUID

from langchain_core.embeddings import Embeddings
from redis import Redis
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import DomainError
from app.common.llm.router import ExtractionRouter, ModelRouter
from app.config.settings import get_settings
from app.database.models import TDR as TDRModel
from app.database.models import ExpertPosition as ExpertPositionModel
from app.database.models import MatchResult as MatchResultModel
from app.database.session import async_session_factory
from app.features.pipeline.nodes.extract import ProgressCallback, extract_tdr
from app.features.pipeline.nodes.ingest import extract_raw_text

logger = logging.getLogger(__name__)

# Only needed for the lifetime of one extraction job -- stale after that,
# so a short TTL rather than a permanent key.
_PROGRESS_TTL_SECONDS = 3600


def _progress_key(tdr_id: str) -> str:
    return f"tdr:{tdr_id}:progress"


def make_redis_progress_reporter(redis_client: Redis, tdr_id: str) -> ProgressCallback:
    def report(step: str, chunks_done: int, chunks_total: int) -> None:
        redis_client.hset(
            _progress_key(tdr_id),
            mapping={"step": step, "chunks_done": chunks_done, "chunks_total": chunks_total},
        )
        redis_client.expire(_progress_key(tdr_id), _PROGRESS_TTL_SECONDS)

    return report


async def run_tdr_extraction_job(
    tdr_id: str,
    file_bytes: bytes,
    filename: str,
    *,
    session: AsyncSession,
    router: ExtractionRouter,
    embeddings: Embeddings,
    on_progress: ProgressCallback,
) -> None:
    """The actual extraction + persistence, independent of how it's invoked
    (RQ worker in production, called directly with fakes in tests).

    The TDR row already exists (status="processing", created by
    TdrsService.upload_tdr before enqueueing) -- this only ever updates it,
    never inserts. embeddings is taken as its own parameter (not derived
    from router) since ExtractionRouter (the interface tests fake against)
    only covers LLM calls -- same split extract_tdr itself already makes.
    """
    tdr_row = await session.get(TDRModel, UUID(tdr_id))
    assert (
        tdr_row is not None
    ), f"TdrsService.upload_tdr must create tdr_id={tdr_id} before enqueueing"

    try:
        on_progress("parsing", 0, 0)
        raw_text = extract_raw_text(file_bytes, filename)
        tdr = extract_tdr(
            raw_text,
            tdr_id=tdr_id,
            source_file_path=filename,
            router=router,
            embeddings=embeddings,
            on_progress=on_progress,
            mask_pii=get_settings().pii_masking_enabled,
        )

        tdr_row.status = "done"
        tdr_row.mission_title = tdr.mission_title
        tdr_row.client = tdr.client
        tdr_row.sector = tdr.sector
        tdr_row.deadline = tdr.deadline
        tdr_row.raw_text = raw_text
        tdr_row.extracted_json = tdr.model_dump(mode="json")

        # Reprocessing (e.g. force-reprocess) must replace the position set,
        # not append to it -- otherwise stale positions from prior extraction
        # runs pile up forever. Match results reference expert_positions via
        # FK with no ON DELETE CASCADE, so they must be cleared first.
        await session.execute(
            delete(MatchResultModel).where(MatchResultModel.tdr_id == UUID(tdr_id))
        )
        await session.execute(
            delete(ExpertPositionModel).where(ExpertPositionModel.tdr_id == UUID(tdr_id))
        )
        for position in tdr.positions:
            session.add(
                ExpertPositionModel(
                    position_id=UUID(position.position_id),
                    tdr_id=UUID(tdr_id),
                    position_title=position.position_title,
                    requirements_json=position.model_dump(mode="json"),
                )
            )
        await session.commit()
    except Exception as exc:
        # Covers extraction failures *and* persistence failures (e.g. the
        # commit above) -- either way the row must not be left stuck at
        # status="processing" forever. rollback() first: a failed commit
        # leaves the session's pending state unusable for the follow-up
        # update below. DomainError.message is already safe to show a
        # client (typed, written for that purpose); anything else is an
        # unexpected internal failure, so keep the detail out of
        # error_message — matches the "never leak internals to consumers"
        # convention.
        await session.rollback()
        tdr_row.status = "failed"
        tdr_row.error_message = (
            exc.message if isinstance(exc, DomainError) else "TDR extraction failed"
        )
        await session.commit()
        logger.warning("tdr.extraction_failed tdr_id=%s error=%s", tdr_id, type(exc).__name__)


async def _run(tdr_id: str, file_bytes: bytes, filename: str) -> None:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    router = ModelRouter(settings)
    on_progress = make_redis_progress_reporter(redis_client, tdr_id)

    async with async_session_factory() as session:
        await run_tdr_extraction_job(
            tdr_id,
            file_bytes,
            filename,
            session=session,
            router=router,
            # extract_tdr's embeddings usage (chunk retrieval) is fully
            # transient -- query/chunk vectors are computed and compared
            # only within this one call, never persisted -- so it's safe to
            # use the fallback-capable embeddings here (Class C, see
            # ModelRouter.get_transient_embedding_model), unlike every other
            # embedding call site in this codebase.
            embeddings=router.get_transient_embedding_model(),
            on_progress=on_progress,
        )


def run_tdr_extraction(tdr_id: str, file_bytes: bytes, filename: str) -> None:
    """RQ entry point. Runs on the worker process, not the request thread.

    Wrapped in asyncio.run: RQ workers are plain sync processes, and the DB
    session (async_session_factory) needs an event loop. The LLM router
    calls themselves are sync (LangChain's .invoke), so nothing else here
    needs to be async.
    """
    asyncio.run(_run(tdr_id, file_bytes, filename))
