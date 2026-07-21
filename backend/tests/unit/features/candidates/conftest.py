"""Real (SQLite in-memory) AsyncSession fixture, scoped to candidates/ only.

The suite-wide convention elsewhere is `_FakeSession`, a hand-rolled stub
that ignores query predicates entirely (see test_service.py's _FakeSession
docstring). That's fine for tests asserting "some CV row was found", but
it can't prove a `WHERE content_hash == ...` lookup actually filters on
the hash -- a broken query that returns "any CV row" would pass just as
well. The dedup regression tests in this directory need a real predicate
evaluation, so this fixture spins up an actual AsyncSession against an
in-memory SQLite database, with the real Candidate/CV table schemas.

This is deliberately narrow: only candidates/ uses it. Every other
feature's tests keep using _FakeSession, unchanged.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.models import CV, Candidate

# JSONB (extracted_json) has no SQLite equivalent -- render it as SQLite's
# native JSON type instead. Postgres in production is unaffected: this
# compiler hook only fires for the "sqlite" dialect.
@compiles(JSONB, "sqlite")
def _compile_jsonb_as_json(element: object, compiler: object, **kw: object) -> str:
    return "JSON"


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A real AsyncSession backed by a fresh in-memory SQLite database,
    with the actual Candidate/CV table schemas created against it.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # candidates.candidate_id/cvs.cv_id use server_default=text("gen_random_uuid()")
    # and created_at uses server_default=text("now()") -- both Postgres
    # functions with no SQLite builtin. Register them as real SQLite
    # functions on connect so inserts that rely on the server default
    # (e.g. CandidatesService never sets CV.cv_id) still work.
    @event.listens_for(engine.sync_engine, "connect")
    def _register_postgres_compat_functions(dbapi_connection: object, _record: object) -> None:
        # SQLAlchemy's postgresql.UUID(as_uuid=True) falls back to a plain
        # 32-char hex string (no dashes) on non-native dialects like
        # SQLite -- match that format here, or a value inserted via this
        # server-side default won't compare equal to the same value bound
        # from Python later (e.g. in an UPDATE ... WHERE cv_id = :cv_id).
        dbapi_connection.create_function(  # type: ignore[attr-defined]
            "gen_random_uuid", 0, lambda: uuid.uuid4().hex
        )
        dbapi_connection.create_function(  # type: ignore[attr-defined]
            "now", 0, lambda: datetime.now(timezone.utc).isoformat()
        )

    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[Candidate.__table__, CV.__table__],  # type: ignore[list-item]
        )

    async with AsyncSession(engine) as session:
        yield session

    await engine.dispose()
