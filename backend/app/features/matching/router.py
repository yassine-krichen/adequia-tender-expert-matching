from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.features.matching.schemas import MatchResultWithCandidate
from app.features.matching.service import MatchingService

router = APIRouter(prefix="/positions", tags=["matching"])
service = MatchingService()


@router.get("/{position_id}/matches", response_model=list[MatchResultWithCandidate])
async def list_matches_for_position(
    position_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> list[MatchResultWithCandidate]:
    return await service.list_matches_for_position(position_id, session)
