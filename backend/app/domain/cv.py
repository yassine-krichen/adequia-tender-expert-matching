from datetime import date

from pydantic import BaseModel, Field


class Education(BaseModel):
    degree: str
    field: str
    institution: str
    country: str | None = None
    graduation_year: int | None = None
    source_span: str


class Certification(BaseModel):
    name: str
    issuing_body: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    source_span: str


class Experience(BaseModel):
    title: str
    employer: str
    sector: str | None = None
    start_date: date
    end_date: date | None = None  # None = current
    responsibilities: list[str] = Field(default_factory=list)
    source_span: str


class LanguageProficiency(BaseModel):
    language: str
    level: str  # e.g. "native", "B2", "fluent" — normalize later


class NormalizedSkill(BaseModel):
    raw_term: str
    canonical_id: str | None = None  # taxonomy node id, None if unmatched
    confidence: float
    matched_via: str  # "direct" | "rag_retry" | "llm_fallback"


class CandidateCV(BaseModel):
    """The extraction contract for one employee CV.

    total_years_experience is computed at query time from Experience entries,
    never stored as a fixed number — see docs/02-data-schemas.md.
    """

    candidate_id: str
    full_name: str
    education: list[Education]
    certifications: list[Certification]
    experience: list[Experience]
    languages: list[LanguageProficiency]
    raw_skills: list[str]
    normalized_skills: list[NormalizedSkill] = Field(default_factory=list)
    total_years_experience: float
    raw_text: str
    source_file_path: str
