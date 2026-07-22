from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.domain.matching import ReviewDecision
from app.features.reporting.schemas import MatchReportDetail
from app.features.reporting.service import ReportingService

router = APIRouter(prefix="/matches", tags=["reporting"])
service = ReportingService()


class ReviewDecisionRequest(BaseModel):
    decision: ReviewDecision
    note: str | None = None


@router.get("/{match_id}", response_model=MatchReportDetail)
async def get_match(
    match_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> MatchReportDetail:
    return await service.get_match(match_id, session)


@router.post("/{match_id}/review", response_model=MatchReportDetail)
async def submit_review(
    match_id: UUID,
    body: ReviewDecisionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MatchReportDetail:
    return await service.submit_review(match_id, body.decision, body.note, session)
