"""Backfill cvs.embedding for rows inserted before migration 0003.

CandidatesService.upload_cv computes the embedding at ingestion time going
forward -- this only covers CVs uploaded before that (e.g. the synthetic
CVs from earlier manual testing). Safe to re-run: only touches rows where
embedding is still null.

Run from backend/: uv run python scripts/backfill_cv_embeddings.py
"""

import asyncio

from sqlalchemy import select

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.models import CV
from app.database.session import async_session_factory
from app.domain.cv import CandidateCV
from app.features.candidates.service import _build_cv_embedding_text


async def backfill() -> None:
    embeddings = ModelRouter(get_settings()).get_embedding_model()

    async with async_session_factory() as session:
        rows = (
            (await session.execute(select(CV).where(CV.embedding.is_(None)))).scalars().all()
        )
        for row in rows:
            cv = CandidateCV.model_validate(row.extracted_json)
            row.embedding = embeddings.embed_query(_build_cv_embedding_text(cv))
            print(f"backfilled: {cv.full_name} ({row.cv_id})")

        await session.commit()

    print(f"done -- {len(rows)} cv embeddings backfilled")


if __name__ == "__main__":
    asyncio.run(backfill())
