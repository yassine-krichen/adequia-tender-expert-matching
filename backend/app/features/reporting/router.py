from pydantic import BaseModel

from fastapi import APIRouter

from app.domain.matching import MatchResult
from app.features.reporting.service import ReportingService

router = APIRouter(prefix="/matches", tags=["reporting"])
service = ReportingService()


class ReviewDecisionRequest(BaseModel):
    decision: str  # "approved" | "rejected" | "overridden"
    reviewer_id: str
    note: str | None = None


@router.get("/{match_id}", response_model=MatchResult)
async def get_match(match_id: str) -> MatchResult:
    return await service.get_match(match_id)


@router.post("/{match_id}/review", response_model=MatchResult)
async def submit_review(match_id: str, body: ReviewDecisionRequest) -> MatchResult:
    return await service.submit_review(match_id, body.decision, body.reviewer_id, body.note)
