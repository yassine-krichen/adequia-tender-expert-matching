"""One-off setup for the LangGraph Postgres checkpointer.

AsyncPostgresSaver.setup() creates the checkpoints/checkpoint_blobs/
checkpoint_writes tables -- these are LangGraph-internal and intentionally
NOT Alembic-managed (Sprint 3 decision 1). Runs as its own one-shot
docker-compose step (mirrors the existing `migrate` service), since these
tables are unrelated to the Alembic-managed schema and conflating the two
would make `migrate` responsible for two different migration systems.

Idempotent -- safe to re-run (AsyncPostgresSaver.setup() only creates
tables/indexes if they don't already exist).

Run from backend/: uv run python -m app.mcp.setup_checkpointer
"""

import asyncio
import sys

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config.settings import get_settings

if sys.platform == "win32":
    # psycopg's async mode can't run on Windows' default ProactorEventLoop
    # (confirmed: raises psycopg.InterfaceError). Only affects local `uv
    # run` on Windows dev machines -- the Linux container uses the default
    # selector-based loop already.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _to_psycopg_conninfo(database_url: str) -> str:
    """AsyncPostgresSaver uses psycopg (v3), not asyncpg -- the app's
    DATABASE_URL is an asyncpg SQLAlchemy URL (`postgresql+asyncpg://...`).
    psycopg accepts a plain `postgresql://` conninfo string.
    """
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def setup() -> None:
    conninfo = _to_psycopg_conninfo(get_settings().database_url)

    async with AsyncPostgresSaver.from_conn_string(conninfo) as checkpointer:
        await checkpointer.setup()

    print("done -- checkpointer tables ready")


if __name__ == "__main__":
    asyncio.run(setup())
