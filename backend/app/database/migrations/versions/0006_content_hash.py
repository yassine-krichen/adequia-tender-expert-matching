"""content_hash on cvs and tdrs for upload dedup

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-13

Every CV/TDR upload always created a new row -- for TDRs, always re-ran
the full LLM extraction pipeline too -- with no way to recognize "this
exact file was already uploaded." Nullable because existing rows have no
stored file bytes to hash retroactively; a unique index on a nullable
column is safe in Postgres since every NULL is treated as distinct, so
old rows with no hash simply never collide with anything.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cvs", sa.Column("content_hash", sa.Text(), nullable=True))
    op.create_index("cvs_content_hash_idx", "cvs", ["content_hash"], unique=True)
    op.add_column("tdrs", sa.Column("content_hash", sa.Text(), nullable=True))
    op.create_index("tdrs_content_hash_idx", "tdrs", ["content_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("tdrs_content_hash_idx", table_name="tdrs")
    op.drop_column("tdrs", "content_hash")
    op.drop_index("cvs_content_hash_idx", table_name="cvs")
    op.drop_column("cvs", "content_hash")
