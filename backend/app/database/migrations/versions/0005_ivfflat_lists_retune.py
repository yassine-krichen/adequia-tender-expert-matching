"""retune ivfflat lists for actual data scale

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13

Both cvs.embedding and skill_taxonomy.embedding indexes were created with
pgvector's ivfflat default (lists=100). At this project's actual scale
(dozens of CVs, ~70 taxonomy terms), that's not just an over-tuning nit --
ivfflat probes only 1 list per query by default (ivfflat.probes=1), so
with far more lists than rows, most lists end up empty or holding a
single row. A true nearest neighbor can land in a list that never gets
probed, silently degrading retrieval quality with no error. lists=10 is
a reasonable floor for this scale; re-tune again in a future migration if
either table grows into the thousands of rows.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_LISTS = 10


def upgrade() -> None:
    op.execute("drop index if exists cvs_embedding_ivfflat")
    op.execute(
        f"create index cvs_embedding_ivfflat on cvs "
        f"using ivfflat (embedding vector_cosine_ops) with (lists = {_NEW_LISTS})"
    )
    op.execute("drop index if exists skill_taxonomy_embedding_ivfflat")
    op.execute(
        f"create index skill_taxonomy_embedding_ivfflat on skill_taxonomy "
        f"using ivfflat (embedding vector_cosine_ops) with (lists = {_NEW_LISTS})"
    )


def downgrade() -> None:
    op.execute("drop index if exists cvs_embedding_ivfflat")
    op.execute("create index cvs_embedding_ivfflat on cvs using ivfflat (embedding vector_cosine_ops)")
    op.execute("drop index if exists skill_taxonomy_embedding_ivfflat")
    op.execute(
        "create index skill_taxonomy_embedding_ivfflat on skill_taxonomy "
        "using ivfflat (embedding vector_cosine_ops)"
    )
