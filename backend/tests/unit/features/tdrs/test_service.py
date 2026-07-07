from io import BytesIO
from typing import Any
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.common.exceptions import NotFoundError, ResourceNotReadyError
from app.database.models import TDR as TDRModel
from app.features.tdrs.service import TdrsService


class _FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[Any, tuple[Any, ...], int]] = []

    def enqueue(self, func: Any, *args: Any, job_timeout: int) -> None:
        self.enqueued.append((func, args, job_timeout))


class _FakeRedis:
    def __init__(self, progress: dict[str, dict[bytes, bytes]] | None = None) -> None:
        self._progress = progress or {}

    def hgetall(self, key: str) -> dict[bytes, bytes]:
        return self._progress.get(key, {})


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


async def test_get_status_reports_processing_with_redis_progress() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="processing"))
    redis = _FakeRedis(
        {f"tdr:{tdr_id}:progress": {b"step": b"extracting", b"chunks_done": b"3", b"chunks_total": b"12"}}
    )
    service = TdrsService(queue=_FakeQueue(), redis_client=redis)  # type: ignore[arg-type]

    status = await service.get_status(str(tdr_id), session)  # type: ignore[arg-type]

    assert status.status == "processing"
    assert status.step == "extracting"
    assert status.chunks_done == 3
    assert status.chunks_total == 12


async def test_get_status_reports_done_without_touching_redis() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="done"))
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    status = await service.get_status(str(tdr_id), session)  # type: ignore[arg-type]

    assert status.status == "done"


async def test_get_status_raises_not_found_for_unknown_tdr_id() -> None:
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    with pytest.raises(NotFoundError):
        await service.get_status(str(uuid4()), _FakeSession())  # type: ignore[arg-type]


async def test_get_tdr_raises_not_ready_while_still_processing() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="processing"))
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    with pytest.raises(ResourceNotReadyError):
        await service.get_tdr(str(tdr_id), session)  # type: ignore[arg-type]


async def test_get_tdr_raises_not_ready_with_error_message_when_failed() -> None:
    tdr_id = uuid4()
    session = _FakeSession()
    session.added.append(TDRModel(tdr_id=tdr_id, status="failed", error_message="TDR extraction failed"))
    service = TdrsService(queue=_FakeQueue(), redis_client=_FakeRedis())  # type: ignore[arg-type]

    with pytest.raises(ResourceNotReadyError, match="TDR extraction failed"):
        await service.get_tdr(str(tdr_id), session)  # type: ignore[arg-type]


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

    tdr = await service.get_tdr(str(tdr_id), session)  # type: ignore[arg-type]

    assert tdr.mission_title == "Mission"
    assert tdr.tdr_id == str(tdr_id)
