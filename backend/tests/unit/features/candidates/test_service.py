import hashlib
import uuid
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CV, EMBEDDING_DIMENSION, Candidate
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


class _FakeEmbeddings768:
    """The real `embedding` column is a fixed-width pgvector(768) -- the
    real-session (SQLite) tests insert against the actual column type, so
    (unlike _FakeSession, which never validates dimensionality) they need
    a vector of the real width or the insert itself raises.
    """

    def embed_query(self, text: str) -> list[float]:
        return [1.0] * EMBEDDING_DIMENSION


class _FakeRouter:
    def __init__(self, *, real_embedding_dim: bool = False) -> None:
        self.extraction_calls = 0
        self._real_embedding_dim = real_embedding_dim

    def get_embedding_model(self) -> _FakeEmbeddings | _FakeEmbeddings768:
        return _FakeEmbeddings768() if self._real_embedding_dim else _FakeEmbeddings()

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


_LEGACY_EXTRACTED_JSON = {
    "candidate_id": "22222222-2222-2222-2222-222222222222",
    "full_name": "Legacy Someone",
    "education": [],
    "certifications": [],
    "experience": [],
    "languages": [],
    "raw_skills": [],
    "normalized_skills": [],
    "total_years_experience": 0.0,
    "raw_text": "legacy pre-migration extraction",
    "source_file_path": "legacy.pdf",
}


async def _seed_legacy_null_hash_cv(session: AsyncSession) -> uuid.UUID:
    """A CV row inserted before migration 0006 added content_hash: the
    column exists but is NULL because there was no stored file to hash
    retroactively (see backend/scripts/backfill_cv_content_hash.py).
    """
    legacy_candidate_id = uuid.uuid4()
    session.add(Candidate(candidate_id=legacy_candidate_id, full_name="Legacy Someone"))
    await session.flush()
    session.add(
        CV(
            candidate_id=legacy_candidate_id,
            raw_text="legacy pre-migration extraction",
            source_file_path="legacy.pdf",
            content_hash=None,
            extracted_json=_LEGACY_EXTRACTED_JSON,
        )
    )
    await session.commit()
    return legacy_candidate_id


async def test_upload_cv_uploaded_twice_without_force_reuses_same_candidate(
    db_session: AsyncSession,
) -> None:
    """Regression test for a live bug: re-uploading a CV whose existing row
    predates the content_hash column (migration 0006) had a NULL hash, so
    the dedup lookup silently missed it and a second upload of the exact
    same file created a brand-new Candidate/CV pair for the same person
    instead of reusing the existing candidate_id -- see
    backend/scripts/backfill_cv_content_hash.py.

    Uses a real SQLite-backed session (not _FakeSession, which ignores
    query predicates and would happily "match" any pre-seeded CV row
    regardless of its hash). A legacy NULL-hash CV row is seeded first: if
    the dedup lookup ever regresses to "find any CV row" instead of
    "WHERE content_hash == :hash", the first upload below would
    incorrectly short-circuit to that unrelated legacy candidate instead
    of running extraction and creating a new one.
    """
    router = _FakeRouter(real_embedding_dim=True)
    service = CandidatesService(router=router)  # type: ignore[arg-type]
    legacy_candidate_id = await _seed_legacy_null_hash_cv(db_session)
    file_bytes = _SYNTHETIC_CV_PATH.read_bytes()

    first = await service.upload_cv(
        UploadFile(file=BytesIO(file_bytes), filename="nadia.pdf"), db_session
    )
    second = await service.upload_cv(
        UploadFile(file=BytesIO(file_bytes), filename="nadia-again.pdf"), db_session
    )

    assert first.candidate_id == second.candidate_id
    assert first.candidate_id != str(legacy_candidate_id)
    assert router.extraction_calls == 1  # second upload short-circuited to the cached result

    candidate_rows = (await db_session.execute(select(Candidate))).scalars().all()
    cv_rows = (await db_session.execute(select(CV))).scalars().all()
    assert len(candidate_rows) == 2  # the seeded legacy one + the new one
    assert len(cv_rows) == 2
    new_cv = next(row for row in cv_rows if row.content_hash is not None)
    assert str(new_cv.candidate_id) == first.candidate_id


async def test_upload_cv_uploaded_twice_with_force_reuses_same_candidate(
    db_session: AsyncSession,
) -> None:
    """Same regression as above, but for the force=True path: force must
    re-extract in place on the SAME candidate/CV row across two real
    upload_cv calls, never spin up a second Candidate/CV pair -- and must
    still resolve to the newly created candidate, not the seeded legacy
    NULL-hash row.
    """
    router = _FakeRouter(real_embedding_dim=True)
    service = CandidatesService(router=router)  # type: ignore[arg-type]
    legacy_candidate_id = await _seed_legacy_null_hash_cv(db_session)
    file_bytes = _SYNTHETIC_CV_PATH.read_bytes()

    first = await service.upload_cv(
        UploadFile(file=BytesIO(file_bytes), filename="nadia.pdf"), db_session
    )
    second = await service.upload_cv(
        UploadFile(file=BytesIO(file_bytes), filename="nadia-again.pdf"),
        db_session,
        force=True,
    )

    assert first.candidate_id == second.candidate_id
    assert first.candidate_id != str(legacy_candidate_id)
    assert router.extraction_calls == 2  # force re-ran extraction on the second upload

    candidate_rows = (await db_session.execute(select(Candidate))).scalars().all()
    cv_rows = (await db_session.execute(select(CV))).scalars().all()
    assert len(candidate_rows) == 2  # the seeded legacy one + the new one
    assert len(cv_rows) == 2
    new_cv = next(row for row in cv_rows if row.content_hash is not None)
    assert str(new_cv.candidate_id) == first.candidate_id


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
