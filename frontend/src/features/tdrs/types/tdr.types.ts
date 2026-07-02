export type ExpertPosition = {
  positionId: string;
  positionTitle: string;
  mandatoryDiploma: string | null;
  minimumYearsExperience: number | null;
};

export type Tdr = {
  tdrId: string;
  missionTitle: string;
  client: string | null;
  sector: string | null;
  positions: ExpertPosition[];
};

// Mirrors backend/app/domain/tdr.py field-for-field (including snake_case)
// since this is the raw POST /tdrs response body, not a UI model.
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
