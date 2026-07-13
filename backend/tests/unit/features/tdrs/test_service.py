import hashlib
from io import BytesIO
from typing import Any
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.common.exceptions import NotFoundError, ResourceNotReadyError
from app.database.models import TDR as TDRModel
from app.features.tdrs.service import TdrsService


class _FakeQueue:
    def __init__(self, calls: list[str] | None = None) -> None:
        self.enqueued: list[tuple[Any, tuple[Any, ...], int]] = []
        self._calls = calls  # shared ordering log with _FakeRedis, when provided

    def enqueue(self, func: Any, *args: Any, job_timeout: int) -> None:
        self.enqueued.append((func, args, job_timeout))
        if self._calls is not None:
            self._calls.append("enqueue")


class _FakeRedis:
    def __init__(
        self,
        progress: dict[str, dict[bytes, bytes]] | None = None,
        calls: list[str] | None = None,
    ) -> None:
        self._progress = progress or {}
        self.expired: list[tuple[str, int]] = []
        self._calls = calls  # shared ordering log with _FakeQueue, when provided

    def hgetall(self, key: str) -> dict[bytes, bytes]:
        return self._progress.get(key, {})

    def hset(self, key: str, mapping: dict[str, Any]) -> None:
        """Mirrors make_redis_matching_progress_reporter's real redis-py
        call -- stores string/int values as the bytes hgetall would hand
        back, so a test can read its own write straight through hgetall."""
        encoded = {
            (field.encode() if isinstance(field, str) else field): (
                value if isinstance(value, bytes) else str(value).encode()
            )
            for field, value in mapping.items()
        }
        self._progress.setdefault(key, {}).update(encoded)
        if self._calls is not None:
            self._calls.append("hset")

    def expire(self, key: str, seconds: int) -> None:
        self.expired.append((key, seconds))


class _FakeResult:
    def __init__(self, row: Any | None) -> None:
        self._row = row

    def scalar_one_or_none(self) -> Any | None:
        return self._row


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def get(self, model_cls: type[Any], pk: Any) -> Any | None:
        for obj in self.added:
            if isinstance(obj, model_cls) and getattr(obj, "tdr_id", None) == pk:
                return obj
        return None

    async def execute(self, _stmt: Any) -> _FakeResult:
        """Fakes upload_tdr's `select(TDRModel).where(content_hash == ...)`
        -- returns the first TDRModel row already present (pre-seeded via
        session.added), same as a real dedup hit.
        """
        existing_tdr = next((row for row in self.added if isinstance(row, TDRModel)), None)
        return _FakeResult(existing_tdr)


async def test_upload_tdr_creates_a_processing_row_and_enqueues_the_extraction_job() -> None:
    queue = _FakeQueue()
    service = TdrsService(queue=queue, redis_client=_FakeRedis())  # type: ignore[arg-type]
    session = _FakeSession()
    upload = UploadFile(file=BytesIO(b"raw tdr bytes"), filename="tdr.pdf")

    ack = await service.upload_tdr(upload, session)  # type: ignore[arg-type]

    assert ack.status == "processing"
    assert session.committed is True
    tdr_rows = [row for row in session.added if isinstance(row, TDRModel)]
    assert len(tdr_rows) == 1
    assert tdr_rows[0].status == "processing"
    assert str(tdr_rows[0].tdr_id) == ack.tdr_id

    assert len(queue.enqueued) == 1
    func, args, job_timeout = queue.enqueued[0]
    assert func.__name__ == "run_tdr_extraction"
    assert args == (ack.tdr_id, b"raw tdr bytes", "tdr.pdf")
    assert job_timeout >= 300  # generous enough that a degraded LLM day doesn't get killed mid-run


async def test_upload_tdr_returns_existing_tdr_on_duplicate_file_without_re_enqueueing() -> None:
    file_bytes = b"raw tdr bytes"
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    existing_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=existing_id, content_hash=content_hash, status="done"))
    queue = _FakeQueue()
    service = TdrsService(queue=queue, redis_client=_FakeRedis())  # type: ignore[arg-type]
    upload = UploadFile(file=BytesIO(file_bytes), filename="tdr-again.pdf")

    ack = await service.upload_tdr(upload, session)  # type: ignore[arg-type]

    assert ack.tdr_id == str(existing_id)
    assert ack.status == "done"
    assert len(queue.enqueued) == 0  # no re-extraction enqueued
    assert len([row for row in session.added if isinstance(row, TDRModel)]) == 1  # no new row


async def test_upload_tdr_with_force_re_enqueues_against_the_same_row() -> None:
    """force=True is the escape hatch for a known-bad stored extraction
    (e.g. a prompt/pipeline bug fixed after the file was first uploaded)
    -- it must reset the existing row to processing and re-enqueue, not
    create a second row (content_hash is unique-indexed).
    """
    file_bytes = b"raw tdr bytes"
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    existing_id = uuid4()
    session = _FakeSession()
    session.added.append(
        TDRModel(
            tdr_id=existing_id,
            content_hash=content_hash,
            status="done",
            extracted_json={"stale": True},
        )
    )
    queue = _FakeQueue()
    service = TdrsService(queue=queue, redis_client=_FakeRedis())  # type: ignore[arg-type]
    upload = UploadFile(file=BytesIO(file_bytes), filename="tdr-again.pdf")

    ack = await service.upload_tdr(upload, session, force=True)  # type: ignore[arg-type]

    assert ack.tdr_id == str(existing_id)
    assert ack.status == "processing"
    tdr_rows = [row for row in session.added if isinstance(row, TDRModel)]
    assert len(tdr_rows) == 1  # no new row
    assert tdr_rows[0].status == "processing"
    assert tdr_rows[0].extracted_json is None

    assert len(queue.enqueued) == 1
    func, args, _ = queue.enqueued[0]
    assert func.__name__ == "run_tdr_extraction"
    assert args == (str(existing_id), file_bytes, "tdr-again.pdf")


async def test_get_status_reports_processing_with_redis_progress() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="processing"))
    redis = _FakeRedis(
        {f"tdr:{tdr_id}:progress": {b"step": b"extracting", b"chunks_done": b"3", b"chunks_total": b"12"}}
    )
    service = TdrsService(queue=_FakeQueue(), redis_client=redis)  # type: ignore[arg-type]

    status = await service.get_status(tdr_id, session)  # type: ignore[arg-type]

    assert status.status == "processing"
    assert status.step == "extracting"
    assert status.chunks_done == 3
    assert status.chunks_total == 12


async def test_get_status_reports_done_without_touching_redis() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="done"))
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    status = await service.get_status(tdr_id, session)  # type: ignore[arg-type]

    assert status.status == "done"


async def test_get_status_raises_not_found_for_unknown_tdr_id() -> None:
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    with pytest.raises(NotFoundError):
        await service.get_status(uuid4(), _FakeSession())  # type: ignore[arg-type]


async def test_get_tdr_raises_not_ready_while_still_processing() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="processing"))
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    with pytest.raises(ResourceNotReadyError):
        await service.get_tdr(tdr_id, session)  # type: ignore[arg-type]


async def test_get_tdr_raises_not_ready_with_error_message_when_failed() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="failed", error_message="TDR extraction failed"))
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    with pytest.raises(ResourceNotReadyError, match="TDR extraction failed"):
        await service.get_tdr(tdr_id, session)  # type: ignore[arg-type]


async def test_get_tdr_returns_the_extracted_tdr_once_done() -> None:
    tdr_id = uuid4()
    extracted = {
        "tdr_id": str(tdr_id),
        "mission_title": "Mission",
        "client": None,
        "sector": None,
        "deadline": None,
        "positions": [],
        "raw_text": "raw",
        "source_file_path": "tdr.pdf",
    }
    session = _FakeSession()
    session.added.append(
        TDRModel(tdr_id=tdr_id, status="done", mission_title="Mission", extracted_json=extracted)
    )
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    tdr = await service.get_tdr(tdr_id, session)  # type: ignore[arg-type]

    assert tdr.mission_title == "Mission"
    assert tdr.tdr_id == str(tdr_id)


async def test_run_matching_enqueues_when_extraction_is_done() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="done"))
    queue = _FakeQueue()
    service = TdrsService(queue=queue, redis_client=_FakeRedis())  # type: ignore[arg-type]

    await service.run_matching(tdr_id, session)  # type: ignore[arg-type]

    assert len(queue.enqueued) == 1
    func, args, job_timeout = queue.enqueued[0]
    assert func.__name__ == "run_matching"
    assert args == (str(tdr_id),)
    assert job_timeout >= 300


async def test_run_matching_writes_processing_progress_to_redis_before_enqueueing() -> None:
    """Regression test: run_matching must write a fresh "processing" state
    to Redis synchronously, before the enqueue call, so a match-status poll
    landing between the 202 response and the worker dequeuing the job never
    reads stale state left over from a previous run."""
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="done"))
    calls: list[str] = []
    queue = _FakeQueue(calls=calls)
    redis = _FakeRedis(calls=calls)
    service = TdrsService(queue=queue, redis_client=redis)  # type: ignore[arg-type]

    await service.run_matching(tdr_id, session)  # type: ignore[arg-type]

    assert calls == ["hset", "enqueue"]  # progress write must happen before the job is scheduled
    progress = redis.hgetall(f"tdr:{tdr_id}:matching_progress")
    assert progress[b"status"] == b"processing"
    assert progress[b"positions_done"] == b"0"
    assert progress[b"positions_total"] == b"0"
    assert len(queue.enqueued) == 1  # progress write didn't block the job from also being scheduled


async def test_run_matching_overwrites_stale_done_status_left_by_a_previous_run() -> None:
    """Without the synchronous progress write, a poll landing right after
    the 202 response would still see this stale "done" from the prior
    matching run and stop polling before the new run has scored anything."""
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="done"))
    queue = _FakeQueue()
    redis = _FakeRedis(
        {
            f"tdr:{tdr_id}:matching_progress": {
                b"status": b"done",
                b"positions_done": b"3",
                b"positions_total": b"3",
            }
        }
    )
    service = TdrsService(queue=queue, redis_client=redis)  # type: ignore[arg-type]

    await service.run_matching(tdr_id, session)  # type: ignore[arg-type]

    progress = redis.hgetall(f"tdr:{tdr_id}:matching_progress")
    assert progress[b"status"] == b"processing"
    assert progress[b"positions_done"] == b"0"
    assert progress[b"positions_total"] == b"0"


async def test_run_matching_raises_not_found_for_unknown_tdr_id() -> None:
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    with pytest.raises(NotFoundError):
        await service.run_matching(uuid4(), _FakeSession())  # type: ignore[arg-type]


async def test_run_matching_raises_not_ready_while_extraction_still_processing() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="processing"))
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    with pytest.raises(ResourceNotReadyError):
        await service.run_matching(tdr_id, session)  # type: ignore[arg-type]


async def test_get_matching_status_raises_not_found_for_unknown_tdr_id() -> None:
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    with pytest.raises(NotFoundError):
        await service.get_matching_status(uuid4(), _FakeSession())  # type: ignore[arg-type]


async def test_get_matching_status_reports_not_started_when_matching_never_run() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="done"))
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    status = await service.get_matching_status(tdr_id, session)  # type: ignore[arg-type]

    assert status.status == "not_started"


async def test_get_matching_status_reports_processing_progress() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="done"))
    redis = _FakeRedis(
        {
            f"tdr:{tdr_id}:matching_progress": {
                b"status": b"processing",
                b"positions_done": b"1",
                b"positions_total": b"3",
            }
        }
    )
    service = TdrsService(queue=_FakeQueue(), redis_client=redis)  # type: ignore[arg-type]

    status = await service.get_matching_status(tdr_id, session)  # type: ignore[arg-type]

    assert status.status == "processing"
    assert status.positions_done == 1
    assert status.positions_total == 3
