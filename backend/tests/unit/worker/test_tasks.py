from collections.abc import Sequence
from io import BytesIO
from typing import Any
from uuid import uuid4

from docx import Document
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from app.database.models import TDR as TDRModel
from app.database.models import ExpertPosition as ExpertPositionModel
from app.database.models import MatchResult as MatchResultModel
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
    def __init__(
        self,
        tdr_row: TDRModel,
        existing_positions: list[ExpertPositionModel] | None = None,
        existing_matches: list[MatchResultModel] | None = None,
    ) -> None:
        self._tdr_row = tdr_row
        self.added: list[Any] = []
        self.committed = False
        # Stand-ins for rows already in the DB before this job runs (e.g.
        # leftovers from a prior extraction run), separate from `added`
        # since those were never inserted via this session.
        self.existing_positions = existing_positions or []
        self.existing_matches = existing_matches or []

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

    async def execute(self, stmt: Any) -> None:
        """Fakes the reprocessing deletes (`delete(ExpertPosition/MatchResult)
        .where(tdr_id == ...)`) by dropping rows from the in-memory
        "existing" lists that stand in for the DB, matching both the table
        the statement targets AND the bound tdr_id in its where-clause --
        so a regression that widens or drops the tdr_id filter (e.g. deleting
        every TDR's rows, or filtering on the wrong tdr_id) shows up as rows
        from other TDRs unexpectedly disappearing.
        """
        bound_tdr_id = stmt.whereclause.right.value
        if stmt.table.name == ExpertPositionModel.__tablename__:
            self.existing_positions = [
                row for row in self.existing_positions if row.tdr_id != bound_tdr_id
            ]
        elif stmt.table.name == MatchResultModel.__tablename__:
            self.existing_matches = [
                row for row in self.existing_matches if row.tdr_id != bound_tdr_id
            ]


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


async def test_reprocessing_tdr_replaces_stale_positions_and_matches() -> None:
    """Force-reprocessing the same tdr_id must replace the position set, not
    append to it -- stale positions (and match_results referencing them)
    from a prior extraction run must be gone once the new run commits.
    """
    tdr_id = uuid4()
    other_tdr_id = uuid4()
    tdr_row = TDRModel(tdr_id=tdr_id, status="processing", source_file_path="tdr.pdf")
    stale_position = ExpertPositionModel(
        position_id=uuid4(),
        tdr_id=tdr_id,
        position_title="Stale position from a prior buggy run",
        requirements_json={},
    )
    stale_match = MatchResultModel(
        match_id=uuid4(),
        tdr_id=tdr_id,
        position_id=stale_position.position_id,
        hard_filter_passed=True,
    )
    # Belongs to a different TDR entirely -- the reprocessing delete for
    # `tdr_id` must be scoped and leave these completely untouched.
    other_tdr_position = ExpertPositionModel(
        position_id=uuid4(),
        tdr_id=other_tdr_id,
        position_title="Position belonging to an unrelated TDR",
        requirements_json={},
    )
    other_tdr_match = MatchResultModel(
        match_id=uuid4(),
        tdr_id=other_tdr_id,
        position_id=other_tdr_position.position_id,
        hard_filter_passed=True,
    )
    session = _FakeSession(
        tdr_row,
        existing_positions=[stale_position, other_tdr_position],
        existing_matches=[stale_match, other_tdr_match],
    )
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

    await run_tdr_extraction_job(
        str(tdr_id),
        _valid_docx_bytes("some raw tdr text about staffing requirements"),
        "tdr.docx",
        session=session,  # type: ignore[arg-type]
        router=router,  # type: ignore[arg-type]
        embeddings=router.get_embedding_model(),
        on_progress=lambda step, done, total: None,
    )

    assert tdr_row.status == "done"
    assert session.committed is True

    # The stale rows for this tdr_id must be gone from the DB stand-ins ...
    assert session.existing_positions == [other_tdr_position]
    assert session.existing_matches == [other_tdr_match]

    # ... and only the freshly extracted position remains.
    position_rows = [row for row in session.added if isinstance(row, ExpertPositionModel)]
    assert len(position_rows) == 1
    assert position_rows[0].position_title == "Chef de projet"
    assert position_rows[0].position_id != stale_position.position_id
