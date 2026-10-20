from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.domain.cv import CandidateCV
from app.features.candidates.schemas import CandidateSummary
from app.features.candidates.service import CandidatesService

router = APIRouter(prefix="/candidates", tags=["candidates"])
service = CandidatesService()


@router.post("/cv", response_model=CandidateCV)
async def upload_cv(
    file: UploadFile,
    force: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateCV:
    """force=true re-runs extraction on an already-uploaded file (same
    content_hash) instead of returning the cached result -- use after a
    pipeline/prompt fix to re-process a CV whose stored extraction is
    known-bad.
    """
    return await service.upload_cv(file, session, force=force)


@router.get("", response_model=list[CandidateSummary])
async def list_candidates(
    session: AsyncSession = Depends(get_db_session),
) -> list[CandidateSummary]:
    return await service.list_candidates(session)


@router.get("/{candidate_id}", response_model=CandidateCV)
async def get_candidate_cv(
    candidate_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> CandidateCV:
    return await service.get_candidate_cv(candidate_id, session)
