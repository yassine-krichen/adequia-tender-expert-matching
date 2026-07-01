from datetime import date

from pydantic import BaseModel, Field


class LanguageRequirement(BaseModel):
    language: str
    minimum_level: str


class ExpertPosition(BaseModel):
    position_id: str
    position_title: str  # e.g. "Team Leader", "QA Expert"
    mandatory_diploma: str | None = None
    minimum_years_experience: float | None = None
    required_certifications: list[str] = Field(default_factory=list)
    required_languages: list[LanguageRequirement] = Field(default_factory=list)
    required_sector_experience: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    evaluation_weight: float | None = None  # if TDR specifies scoring weights
    source_span: str


class TDR(BaseModel):
    tdr_id: str
    mission_title: str
    client: str | None = None
    sector: str | None = None
    deadline: date | None = None
    positions: list[ExpertPosition]
    raw_text: str
    source_file_path: str
