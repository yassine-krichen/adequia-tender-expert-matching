"""tdr status tracking

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-06

POST /tdrs moves to async processing (RQ worker) so a slow multi-section
extraction no longer blocks the request -- see docs/01-architecture.md
"TDR upload: async processing". The row is created immediately with
status="processing" and no extracted fields yet, so mission_title/raw_text/
extracted_json must become nullable; they're only known once the worker
finishes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tdrs", sa.Column("status", sa.Text(), nullable=False, server_default="done"))
    op.add_column("tdrs", sa.Column("error_message", sa.Text()))
    op.alter_column("tdrs", "mission_title", nullable=True)
    op.alter_column("tdrs", "raw_text", nullable=True)
    op.alter_column("tdrs", "extracted_json", nullable=True)


def downgrade() -> None:
    # Backfill first -- any row still status="processing" (or "failed")
    # has NULLs in these columns, which the alter_column calls below would
    # otherwise fail against on real data.
    op.execute(
        "update tdrs set "
        "mission_title = coalesce(mission_title, ''), "
        "raw_text = coalesce(raw_text, ''), "
        "extracted_json = coalesce(extracted_json, '{}'::jsonb) "
        "where mission_title is null or raw_text is null or extracted_json is null"
    )
    op.alter_column("tdrs", "extracted_json", nullable=False)
    op.alter_column("tdrs", "raw_text", nullable=False)
    op.alter_column("tdrs", "mission_title", nullable=False)
    op.drop_column("tdrs", "error_message")
    op.drop_column("tdrs", "status")
