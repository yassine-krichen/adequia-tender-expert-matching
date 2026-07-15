"""Shared conninfo conversion for the LangGraph Postgres checkpointer --
used by both the one-shot setup script and the worker's per-run checkpointer
context (app/worker/matching_tasks.py).
"""


def get_checkpointer_conninfo(database_url: str) -> str:
    """AsyncPostgresSaver uses psycopg (v3), not asyncpg -- the app's
    DATABASE_URL is an asyncpg SQLAlchemy URL (`postgresql+asyncpg://...`).
    psycopg accepts a plain `postgresql://` conninfo string.
    """
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
