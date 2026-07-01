from fastapi import APIRouter, UploadFile

from app.domain.tdr import TDR
from app.features.tdrs.service import TdrsService

router = APIRouter(prefix="/tdrs", tags=["tdrs"])
service = TdrsService()


@router.post("", response_model=TDR)
async def upload_tdr(file: UploadFile) -> TDR:
    return await service.upload_tdr(file)


@router.get("/{tdr_id}", response_model=TDR)
async def get_tdr(tdr_id: str) -> TDR:
    return await service.get_tdr(tdr_id)


@router.post("/{tdr_id}/match", status_code=202)
async def run_matching(tdr_id: str) -> None:
    await service.run_matching(tdr_id)
