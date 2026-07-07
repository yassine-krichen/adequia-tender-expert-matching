from uuid import UUID

from app.domain.matching import MatchResult


class ReportingService:
    """Owns the full match report and the human-in-the-loop review decision.

    An override is written to match_results.reviewer_decision and appended to
    historical_decisions, closing the loop for future scoring calibration —
    see docs/03-agent-pipeline.md.
    """

    async def get_match(self, match_id: UUID) -> MatchResult:
        raise NotImplementedError

    async def submit_review(
        self, match_id: UUID, decision: str, reviewer_id: str, note: str | None
    ) -> MatchResult:
        raise NotImplementedError
