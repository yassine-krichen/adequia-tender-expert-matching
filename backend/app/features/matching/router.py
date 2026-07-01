from fastapi import APIRouter

from app.domain.matching import MatchResult
from app.features.matching.service import MatchingService

router = APIRouter(prefix="/positions", tags=["matching"])
service = MatchingService()


@router.get("/{position_id}/matches", response_model=list[MatchResult])
async def list_matches_for_position(position_id: str) -> list[MatchResult]:
    return await service.list_matches_for_position(position_id)
