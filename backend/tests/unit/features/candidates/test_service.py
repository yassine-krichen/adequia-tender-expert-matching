import hashlib
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.database.models import CV, Candidate
from app.domain.cv import LanguageProficiency
from app.features.candidates.service import CandidatesService
from app.features.pipeline.nodes.extract import (
    _CVExtraction,
    _ExtractedEducation,
    _ExtractedExperience,
)

_SYNTHETIC_CV_PATH = (
    Path(__file__).resolve().parents[5] / "docs" / "cvs" / "synthetic" / "nadia-ben-salah.pdf"
)


class _FakeEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [1.0]


class _FakeRouter:
    def __init__(self) -> None:
        self.extraction_calls = 0

    def get_embedding_model(self) -> _FakeEmbeddings:
        return _FakeEmbeddings()

    def invoke_extraction(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _CVExtraction:
        self.extraction_calls += 1
        return _CVExtraction(
            full_name="Nadia Ben Salah",
            education=[
                _ExtractedEducation(
                    degree="Master",
                    field="IT Project Management",
                    institution="IHEC Carthage",
                    source_span="Master in IT Project Management",
                )
            ],
            certifications=[],
            experience=[
                _ExtractedExperience(
                    title="Cheffe de projet SI",
                    employer="ST2i",
                    start_date="2016-01-01",
                    end_date=None,
                    source_span="Cheffe de projet SI at ST2i since 2016",
                )
            ],
            languages=[LanguageProficiency(language="French", level="fluent")],
            raw_skills=["Gestion de projet"],
        )

    invoke_reasoning = invoke_extraction


class _FakeResult:
    def __init__(self, row: Any | None) -> None:
        self._row = row

    def scalar_one_or_none(self) -> Any | None:
        return self._row


class _FakeSession:
    def __init__(self, existing_cvs: list[CV] | None = None) -> None:
        self.added: list[Any] = [*(existing_cvs or [])]
        self.committed = False
        self.execute_calls = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def get(self, model_cls: type[Any], pk: Any) -> Any | None:
        for obj in self.added:
            if isinstance(obj, model_cls) and getattr(obj, "candidate_id", None) == pk:
                return obj
        return None

    async def execute(self, _stmt: Any) -> _FakeResult:
        """Fakes upload_cv's `select(CV).where(CV.content_hash == ...)` --
        real matching would need parsing the statement, so this just
        returns the first CV row already present (pre-seeded via
        existing_cvs), same as a real dedup hit.
        """
        self.execute_calls += 1
        existing_cv = next((row for row in self.added if isinstance(row, CV)), None)
        return _FakeResult(existing_cv)


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
    assert cv_rows[0].embedding == [1.0]


async def test_upload_cv_returns_existing_candidate_on_duplicate_file_without_re_extracting() -> None:
    router = _FakeRouter()
    file_bytes = _SYNTHETIC_CV_PATH.read_bytes()
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    existing_extracted = {
        "candidate_id": "11111111-1111-1111-1111-111111111111",
        "full_name": "Nadia Ben Salah",
        "education": [],
        "certifications": [],
        "experience": [],
        "languages": [],
        "raw_skills": ["Gestion de projet"],
        "normalized_skills": [],
        "total_years_experience": 5.0,
        "raw_text": "already extracted",
        "source_file_path": "nadia.pdf",
    }
    existing_cv = CV(content_hash=content_hash, raw_text="already extracted", extracted_json=existing_extracted)
    service = CandidatesService(router=router)  # type: ignore[arg-type]
    session = _FakeSession(existing_cvs=[existing_cv])
    upload = UploadFile(file=BytesIO(file_bytes), filename="nadia-again.pdf")

    result = await service.upload_cv(upload, session)  # type: ignore[arg-type]

    assert result.full_name == "Nadia Ben Salah"
    assert result.raw_text == "already extracted"
    assert router.extraction_calls == 0
    assert session.added == [existing_cv]  # nothing new added
    assert session.committed is False


async def test_upload_cv_with_force_re_extracts_in_place_instead_of_using_cache() -> None:
    """force=True is the escape hatch for a known-bad stored extraction
    (e.g. a prompt/pipeline bug fixed after the file was first uploaded)
    -- it must re-run extraction and overwrite the existing row, not
    create a second Candidate/CV pair (content_hash is unique-indexed).
    """
    router = _FakeRouter()
    file_bytes = _SYNTHETIC_CV_PATH.read_bytes()
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    candidate_id = "11111111-1111-1111-1111-111111111111"
    existing_candidate = Candidate(candidate_id=candidate_id, full_name="Stale Name")
    existing_cv = CV(
        candidate_id=candidate_id,
        content_hash=content_hash,
        raw_text="stale extraction",
        extracted_json={"full_name": "Stale Name"},
    )
    service = CandidatesService(router=router)  # type: ignore[arg-type]
    session = _FakeSession(existing_cvs=[existing_candidate, existing_cv])
    upload = UploadFile(file=BytesIO(file_bytes), filename="nadia-again.pdf")

    result = await service.upload_cv(upload, session, force=True)  # type: ignore[arg-type]

    assert result.full_name == "Nadia Ben Salah"
    assert router.extraction_calls == 1
    assert existing_cv.raw_text != "stale extraction"
    assert existing_cv.extracted_json["full_name"] == "Nadia Ben Salah"
    assert existing_candidate.full_name == "Nadia Ben Salah"
    # no new rows -- same two objects, updated in place
    candidate_rows = [row for row in session.added if isinstance(row, Candidate)]
    cv_rows = [row for row in session.added if isinstance(row, CV)]
    assert len(candidate_rows) == 1
    assert len(cv_rows) == 1
    assert session.committed is True
