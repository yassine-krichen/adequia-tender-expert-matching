from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.domain.cv import CandidateCV
from app.features.candidates.service import CandidatesService

router = APIRouter(prefix="/candidates", tags=["candidates"])
service = CandidatesService()


@router.post("/cv", response_model=CandidateCV)
async def upload_cv(
    file: UploadFile, session: AsyncSession = Depends(get_db_session)
) -> CandidateCV:
    return await service.upload_cv(file, session)


@router.get("", response_model=list[CandidateCV])
async def list_candidates() -> list[CandidateCV]:
    return await service.list_candidates()
