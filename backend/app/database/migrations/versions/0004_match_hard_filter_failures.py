"""match_results hard filter failure reasons

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-13

ADQ-17's matching results page needs to show *why* a candidate failed a
hard filter (docs/05-frontend-dashboard.md: "Hard filter status (pass/fail,
with reason if failed)") -- match_results had nowhere to persist
score.check_hard_filters' human-readable failure list.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("match_results", sa.Column("hard_filter_failures_json", postgresql.JSONB()))


def downgrade() -> None:
    op.drop_column("match_results", "hard_filter_failures_json")
