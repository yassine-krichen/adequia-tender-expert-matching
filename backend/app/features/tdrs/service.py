import asyncio
import logging
from typing import Any, Protocol
from uuid import UUID, uuid4

from fastapi import UploadFile
from redis import Redis
from rq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError, ResourceNotReadyError
from app.config.settings import get_settings
from app.database.models import TDR as TDRModel
from app.domain.tdr import TDR
from app.features.tdrs.schemas import MatchingStatus, TdrStatus, TdrUploadAck
from app.worker import matching_tasks
from app.worker.tasks import run_tdr_extraction

logger = logging.getLogger(__name__)


def _decode(value: bytes | str) -> str:
    """redis-py's stubs report hash values as bytes | str depending on
    decode_responses — normalize regardless of which one a given client is
    configured with."""
    return value.decode() if isinstance(value, bytes) else value


class JobQueue(Protocol):
    """What TdrsService needs from RQ's Queue — lets tests substitute a fake
    that records enqueued jobs instead of needing a real Redis connection.
    """

    def enqueue(self, func: Any, /, *args: Any, job_timeout: int) -> Any: ...


# RQ's own default job_timeout is 180s -- observed live to kill a real
# multi-section TDR extraction mid-run (JobTimeoutException) on a day when
# both the Groq and Gemini pools were degraded/quota-exhausted and every
# one of the 12 chunks had to retry through both pools before falling back
# to Ollama. The pipeline itself can legitimately take several minutes in
# that situation -- the job timeout should not be the thing that decides
# whether an otherwise-successful extraction finishes.
_JOB_TIMEOUT_SECONDS = 600
# Matching runs one shortlist (~10 candidates) through embedding-only
# retrieval/scoring per position -- cheaper than a full TDR extraction, but
# uses the same generous ceiling for the same reason: it shouldn't be the
# thing that decides whether an otherwise-successful run finishes.
_MATCHING_JOB_TIMEOUT_SECONDS = 600


class TdrsService:
    """Owns TDR ingestion, section-localized extraction, and triggering matching runs.

    Extraction itself runs on the RQ worker (app/worker/tasks.py), not the
    request thread — a real multi-section TDR can take over a minute
    end-to-end, too slow to hold an HTTP request open for. upload_tdr only
    creates the placeholder row and enqueues the job; poll
    GET /tdrs/{tdr_id}/status for progress.
    """

    def __init__(self, queue: JobQueue | None = None, redis_client: Redis | None = None) -> None:
        settings = get_settings()
        self._queue = queue or Queue("default", connection=Redis.from_url(settings.redis_url))
        self._redis = redis_client or Redis.from_url(settings.redis_url)

    async def upload_tdr(self, file: UploadFile, session: AsyncSession) -> TdrUploadAck:
        file_bytes = await file.read()
        filename = file.filename or "upload"
        tdr_id = uuid4()

        tdr_row = TDRModel(tdr_id=tdr_id, source_file_path=filename, status="processing")
        session.add(tdr_row)
        await session.commit()

        try:
            self._queue.enqueue(
                run_tdr_extraction,
                str(tdr_id),
                file_bytes,
                filename,
                job_timeout=_JOB_TIMEOUT_SECONDS,
            )
        except Exception:
            # Row already exists at status="processing" -- if scheduling
            # itself fails (e.g. Redis unreachable), no job will ever run
            # against it. Mark it failed instead of leaving it orphaned
            # forever with nothing for the frontend poll to key off.
            tdr_row.status = "failed"
            tdr_row.error_message = "Failed to schedule extraction"
            await session.commit()
            logger.warning("tdr.enqueue_failed tdr_id=%s", tdr_id)
            raise

        return TdrUploadAck(tdr_id=str(tdr_id), status="processing")

    async def get_status(self, tdr_id: UUID, session: AsyncSession) -> TdrStatus:
        row = await session.get(TDRModel, tdr_id)
        if row is None:
            raise NotFoundError(f"No TDR with id {tdr_id}")

        if row.status != "processing":
            return TdrStatus(tdr_id=str(tdr_id), status=row.status, error_message=row.error_message)

        # self._redis is a sync client (shared with self._queue, which RQ
        # requires to be sync) -- hgetall would otherwise block the event
        # loop inside this async def.
        progress = await asyncio.to_thread(self._redis.hgetall, f"tdr:{tdr_id}:progress")
        if not progress:
            return TdrStatus(tdr_id=str(tdr_id), status="processing")
        return TdrStatus(
            tdr_id=str(tdr_id),
            status="processing",
            step=_decode(progress.get(b"step", b"")),
            chunks_done=int(_decode(progress.get(b"chunks_done", b"0"))),
            chunks_total=int(_decode(progress.get(b"chunks_total", b"0"))),
        )

    async def get_tdr(self, tdr_id: UUID, session: AsyncSession) -> TDR:
        row = await session.get(TDRModel, tdr_id)
        if row is None:
            raise NotFoundError(f"No TDR with id {tdr_id}")
        if row.status == "processing":
            raise ResourceNotReadyError(f"TDR {tdr_id} is still processing")
        if row.status == "failed":
            raise ResourceNotReadyError(row.error_message or f"TDR {tdr_id} extraction failed")

        assert row.extracted_json is not None  # guaranteed once status == "done"
        return TDR.model_validate(row.extracted_json)

    async def run_matching(self, tdr_id: UUID, session: AsyncSession) -> None:
        """Kicks off the matching pipeline for every position on this TDR.

        Coarse retrieval shortlists ~8-10 candidates per position before the
        full graph runs — see docs/01-architecture.md two-phase matching.
        Runs on the RQ worker (app/worker/matching_tasks.py), same reasoning
        as TDR extraction — poll GET /tdrs/{tdr_id}/match-status.
        """
        row = await session.get(TDRModel, tdr_id)
        if row is None:
            raise NotFoundError(f"No TDR with id {tdr_id}")
        if row.status != "done":
            raise ResourceNotReadyError(f"TDR {tdr_id} extraction hasn't finished yet")

        self._queue.enqueue(
            matching_tasks.run_matching, str(tdr_id), job_timeout=_MATCHING_JOB_TIMEOUT_SECONDS
        )

    async def get_matching_status(self, tdr_id: UUID, session: AsyncSession) -> MatchingStatus:
        row = await session.get(TDRModel, tdr_id)
        if row is None:
            raise NotFoundError(f"No TDR with id {tdr_id}")

        progress = await asyncio.to_thread(
            self._redis.hgetall, matching_tasks.matching_progress_key(str(tdr_id))
        )
        if not progress:
            return MatchingStatus(tdr_id=str(tdr_id), status="not_started")
        return MatchingStatus(
            tdr_id=str(tdr_id),
            status=_decode(progress.get(b"status", b"processing")),
            positions_done=int(_decode(progress.get(b"positions_done", b"0"))),
            positions_total=int(_decode(progress.get(b"positions_total", b"0"))),
        )
