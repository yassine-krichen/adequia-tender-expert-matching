from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.models import CV, Candidate
from app.domain.cv import CandidateCV
from app.features.candidates.schemas import CandidateSummary
from app.features.pipeline.nodes.extract import extract_cv
from app.features.pipeline.nodes.ingest import extract_raw_text


def _build_cv_embedding_text(cv: CandidateCV) -> str:
    """Coarse-retrieval signal (ADQ-11): skills carry the most weight, plus
    job titles/sectors for a bit of semantic coverage beyond a bare
    skill-term list.
    """
    parts = list(cv.raw_skills)
    parts.extend(exp.title for exp in cv.experience)
    parts.extend(exp.sector for exp in cv.experience if exp.sector)
    return " ".join(parts)


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

        embedding = self._router.get_embedding_model().embed_query(
            _build_cv_embedding_text(candidate_cv)
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
                embedding=embedding,
            )
        )
        await session.commit()

        return candidate_cv

    async def list_candidates(self, session: AsyncSession) -> list[CandidateSummary]:
        # A candidate has exactly one CV today (no re-upload/update flow
        # yet), but group by candidate_id + max(created_at) rather than a
        # bare join so this doesn't silently duplicate roster rows once
        # re-upload lands.
        latest_cv = (
            select(CV.candidate_id, func.max(CV.created_at).label("last_updated"))
            .group_by(CV.candidate_id)
            .subquery()
        )
        stmt = (
            select(Candidate.candidate_id, Candidate.full_name, latest_cv.c.last_updated)
            .join(latest_cv, latest_cv.c.candidate_id == Candidate.candidate_id)
            .order_by(latest_cv.c.last_updated.desc())
        )
        rows = (await session.execute(stmt)).all()
        return [
            CandidateSummary(
                candidate_id=str(row.candidate_id),
                full_name=row.full_name,
                last_updated=row.last_updated,
            )
            for row in rows
        ]
