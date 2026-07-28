from datetime import datetime

from pydantic import BaseModel


class SkillCandidateSummary(BaseModel):
    """GET /admin/skill-candidates response shape -- one harvested
    genuinely-unmatched skill term awaiting human review.
    """

    candidate_id: str
    raw_term: str
    occurrence_count: int
    best_similarity: float | None
    suggested_canonical_name: str | None
    suggested_aliases: list[str]
    first_seen_at: datetime


class ApproveSkillCandidateRequest(BaseModel):
    """The human reviewer's final decision on what this term should be
    canonicalized as -- may differ from raw_term (e.g. normalizing a typo
    or an abbreviation into its full canonical form).
    """

    canonical_name: str
    aliases: list[str] = []


class RejectSkillCandidateRequest(BaseModel):
    note: str | None = None
