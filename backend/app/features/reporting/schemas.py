from app.domain.matching import MatchResult


class MatchReportDetail(MatchResult):
    """GET /matches/{match_id} response shape.

    MatchResult itself has no candidate/position/TDR names (only their ids)
    -- the match report page needs them to render a real header, so this is
    the response DTO, not the bare domain model.
    """

    candidate_full_name: str
    position_title: str
    tdr_mission_title: str
