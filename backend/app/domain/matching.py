from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    employment_gap = "employment_gap"
    date_overlap = "date_overlap"
    expired_certification = "expired_certification"
    education_date_inconsistency = "education_date_inconsistency"
    unverifiable_claim = "unverifiable_claim"
    title_seniority_mismatch = "title_seniority_mismatch"
    missing_mandatory_requirement = "missing_mandatory_requirement"


class AnomalySeverity(str, Enum):
    info = "info"
    warning = "warning"
    blocking = "blocking"


class Anomaly(BaseModel):
    type: AnomalyType
    severity: AnomalySeverity
    description: str
    source_citation: str  # points back into raw_text


class Citation(BaseModel):
    claim: str  # the claim being supported
    source_doc: str  # "cv" | "tdr"
    source_span: str


class SubScores(BaseModel):
    """education_score/experience_score/certification_score/language_score
    are unset this sprint — only skill_score and sector_score are computed
    (see docs/scrum/sprint-2-plan.md ADQ-16). The other four need
    detect_anomalies/generate_report context to score meaningfully and are
    Sprint 3 work; leaving them null is more honest than a fabricated
    placeholder number.
    """

    education_score: float | None = None
    experience_score: float | None = None
    certification_score: float | None = None
    sector_score: float
    language_score: float | None = None
    skill_score: float


class MatchResult(BaseModel):
    """hard_filter_passed=false implies compatibility_score is None — a
    rejected-on-hard-filter candidate is never ranked. sub_scores, however,
    is always populated regardless of hard_filter_passed: a candidate who
    fails on e.g. years but has strong skill/sector fit should still show
    that fit, not just a bare failure string. See docs/02-data-schemas.md
    and the route_after_hard_filter conditional edge in
    docs/03-agent-pipeline.md.
    """

    match_id: str
    cv_id: str
    tdr_id: str
    position_id: str
    hard_filter_passed: bool
    hard_filter_failures: list[str] = Field(default_factory=list)
    compatibility_score: float | None = None
    sub_scores: SubScores | None = None
    anomalies: list[Anomaly] = Field(default_factory=list)
    # generate_report (the only thing that produces this) is Sprint 3 —
    # a sprint-2 match result has no rationale yet.
    rationale: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    reviewer_decision: str | None = None  # "approved" | "rejected" | "overridden"
    reviewer_id: str | None = None
    reviewer_note: str | None = None
    decided_at: date | None = None
