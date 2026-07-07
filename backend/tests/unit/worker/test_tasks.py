from collections.abc import Sequence
from io import BytesIO
from typing import Any
from uuid import uuid4

from docx import Document
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from app.database.models import TDR as TDRModel
from app.database.models import ExpertPosition as ExpertPositionModel
from app.features.pipeline.nodes.extract import _ExtractedPosition, _TDRChunkExtraction
from app.worker.tasks import run_tdr_extraction_job


class _FakeEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [1.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


class _FakeRouter:
    def __init__(self, responses: Sequence[_TDRChunkExtraction | Exception]) -> None:
        self._responses = iter(responses)

    def invoke_extraction(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _TDRChunkExtraction:
        return self._next_response()

    def invoke_reasoning(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _TDRChunkExtraction:
        return self._next_response()

    def _next_response(self) -> _TDRChunkExtraction:
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response

    def get_embedding_model(self) -> _FakeEmbeddings:
        return _FakeEmbeddings()


class _FakeSession:
    def __init__(self, tdr_row: TDRModel) -> None:
        self._tdr_row = tdr_row
        self.added: list[Any] = []
        self.committed = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

    async def get(self, model_cls: type[Any], pk: Any) -> Any | None:
        if model_cls is TDRModel and pk == self._tdr_row.tdr_id:
            return self._tdr_row
        return None


def _valid_docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _validation_error() -> ValidationError:
    try:
        _TDRChunkExtraction.model_validate({"positions": [{"position_title": 1}]})
    except ValidationError as exc:
        return exc
    raise AssertionError("expected ValidationError")


async def test_run_tdr_extraction_job_marks_the_row_done_and_persists_positions() -> None:
    tdr_id = uuid4()
    tdr_row = TDRModel(tdr_id=tdr_id, status="processing", source_file_path="tdr.pdf")
    session = _FakeSession(tdr_row)
    router = _FakeRouter(
        [
            _TDRChunkExtraction(
                mission_title="Mission",
                client="Client",
                positions=[
                    _ExtractedPosition(
                        position_title="Chef de projet", mandatory_diploma="Bac+5", source_span="span"
                    )
                ],
            )
        ]
    )
    progress_calls: list[tuple[str, int, int]] = []

    await run_tdr_extraction_job(
        str(tdr_id),
        _valid_docx_bytes("some raw tdr text about staffing requirements"),
        "tdr.docx",
        session=session,  # type: ignore[arg-type]
        router=router,  # type: ignore[arg-type]
        embeddings=router.get_embedding_model(),
        on_progress=lambda step, done, total: progress_calls.append((step, done, total)),
    )

    assert tdr_row.status == "done"
    assert tdr_row.mission_title == "Mission"
    assert tdr_row.extracted_json is not None
    assert session.committed is True

    position_rows = [row for row in session.added if isinstance(row, ExpertPositionModel)]
    assert len(position_rows) == 1
    assert position_rows[0].tdr_id == tdr_id
    assert position_rows[0].position_title == "Chef de projet"

    assert progress_calls[0][0] == "parsing"
    assert any(step == "extracting" for step, _, _ in progress_calls)
    assert progress_calls[-1][0] == "merging"


async def test_run_tdr_extraction_job_marks_the_row_failed_without_leaking_internal_details() -> None:
    tdr_id = uuid4()
    tdr_row = TDRModel(tdr_id=tdr_id, status="processing", source_file_path="tdr.pdf")
    session = _FakeSession(tdr_row)
    router = _FakeRouter([_validation_error(), OutputParserException("still broken")])

    await run_tdr_extraction_job(
        str(tdr_id),
        _valid_docx_bytes("some raw tdr text about staffing requirements"),
        "tdr.docx",
        session=session,  # type: ignore[arg-type]
        router=router,  # type: ignore[arg-type]
        embeddings=router.get_embedding_model(),
        on_progress=lambda step, done, total: None,
    )

    assert tdr_row.status == "failed"
    assert tdr_row.error_message == "TDR section extraction failed"
    assert session.committed is True
    assert not any(isinstance(row, ExpertPositionModel) for row in session.added)
