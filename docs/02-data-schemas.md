# 02 — Data Schemas

## Core entities

The central relationship: one **TDR** has one or more **expert positions**
(required roles). One **candidate** has one **CV**. A **match result** connects
one CV to one expert position within one TDR.

```
TDR ──< ExpertPosition ──< MatchResult >── CV ── Candidate
                                │
                                ├──< Anomaly
                                └──< Citation
```

## Pydantic models

```python
from pydantic import BaseModel, Field
from datetime import date
from enum import Enum
from typing import Optional


# ---------- CV side ----------

class Education(BaseModel):
    degree: str                 # e.g. "Master's in Computer Science"
    field: str
    institution: str
    country: Optional[str] = None
    graduation_year: Optional[int] = None
    source_span: str            # raw text this was extracted from, for citation

class Certification(BaseModel):
    name: str
    issuing_body: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    source_span: str

class Experience(BaseModel):
    title: str
    employer: str
    sector: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None   # None = current
    responsibilities: list[str] = Field(default_factory=list)
    source_span: str

class LanguageProficiency(BaseModel):
    language: str
    level: str                  # e.g. "native", "B2", "fluent" — normalize later

class NormalizedSkill(BaseModel):
    raw_term: str                # as it appeared in the CV
    canonical_id: Optional[str]  # taxonomy node id, None if unmatched
    confidence: float            # retrieval/rerank confidence, 0-1
    matched_via: str             # "direct" | "rag_retry" | "llm_fallback"

class CandidateCV(BaseModel):
    candidate_id: str
    full_name: str               # handle per data governance note in 01
    education: list[Education]
    certifications: list[Certification]
    experience: list[Experience]
    languages: list[LanguageProficiency]
    raw_skills: list[str]        # as extracted, pre-normalization
    normalized_skills: list[NormalizedSkill] = Field(default_factory=list)
    total_years_experience: float
    raw_text: str                 # full parsed document text, for citation grounding
    source_file_path: str


# ---------- TDR side ----------

class LanguageRequirement(BaseModel):
    language: str
    minimum_level: str

class ExpertPosition(BaseModel):
    position_id: str
    position_title: str          # e.g. "Team Leader", "QA Expert"
    mandatory_diploma: Optional[str] = None
    minimum_years_experience: Optional[float] = None
    required_certifications: list[str] = Field(default_factory=list)
    required_languages: list[LanguageRequirement] = Field(default_factory=list)
    required_sector_experience: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    evaluation_weight: Optional[float] = None  # if TDR specifies scoring weights
    source_span: str

class TDR(BaseModel):
    tdr_id: str
    mission_title: str
    client: Optional[str] = None
    sector: Optional[str] = None
    deadline: Optional[date] = None
    positions: list[ExpertPosition]
    raw_text: str
    source_file_path: str


# ---------- Matching / scoring ----------

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
    source_citation: str        # points back into raw_text

class Citation(BaseModel):
    claim: str                  # the claim being supported
    source_doc: str             # "cv" | "tdr"
    source_span: str

class SubScores(BaseModel):
    education_score: float
    experience_score: float
    certification_score: float
    sector_score: float
    language_score: float
    skill_score: float

class MatchResult(BaseModel):
    match_id: str
    cv_id: str
    tdr_id: str
    position_id: str
    hard_filter_passed: bool
    hard_filter_failures: list[str] = Field(default_factory=list)
    compatibility_score: Optional[float] = None   # None if hard filter failed
    sub_scores: Optional[SubScores] = None
    anomalies: list[Anomaly] = Field(default_factory=list)
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    reviewer_decision: Optional[str] = None   # "approved" | "rejected" | "overridden"
    reviewer_id: Optional[str] = None
    reviewer_note: Optional[str] = None
    decided_at: Optional[date] = None
```

## Postgres schema (sketch — refine as you build)

```sql
create extension if not exists vector;

create table candidates (
    candidate_id    uuid primary key default gen_random_uuid(),
    full_name       text not null,
    created_at      timestamptz default now()
);

create table cvs (
    cv_id                 uuid primary key default gen_random_uuid(),
    candidate_id          uuid references candidates(candidate_id),
    total_years_experience numeric,
    raw_text              text not null,
    source_file_path      text,
    extracted_json        jsonb not null,   -- full CandidateCV serialization
    created_at            timestamptz default now()
);

create table tdrs (
    tdr_id            uuid primary key default gen_random_uuid(),
    mission_title     text not null,
    client            text,
    sector            text,
    deadline          date,
    raw_text          text not null,
    source_file_path  text,
    extracted_json    jsonb not null,
    created_at        timestamptz default now()
);

create table expert_positions (
    position_id        uuid primary key default gen_random_uuid(),
    tdr_id             uuid references tdrs(tdr_id),
    position_title     text not null,
    requirements_json  jsonb not null   -- full ExpertPosition serialization
);

create table skill_taxonomy (
    skill_id     uuid primary key default gen_random_uuid(),
    canonical_name text not null,
    aliases      text[],
    embedding    vector(1536)   -- match your embedding model's dimension
);

create table match_results (
    match_id              uuid primary key default gen_random_uuid(),
    cv_id                 uuid references cvs(cv_id),
    tdr_id                uuid references tdrs(tdr_id),
    position_id           uuid references expert_positions(position_id),
    hard_filter_passed    boolean not null,
    compatibility_score   numeric,
    sub_scores_json        jsonb,
    rationale             text,
    citations_json         jsonb,
    reviewer_decision     text,
    reviewer_id           text,
    reviewer_note         text,
    decided_at            timestamptz,
    created_at            timestamptz default now()
);

create table anomalies (
    anomaly_id     uuid primary key default gen_random_uuid(),
    match_id       uuid references match_results(match_id),
    type           text not null,
    severity       text not null,
    description    text not null,
    source_citation text
);

-- Historical decisions: the memory store the scoring agent calibrates against.
-- Populate from real company data if/when they can share it (see 04-evaluation-metrics.md).
create table historical_decisions (
    decision_id    uuid primary key default gen_random_uuid(),
    tdr_id         uuid references tdrs(tdr_id),
    candidate_id   uuid references candidates(candidate_id),
    was_selected   boolean not null,
    outcome_note   text,
    decided_at     date
);

create index on skill_taxonomy using ivfflat (embedding vector_cosine_ops);
```

## Notes for implementation

- `total_years_experience` should be **computed at query time** from the
  `Experience` entries' start/end dates, not stored as a fixed extracted number.
  A CV extracted in January stays accurate in July as long as the underlying
  dates are correct — this is how the system handles "experience changes over
  time" without needing the company to periodically re-send resumes.
- CVs are refreshed through the dashboard's own CV-management page (HR uploads
  an update when something changes), not via a scheduled bulk re-request to the
  company — see `05-frontend-dashboard.md`.
- `source_span` / `source_citation` fields are not optional extras — they are what
  makes the final report explainable and what RAGAS-style faithfulness checks
  validate against. Every extraction, score, and anomaly must carry one.
- `hard_filter_passed = false` should mean `compatibility_score` is `null`, not
  zero — a rejected-on-hard-filter candidate never entered the scoring stage
  (this is the short-circuit optimization described in `01-architecture.md`).
- Keep `extracted_json` (full structured object) alongside normalized relational
  columns — you'll want the full object for report generation and for re-running
  eval without re-extracting.
