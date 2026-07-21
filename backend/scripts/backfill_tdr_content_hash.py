"""Backfill tdrs.content_hash for rows inserted before migration 0006.

TdrsService.upload_tdr computes content_hash from the uploaded file bytes
at ingestion time going forward -- this only covers TDRs uploaded before
migration 0006 added the column. Those rows have content_hash=NULL, which
the unique index treats as "never collides with anything" (see migration
0006's docstring) -- so upload_tdr's dedup lookup silently misses them and
re-uploading the exact same file creates a brand-new duplicate TDR row
instead of reusing/reprocessing the existing one (same bug class fixed for
cvs.content_hash -- see backfill_cv_content_hash.py).

Unlike the CV backfill, matching cannot rely on source_file_path: the
legacy TDR rows were uploaded through the browser with generic/renamed
filenames (e.g. "TDR (8).pdf", "DP _  Developpement de Applicatif avec 4
modules-revu TAM-ST2I (5).docx") that don't correspond to any fixture
basename in docs/tdrs/. Instead this matches each NULL row to a fixture by
*content*: it re-runs the same extract_raw_text parsing upload_tdr uses
(app/features/pipeline/nodes/ingest.py) against every file in docs/tdrs/
and compares the result to the row's stored raw_text. A row whose raw_text
doesn't exactly match any fixture's extracted text (e.g. status="failed",
where raw_text was never even set) is left alone -- nothing to backfill
from, not an error.

Content matching surfaced a real wrinkle: several fixtures were re-uploaded
multiple times *before* migration 0006 (i.e. the exact bug this backfill
closes, already having happened historically) -- multiple existing tdrs
rows share identical raw_text, each with its own expert_positions /
match_results / historical_decisions already hanging off it. content_hash
is unique-indexed, so only one of those rows can hold the real hash; the
rest are pre-existing legitimate duplicate data with live downstream
references, and merging/deleting them is a data-migration decision well
outside a backfill script's scope. For each content match, this script
picks exactly one canonical row -- ranked by how much downstream data
references it (historical_decisions, then match_results, then
expert_positions counts, then most recently created), on the theory that
the row with the most real usage is the one future re-uploads of that file
should keep resolving to -- and assigns the real hash only to that row.
The other rows in the group are left content_hash=NULL permanently (they
still work today; they just won't be the target of future re-upload dedup
lookups, which already can't tell them apart from each other today
either).

Safe to re-run: only ever reads/patches rows whose content_hash is still
null.

Run from backend/: uv run python scripts/backfill_tdr_content_hash.py
"""

import asyncio
import hashlib
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import TDR, ExpertPosition, HistoricalDecision, MatchResult
from app.database.session import async_session_factory
from app.features.pipeline.nodes.ingest import extract_raw_text

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "docs" / "tdrs"


def _load_fixture_texts() -> dict[str, str]:
    """Maps fixture filename -> its extract_raw_text() output.

    Fixtures that fail to parse (e.g. a scanned/image-only PDF with no
    extractable text layer) are skipped -- there's nothing for a NULL row's
    raw_text to ever match against them anyway.
    """
    texts: dict[str, str] = {}
    for path in _FIXTURES_DIR.iterdir():
        if not path.is_file():
            continue
        try:
            texts[path.name] = extract_raw_text(path.read_bytes(), path.name)
        except Exception as exc:  # noqa: BLE001 - best-effort fixture parsing
            print(f"skipping fixture {path.name}: {exc}")
    return texts


async def _downstream_reference_counts(
    session: AsyncSession, tdr_id: UUID
) -> tuple[int, int, int]:
    """(historical_decisions, match_results, expert_positions) counts for tdr_id.

    Used to rank duplicate rows matching the same fixture -- the row with
    the most real usage is the one kept as canonical (see module docstring).
    """
    hist_count = (
        await session.execute(
            select(func.count()).where(HistoricalDecision.tdr_id == tdr_id)
        )
    ).scalar_one()
    match_count = (
        await session.execute(select(func.count()).where(MatchResult.tdr_id == tdr_id))
    ).scalar_one()
    position_count = (
        await session.execute(select(func.count()).where(ExpertPosition.tdr_id == tdr_id))
    ).scalar_one()
    return (hist_count, match_count, position_count)


async def backfill() -> None:
    fixture_texts = _load_fixture_texts()

    async with async_session_factory() as session:
        rows = (
            (await session.execute(select(TDR).where(TDR.content_hash.is_(None))))
            .scalars()
            .all()
        )

        # Group NULL rows by which fixture their raw_text matches.
        groups: dict[str, list[TDR]] = {}
        for row in rows:
            if not row.raw_text:
                continue
            for fixture_name, fixture_text in fixture_texts.items():
                if fixture_text.strip() == row.raw_text.strip():
                    groups.setdefault(fixture_name, []).append(row)
                    break

        patched = 0
        for fixture_name, group_rows in groups.items():
            fixture_path = _FIXTURES_DIR / fixture_name
            content_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()

            # A row already carrying this exact hash means the file was
            # already re-uploaded post-migration and correctly deduped --
            # nothing to backfill, and assigning the hash to a legacy NULL
            # row here would violate the unique index.
            already_hashed = (
                await session.execute(select(TDR).where(TDR.content_hash == content_hash))
            ).scalar_one_or_none()
            if already_hashed is not None:
                print(
                    f"fixture {fixture_name}: content_hash already set on "
                    f"{already_hashed.tdr_id} (a post-migration upload) -- leaving the "
                    f"{len(group_rows)} legacy row(s) {[row.tdr_id for row in group_rows]} "
                    "content_hash=NULL"
                )
                continue

            canonical = group_rows[0]
            if len(group_rows) > 1:
                ranked = [
                    (await _downstream_reference_counts(session, row.tdr_id), row.created_at, row)
                    for row in group_rows
                ]
                ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
                canonical = ranked[0][2]
                skipped_ids = [row.tdr_id for row in group_rows if row.tdr_id != canonical.tdr_id]
                print(
                    f"fixture {fixture_name}: {len(group_rows)} pre-existing duplicate rows "
                    f"found -- keeping content_hash on {canonical.tdr_id} (most downstream "
                    f"references), leaving {skipped_ids} content_hash=NULL"
                )

            canonical.content_hash = content_hash
            patched += 1
            print(f"backfilled: {fixture_name} ({canonical.tdr_id})")

        await session.commit()

    print(f"done -- {patched} tdr content_hash values backfilled")


if __name__ == "__main__":
    asyncio.run(backfill())
