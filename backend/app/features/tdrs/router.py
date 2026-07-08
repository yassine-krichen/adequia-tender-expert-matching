from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.domain.tdr import TDR
from app.features.tdrs.schemas import MatchingStatus, TdrStatus, TdrUploadAck
from app.features.tdrs.service import TdrsService

router = APIRouter(prefix="/tdrs", tags=["tdrs"])
service = TdrsService()


@router.post("", response_model=TdrUploadAck, status_code=202)
async def upload_tdr(
    file: UploadFile,
    force: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> TdrUploadAck:
    """force=true re-runs extraction on an already-uploaded file (same
    content_hash) instead of returning the cached result -- use after a
    pipeline/prompt fix to re-process a TDR whose stored extraction is
    known-bad.
    """
    return await service.upload_tdr(file, session, force=force)


@router.get("/{tdr_id}/status", response_model=TdrStatus)
async def get_tdr_status(
    tdr_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> TdrStatus:
    return await service.get_status(tdr_id, session)


@router.get("/{tdr_id}", response_model=TDR)
async def get_tdr(tdr_id: UUID, session: AsyncSession = Depends(get_db_session)) -> TDR:
    return await service.get_tdr(tdr_id, session)


@router.post("/{tdr_id}/match", status_code=202)
async def run_matching(
    tdr_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> None:
    await service.run_matching(tdr_id, session)


@router.get("/{tdr_id}/match-status", response_model=MatchingStatus)
async def get_matching_status(
    tdr_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> MatchingStatus:
    return await service.get_matching_status(tdr_id, session)
