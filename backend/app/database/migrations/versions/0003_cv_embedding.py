"""cv coarse-retrieval embedding

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-13

ADQ-11 coarse retrieval needs a per-CV embedding to compare against each
TDR position's requirement embedding -- see docs/01-architecture.md
"Two-phase matching". Computed once at CV ingestion time
(CandidatesService.upload_cv), never recomputed per TDR. Existing rows
need backend/scripts/backfill_cv_embeddings.py after this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIMENSION = 768


def upgrade() -> None:
    op.add_column("cvs", sa.Column("embedding", Vector(EMBEDDING_DIMENSION)))
    op.execute(
        "create index cvs_embedding_ivfflat on cvs using ivfflat (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("drop index if exists cvs_embedding_ivfflat")
    op.drop_column("cvs", "embedding")
