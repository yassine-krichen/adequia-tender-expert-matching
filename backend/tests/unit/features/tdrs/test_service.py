from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from langchain_core.embeddings import Embeddings

from app.database.models import TDR as TDRModel
from app.database.models import ExpertPosition as ExpertPositionModel
from app.features.pipeline.nodes.extract import _ExtractedPosition, _TDRChunkExtraction
from app.features.tdrs.service import TdrsService

_SYNTHETIC_TDR_PATH = (
    Path(__file__).resolve().parents[5]
    / "docs"
    / "tdrs"
    / "DP _  Developpement de Applicatif avec 4 modules-revu TAM-ST2I (5).docx"
)


class _FakeRouter:
    def invoke_extraction(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _TDRChunkExtraction:
        return _TDRChunkExtraction(
            mission_title="Développement d'un applicatif à 4 modules",
            client="Ministère de l'Éducation Nationale",
            sector="Éducation",
            positions=[
                _ExtractedPosition(position_title="Chef de projet", source_span="span text")
            ],
        )

    def get_embedding_model(self) -> Embeddings:
        return _FakeEmbeddings()


class _FakeEmbeddings(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        return [1.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True


async def test_upload_tdr_extracts_and_persists_tdr_and_positions() -> None:
    service = TdrsService(router=_FakeRouter())  # type: ignore[arg-type]
    session = _FakeSession()
    upload = UploadFile(file=BytesIO(_SYNTHETIC_TDR_PATH.read_bytes()), filename="tdr.docx")

    result = await service.upload_tdr(upload, session)  # type: ignore[arg-type]

    assert result.mission_title == "Développement d'un applicatif à 4 modules"
    assert result.source_file_path == "tdr.docx"
    assert len(result.positions) == 1
    assert session.committed is True

    tdr_rows = [row for row in session.added if isinstance(row, TDRModel)]
    position_rows = [row for row in session.added if isinstance(row, ExpertPositionModel)]
    assert len(tdr_rows) == 1
    assert len(position_rows) == 1
    assert tdr_rows[0].mission_title == "Développement d'un applicatif à 4 modules"
    assert position_rows[0].tdr_id == tdr_rows[0].tdr_id
    assert position_rows[0].position_title == "Chef de projet"
