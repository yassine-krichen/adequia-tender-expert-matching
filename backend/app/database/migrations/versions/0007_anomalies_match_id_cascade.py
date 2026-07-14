"""anomalies.match_id FK cascades on delete

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-14

ADQ-20 starts writing to `anomalies` for real, and `matching_tasks.py`
re-runs on the same TDR follow a delete-then-insert pattern for
`match_results` -- without ON DELETE CASCADE here, deleting a
match_results row with existing anomaly rows throws a FK violation on
the very first re-run.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_NAME = "anomalies_match_id_fkey"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, "anomalies", type_="foreignkey")
    op.create_foreign_key(
        _CONSTRAINT_NAME,
        "anomalies",
        "match_results",
        ["match_id"],
        ["match_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, "anomalies", type_="foreignkey")
    op.create_foreign_key(
        _CONSTRAINT_NAME,
        "anomalies",
        "match_results",
        ["match_id"],
        ["match_id"],
    )
