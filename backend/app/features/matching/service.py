from app.domain.matching import MatchResult


class MatchingService:
    """Reads ranked match results produced by the pipeline for a given position."""

    async def list_matches_for_position(self, position_id: str) -> list[MatchResult]:
        raise NotImplementedError
