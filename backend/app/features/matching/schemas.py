from app.domain.matching import MatchResult


class MatchResultWithCandidate(MatchResult):
    """GET /positions/{position_id}/matches response shape.

    MatchResult itself has no candidate name (only cv_id) -- the matching
    results page needs one to render, so this is the response DTO, not the
    bare domain model.
    """

    candidate_full_name: str
