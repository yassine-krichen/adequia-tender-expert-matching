"""Backfill cvs.extracted_json["birth_date"] for rows uploaded before the
birth_date field existed on CandidateCV.

Matches by full_name against generate_synthetic_cvs.py's own CANDIDATES data
-- deterministic, no LLM calls, no file re-upload (re-uploading would create
a duplicate row via upload_cv's sha256 dedup, see
app/features/candidates/service.py). Safe to re-run: only patches rows whose
extracted_json still lacks a birth_date, and skips any row whose full_name
isn't a known fixture candidate (a real, non-fixture CV -- nothing to
backfill from, not an error).

Run from backend/: uv run python scripts/backfill_cv_birth_dates.py
"""

import asyncio

from sqlalchemy import select

from app.database.models import CV
from app.database.session import async_session_factory
from scripts.generate_synthetic_cvs import CANDIDATES


async def backfill() -> None:
    by_name = {candidate.full_name: candidate for candidate in CANDIDATES}

    async with async_session_factory() as session:
        rows = (await session.execute(select(CV))).scalars().all()
        patched = 0
        for row in rows:
            if row.extracted_json.get("birth_date"):
                continue
            full_name: str | None = row.extracted_json.get("full_name")
            candidate = by_name.get(full_name) if full_name is not None else None
            if candidate is None:
                continue

            # CV.extracted_json has no MutableDict wrapper (database/models.py)
            # -- an in-place row.extracted_json["birth_date"] = ... would not
            # mark the row dirty and commit() would silently no-op. Reassign
            # the whole dict instead.
            row.extracted_json = {
                **row.extracted_json,
                "birth_date": candidate.birth_date.isoformat(),
            }
            patched += 1
            print(f"backfilled: {candidate.full_name} ({row.cv_id})")

        await session.commit()

    print(f"done -- {patched} candidates patched")


if __name__ == "__main__":
    asyncio.run(backfill())
