export type Candidate = {
  candidateId: string;
  fullName: string;
  lastUpdated: string;
};

// Mirrors backend/app/domain/cv.py field-for-field (including snake_case)
// since this is the raw POST /candidates/cv response body, not a UI model.
export type Education = {
  degree: string;
  // Real CVs often don't cleanly separate degree from field of study.
  field: string | null;
  institution: string;
  country: string | null;
  graduation_year: number | null;
  source_span: string;
};

export type Certification = {
  name: string;
  issuing_body: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  source_span: string;
};

export type Experience = {
  title: string;
  employer: string;
  sector: string | null;
  start_date: string;
  end_date: string | null;
  responsibilities: string[];
  source_span: string;
};

export type LanguageProficiency = {
  language: string;
  level: string;
};

export type CandidateCvExtraction = {
  candidate_id: string;
  full_name: string;
  education: Education[];
  certifications: Certification[];
  experience: Experience[];
  languages: LanguageProficiency[];
  raw_skills: string[];
  total_years_experience: number;
  source_file_path: string;
};
