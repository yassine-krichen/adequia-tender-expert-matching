from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.models import CV, Candidate
from app.domain.cv import CandidateCV
from app.features.pipeline.nodes.extract import extract_cv
from app.features.pipeline.nodes.ingest import extract_raw_text


class CandidatesService:
    """Owns CV ingestion and the candidate roster.

    Re-uploading a CV triggers re-extraction and re-embedding for that
    candidate only — see docs/05-frontend-dashboard.md.
    """

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router or ModelRouter(get_settings())

    async def upload_cv(self, file: UploadFile, session: AsyncSession) -> CandidateCV:
        file_bytes = await file.read()
        filename = file.filename or "upload"

        raw_text = extract_raw_text(file_bytes, filename)
        candidate_id = uuid4()
        candidate_cv = extract_cv(
            raw_text,
            candidate_id=str(candidate_id),
            source_file_path=filename,
            router=self._router,
        )

        session.add(Candidate(candidate_id=candidate_id, full_name=candidate_cv.full_name))
        # Flush before adding the CV row — without a relationship() between
        # Candidate and CV, SQLAlchemy's unit-of-work doesn't guarantee
        # FK-safe insert ordering on its own, and can emit the CV insert
        # first, violating cvs_candidate_id_fkey.
        await session.flush()
        session.add(
            CV(
                candidate_id=candidate_id,
                total_years_experience=candidate_cv.total_years_experience,
                raw_text=raw_text,
                source_file_path=filename,
                extracted_json=candidate_cv.model_dump(mode="json"),
            )
        )
        await session.commit()

        return candidate_cv

    async def list_candidates(self) -> list[CandidateCV]:
        raise NotImplementedError
