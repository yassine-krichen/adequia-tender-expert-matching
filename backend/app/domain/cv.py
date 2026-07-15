from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.common.dates import coerce_partial_date


def _coerce_optional_int(value: Any) -> Any:
    """Real CVs (and models describing them) sometimes give a year as a
    quoted string ("2008") instead of a bare int. Tolerate it the same way
    coerce_partial_date tolerates partial dates.
    """
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return value
    return value


class Education(BaseModel):
    degree: str
    # Real CVs often don't cleanly separate "degree" from "field of study"
    # (e.g. "Diplôme d'ingénieur en Génie Logiciel" is both at once) — never
    # force a value that isn't actually in the text.
    field: str | None = None
    institution: str
    country: str | None = None
    graduation_year: int | None = None
    source_span: str

    _coerce_graduation_year = field_validator("graduation_year", mode="before")(
        _coerce_optional_int
    )


class Certification(BaseModel):
    name: str
    issuing_body: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    source_span: str

    _coerce_issue_date = field_validator("issue_date", mode="before")(coerce_partial_date)
    _coerce_expiry_date = field_validator("expiry_date", mode="before")(coerce_partial_date)


class Experience(BaseModel):
    title: str
    employer: str
    sector: str | None = None
    start_date: date
    end_date: date | None = None  # None = current
    responsibilities: list[str] = Field(default_factory=list)
    source_span: str

    _coerce_start_date = field_validator("start_date", mode="before")(coerce_partial_date)
    _coerce_end_date = field_validator("end_date", mode="before")(coerce_partial_date)


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
    birth_date: date | None = None
    raw_skills: list[str]
    normalized_skills: list[NormalizedSkill] = Field(default_factory=list)
    total_years_experience: float
    raw_text: str
    source_file_path: str

    _coerce_birth_date = field_validator("birth_date", mode="before")(coerce_partial_date)
