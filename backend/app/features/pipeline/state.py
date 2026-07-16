from typing import TypedDict

from app.domain.cv import CandidateCV, NormalizedSkill
from app.domain.matching import Anomaly, Citation, ReviewDecision, SubScores
from app.domain.tdr import ExpertPosition


class PipelineState(TypedDict):
    """Matching-pipeline graph state — one run per CV-position shortlist entry.

    Runs per TDR position against a shortlist, never per full CV pool.
    See docs/03-agent-pipeline.md.
    """

    cv_raw_text: str
    tdr_raw_text: str
    position: ExpertPosition
    cv_extracted: CandidateCV | None
    normalized_skills: list[NormalizedSkill] | None
    normalized_position_skills: list[NormalizedSkill]
    required_sector_vector: list[float] | None
    sector: str | None
    hard_filter_passed: bool | None
    hard_filter_failures: list[str]
    sub_scores: SubScores | None
    compatibility_score: float | None
    qualitative_fit_reasoning: str | None
    sector_match_source_span: str | None
    anomalies: list[Anomaly]
    rationale: str | None
    citations: list[Citation]
    needs_human_review: bool
    reviewer_decision: ReviewDecision | None
