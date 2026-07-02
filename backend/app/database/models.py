import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

# Fixed at migration time — matches the local Ollama nomic-embed-text model
# (see backend/.env.example EMBEDDING_DIMENSION). Changing embedding models
# to a different dimension requires a new migration, not a settings change.
EMBEDDING_DIMENSION = 768


class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class CV(Base):
    __tablename__ = "cvs"

    cv_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.candidate_id")
    )
    total_years_experience: Mapped[float | None] = mapped_column(Numeric)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_path: Mapped[str | None] = mapped_column(Text)
    extracted_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class TDR(Base):
    __tablename__ = "tdrs"

    tdr_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    mission_title: Mapped[str] = mapped_column(Text, nullable=False)
    client: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[date | None] = mapped_column(Date)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_path: Mapped[str | None] = mapped_column(Text)
    extracted_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ExpertPosition(Base):
    __tablename__ = "expert_positions"

    position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tdr_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tdrs.tdr_id"))
    position_title: Mapped[str] = mapped_column(Text, nullable=False)
    requirements_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class SkillTaxonomy(Base):
    __tablename__ = "skill_taxonomy"

    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION))


class MatchResult(Base):
    __tablename__ = "match_results"

    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cv_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cvs.cv_id"))
    tdr_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tdrs.tdr_id"))
    position_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expert_positions.position_id")
    )
    hard_filter_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    compatibility_score: Mapped[float | None] = mapped_column(Numeric)
    sub_scores_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    rationale: Mapped[str | None] = mapped_column(Text)
    citations_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reviewer_decision: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[str | None] = mapped_column(Text)
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Anomaly(Base):
    __tablename__ = "anomalies"

    anomaly_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("match_results.match_id")
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_citation: Mapped[str | None] = mapped_column(Text)


class HistoricalDecision(Base):
    """The memory store the scoring agent calibrates against."""

    __tablename__ = "historical_decisions"

    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tdr_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tdrs.tdr_id"))
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.candidate_id")
    )
    was_selected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    outcome_note: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[date | None] = mapped_column(Date)
