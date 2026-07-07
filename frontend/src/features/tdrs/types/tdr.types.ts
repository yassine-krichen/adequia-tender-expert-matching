// Mirrors backend/app/domain/tdr.py field-for-field (including snake_case)
// since this is the raw GET /tdrs/{id} response body once processing is
// done, not a UI model. POST /tdrs itself returns TdrUploadAck below.
export type LanguageRequirement = {
  language: string;
  minimum_level: string;
};

export type ExpertPositionExtraction = {
  position_id: string;
  position_title: string;
  mandatory_diploma: string | null;
  minimum_years_experience: number | null;
  required_certifications: string[];
  required_languages: LanguageRequirement[];
  required_sector_experience: string | null;
  required_skills: string[];
  evaluation_weight: number | null;
  source_span: string;
};

export type TdrExtraction = {
  tdr_id: string;
  mission_title: string;
  client: string | null;
  sector: string | null;
  deadline: string | null;
  positions: ExpertPositionExtraction[];
  source_file_path: string;
};

// POST /tdrs no longer returns the full extraction — it runs on a
// background worker (can take over a minute on a long TDR), so the request
// returns immediately with just this ack. Poll GET /tdrs/{tdr_id}/status.
export type TdrUploadAck = {
  tdr_id: string;
  status: 'processing' | 'done' | 'failed';
};

export type TdrStatus = {
  tdr_id: string;
  status: 'processing' | 'done' | 'failed';
  step: 'parsing' | 'retrieving' | 'extracting' | 'merging' | null;
  chunks_done: number | null;
  chunks_total: number | null;
  error_message: string | null;
};
