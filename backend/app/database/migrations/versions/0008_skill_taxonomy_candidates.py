"""skill_taxonomy_candidates -- harvested unmatched skill terms

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-28

normalize_skills.py's match_skill_to_taxonomy leaves canonical_id unset for
any term the retrieval/rerank/retry pipeline never confidently resolves --
that's a real gap-in-the-taxonomy signal, previously discarded entirely.
This table lets a matching run harvest those unmatched terms (best-effort,
never load-bearing for the run itself -- see
record_unmatched_skill_candidates), for human review via the new
/admin/skill-candidates API (app/features/taxonomy_admin/).

normalized_term is the dedup key (lowercased/stripped raw_term) --
occurrence_count increments on repeat sightings instead of duplicating a
row, so the review queue naturally surfaces the most-repeated (highest
signal) unmatched terms first.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_taxonomy_candidates",
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("raw_term", sa.Text(), nullable=False),
        sa.Column("normalized_term", sa.Text(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("best_similarity", sa.Numeric()),
        # "pending" | "approved" | "rejected" | "merged" -- see
        # app/features/taxonomy_admin/service.py.
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("suggested_canonical_name", sa.Text()),
        sa.Column("suggested_aliases", postgresql.ARRAY(sa.Text())),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewer_note", sa.Text()),
    )
    op.create_index(
        "skill_taxonomy_candidates_normalized_term_idx",
        "skill_taxonomy_candidates",
        ["normalized_term"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "skill_taxonomy_candidates_normalized_term_idx", table_name="skill_taxonomy_candidates"
    )
    op.drop_table("skill_taxonomy_candidates")
