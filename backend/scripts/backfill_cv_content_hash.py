"""Backfill cvs.content_hash for rows inserted before migration 0006.

CandidatesService.upload_cv computes content_hash from the uploaded file
bytes at ingestion time going forward -- this only covers CVs uploaded
before migration 0006 added the column (e.g. the synthetic CVs from
earlier manual testing). Those rows have content_hash=NULL, which the
unique index treats as "never collides with anything" (see migration
0006's docstring) -- so upload_cv's dedup lookup silently misses them and
re-uploading the exact same file creates a brand-new duplicate
Candidate/CV pair instead of reusing/updating the existing one (observed
live: re-uploading docs/cvs/synthetic/nadia-ben-salah.pdf against the
pre-migration row created a second "Nadia Ben Salah" candidate).

Matches by source_file_path against docs/cvs/synthetic/ -- deterministic,
no LLM calls, no file re-upload (re-uploading would itself hit the same
gap this script fixes).

Matching surfaced the same wrinkle as the TDR backfill (see
backfill_tdr_content_hash.py): several fixtures were re-uploaded multiple
times *before* migration 0006 -- i.e. the exact bug this backfill closes,
already having happened historically -- so multiple existing cvs rows can
share the same source_file_path, each with its own match_results already
hanging off it. content_hash is unique-indexed, so only one of those rows
can hold the real hash; the rest are pre-existing legitimate duplicate
data with live downstream references, and merging/deleting them is a
data-migration decision well outside a backfill script's scope. For each
fixture match, this script picks exactly one canonical row -- ranked by
how many match_results reference it (the only FK pointing at cvs.cv_id --
see app/database/models.py), then by most recently created -- on the
theory that the row with the most real usage is the one future
re-uploads of that file should keep resolving to -- and assigns the real
hash only to that row. The other rows in the group are left
content_hash=NULL permanently (they still work today; they just won't be
the target of future re-upload dedup lookups, which already can't tell
them apart from each other today either).

Safe to re-run: only ever reads/patches rows whose content_hash is still
null, and skips any row whose source_file_path doesn't match a fixture
still on disk (a real, non-fixture CV -- nothing to backfill from, not an
error).

Run from backend/: uv run python scripts/backfill_cv_content_hash.py
"""

import asyncio
import hashlib
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CV, MatchResult
from app.database.session import async_session_factory

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "docs" / "cvs" / "synthetic"


async def _downstream_reference_count(session: AsyncSession, cv_id: UUID) -> int:
    """match_results count referencing cv_id.

    Used to rank duplicate rows matching the same fixture -- the row with
    the most real usage is kept as canonical (see module docstring).
    """
    return (
        await session.execute(select(func.count()).where(MatchResult.cv_id == cv_id))
    ).scalar_one()


async def backfill() -> None:
    async with async_session_factory() as session:
        rows = (await session.execute(select(CV).where(CV.content_hash.is_(None)))).scalars().all()

        # Group NULL rows by which fixture their source_file_path matches.
        groups: dict[str, list[CV]] = {}
        for row in rows:
            if not row.source_file_path:
                continue
            fixture_path = _FIXTURES_DIR / row.source_file_path
            if not fixture_path.is_file():
                continue
            groups.setdefault(row.source_file_path, []).append(row)

        patched = 0
        for fixture_name, group_rows in groups.items():
            fixture_path = _FIXTURES_DIR / fixture_name
            content_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()

            # A row already carrying this exact hash means the file was
            # already re-uploaded post-migration and correctly deduped --
            # nothing to backfill, and assigning the hash to a legacy NULL
            # row here would violate the unique index.
            already_hashed = (
                await session.execute(select(CV).where(CV.content_hash == content_hash))
            ).scalar_one_or_none()
            if already_hashed is not None:
                print(
                    f"fixture {fixture_name}: content_hash already set on "
                    f"{already_hashed.cv_id} (a post-migration upload) -- leaving the "
                    f"{len(group_rows)} legacy row(s) {[row.cv_id for row in group_rows]} "
                    "content_hash=NULL"
                )
                continue

            canonical = group_rows[0]
            if len(group_rows) > 1:
                ranked = [
                    (await _downstream_reference_count(session, row.cv_id), row.created_at, row)
                    for row in group_rows
                ]
                ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
                canonical = ranked[0][2]
                skipped_ids = [row.cv_id for row in group_rows if row.cv_id != canonical.cv_id]
                print(
                    f"fixture {fixture_name}: {len(group_rows)} pre-existing duplicate rows "
                    f"found -- keeping content_hash on {canonical.cv_id} (most downstream "
                    f"references), leaving {skipped_ids} content_hash=NULL"
                )

            canonical.content_hash = content_hash
            patched += 1
            print(f"backfilled: {fixture_name} ({canonical.cv_id})")

        await session.commit()

    print(f"done -- {patched} cv content_hash values backfilled")


if __name__ == "__main__":
    asyncio.run(backfill())
