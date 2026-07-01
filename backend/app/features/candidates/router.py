from fastapi import APIRouter, UploadFile

from app.domain.cv import CandidateCV
from app.features.candidates.service import CandidatesService

router = APIRouter(prefix="/candidates", tags=["candidates"])
service = CandidatesService()


@router.post("/cv", response_model=CandidateCV)
async def upload_cv(file: UploadFile) -> CandidateCV:
    return await service.upload_cv(file)


@router.get("", response_model=list[CandidateCV])
async def list_candidates() -> list[CandidateCV]:
    return await service.list_candidates()
