"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-06

Full schema per docs/02-data-schemas.md: candidates, cvs, tdrs,
expert_positions, skill_taxonomy, match_results, anomalies,
historical_decisions, plus the pgvector extension and the ivfflat index
used for coarse skill-taxonomy retrieval.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIMENSION = 768


def upgrade() -> None:
    op.execute("create extension if not exists vector")

    op.create_table(
        "candidates",
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "cvs",
        sa.Column(
            "cv_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.candidate_id"),
        ),
        sa.Column("total_years_experience", sa.Numeric()),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source_file_path", sa.Text()),
        sa.Column("extracted_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "tdrs",
        sa.Column(
            "tdr_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("mission_title", sa.Text(), nullable=False),
        sa.Column("client", sa.Text()),
        sa.Column("sector", sa.Text()),
        sa.Column("deadline", sa.Date()),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source_file_path", sa.Text()),
        sa.Column("extracted_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "expert_positions",
        sa.Column(
            "position_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("tdr_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tdrs.tdr_id")),
        sa.Column("position_title", sa.Text(), nullable=False),
        sa.Column("requirements_json", postgresql.JSONB(), nullable=False),
    )

    op.create_table(
        "skill_taxonomy",
        sa.Column(
            "skill_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.Text())),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION)),
    )
    op.execute(
        "create index skill_taxonomy_embedding_ivfflat "
        "on skill_taxonomy using ivfflat (embedding vector_cosine_ops)"
    )

    op.create_table(
        "match_results",
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("cv_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cvs.cv_id")),
        sa.Column("tdr_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tdrs.tdr_id")),
        sa.Column(
            "position_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expert_positions.position_id"),
        ),
        sa.Column("hard_filter_passed", sa.Boolean(), nullable=False),
        sa.Column("compatibility_score", sa.Numeric()),
        sa.Column("sub_scores_json", postgresql.JSONB()),
        sa.Column("rationale", sa.Text()),
        sa.Column("citations_json", postgresql.JSONB()),
        sa.Column("reviewer_decision", sa.Text()),
        sa.Column("reviewer_id", sa.Text()),
        sa.Column("reviewer_note", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "anomalies",
        sa.Column(
            "anomaly_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "match_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("match_results.match_id")
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_citation", sa.Text()),
    )

    op.create_table(
        "historical_decisions",
        sa.Column(
            "decision_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("tdr_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tdrs.tdr_id")),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.candidate_id"),
        ),
        sa.Column("was_selected", sa.Boolean(), nullable=False),
        sa.Column("outcome_note", sa.Text()),
        sa.Column("decided_at", sa.Date()),
    )


def downgrade() -> None:
    op.drop_table("historical_decisions")
    op.drop_table("anomalies")
    op.drop_table("match_results")
    op.execute("drop index if exists skill_taxonomy_embedding_ivfflat")
    op.drop_table("skill_taxonomy")
    op.drop_table("expert_positions")
    op.drop_table("tdrs")
    op.drop_table("cvs")
    op.drop_table("candidates")
    op.execute("drop extension if exists vector")
