// Mirrors backend/app/features/matching/schemas.py MatchResultWithCandidate
// field-for-field (snake_case) -- same no-translation-layer convention as
// tdr.types.ts. Only skill_score/sector_score are populated this sprint
// (see backend/app/domain/matching.py SubScores docstring) -- the other
// four wait on detect_anomalies/generate_report in Sprint 3.
export type SubScores = {
  education_score: number | null;
  experience_score: number | null;
  certification_score: number | null;
  sector_score: number;
  language_score: number | null;
  skill_score: number;
};

export type MatchResult = {
  match_id: string;
  cv_id: string;
  tdr_id: string;
  position_id: string;
  hard_filter_passed: boolean;
  hard_filter_failures: string[];
  compatibility_score: number | null;
  sub_scores: SubScores | null;
  rationale: string | null;
  candidate_full_name: string;
};

// GET /tdrs/{tdr_id}/match-status response.
export type MatchingStatus = {
  tdr_id: string;
  status: 'not_started' | 'processing' | 'done' | 'failed';
  positions_done: number | null;
  positions_total: number | null;
};

// Mirrors backend/app/domain/matching.py Anomaly/Citation/MatchResult
// field-for-field (snake_case) -- same no-translation-layer convention as
// above. Named MatchDetail, not MatchResult -- that name is already taken by
// the list-view shape above (GET /positions/{id}/matches), which is missing
// qualitative_fit_score/anomalies/citations/reviewer fields entirely.
export type Anomaly = {
  type:
    | 'employment_gap'
    | 'date_overlap'
    | 'expired_certification'
    | 'education_date_inconsistency'
    | 'age_graduation_implausibility'
    | 'unverifiable_claim'
    | 'title_seniority_mismatch'
    | 'missing_mandatory_requirement';
  severity: 'info' | 'warning' | 'blocking';
  description: string;
  source_citation: string;
};

export type Citation = { claim: string; source_doc: string; source_span: string };

export type MatchDetail = {
  match_id: string;
  cv_id: string;
  tdr_id: string;
  position_id: string;
  hard_filter_passed: boolean;
  hard_filter_failures: string[];
  compatibility_score: number | null;
  sub_scores: {
    education_score: number | null;
    experience_score: number | null;
    certification_score: number | null;
    sector_score: number;
    language_score: number | null;
    skill_score: number;
    qualitative_fit_score: number | null;
  } | null;
  anomalies: Anomaly[];
  rationale: string | null;
  citations: Citation[];
  reviewer_decision: string | null;
  reviewer_id: string | null;
  reviewer_note: string | null;
  decided_at: string | null;
  candidate_full_name: string;
  position_title: string;
  tdr_mission_title: string;
};

export type ReviewDecisionRequest = {
  decision: 'approved' | 'rejected' | 'overridden_to_approve' | 'overridden_to_reject';
  note: string | null;
};
