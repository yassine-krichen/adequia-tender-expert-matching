from collections.abc import Sequence
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.database.models import CV, Candidate
from app.domain.cv import Education, Experience, LanguageProficiency
from app.features.candidates.service import CandidatesService
from app.features.pipeline.nodes.extract import _CVExtraction

_SYNTHETIC_CV_PATH = (
    Path(__file__).resolve().parents[5] / "docs" / "cvs" / "synthetic" / "nadia-ben-salah.pdf"
)


class _FakeRouter:
    def invoke_extraction(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _CVExtraction:
        return _CVExtraction(
            full_name="Nadia Ben Salah",
            education=[
                Education(
                    degree="Master",
                    field="IT Project Management",
                    institution="IHEC Carthage",
                    source_span="Master in IT Project Management",
                )
            ],
            certifications=[],
            experience=[
                Experience(
                    title="Cheffe de projet SI",
                    employer="ST2i",
                    start_date=date(2016, 1, 1),
                    end_date=None,
                    source_span="Cheffe de projet SI at ST2i since 2016",
                )
            ],
            languages=[LanguageProficiency(language="French", level="fluent")],
            raw_skills=["Gestion de projet"],
        )


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True


async def test_upload_cv_extracts_and_persists_candidate_and_cv() -> None:
    service = CandidatesService(router=_FakeRouter())  # type: ignore[arg-type]
    session = _FakeSession()
    upload = UploadFile(file=BytesIO(_SYNTHETIC_CV_PATH.read_bytes()), filename="nadia.pdf")

    result = await service.upload_cv(upload, session)  # type: ignore[arg-type]

    assert result.full_name == "Nadia Ben Salah"
    assert result.source_file_path == "nadia.pdf"
    assert result.raw_text.strip() != ""
    assert session.committed is True

    candidate_rows = [row for row in session.added if isinstance(row, Candidate)]
    cv_rows = [row for row in session.added if isinstance(row, CV)]
    assert len(candidate_rows) == 1
    assert len(cv_rows) == 1
    assert candidate_rows[0].full_name == "Nadia Ben Salah"
    assert cv_rows[0].candidate_id == candidate_rows[0].candidate_id
    assert cv_rows[0].extracted_json["full_name"] == "Nadia Ben Salah"
