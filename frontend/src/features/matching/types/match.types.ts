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
