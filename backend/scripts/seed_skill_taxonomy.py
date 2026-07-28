"""Seed `skill_taxonomy` from app/features/pipeline/seed_data/skill_taxonomy.json.

Embeds each canonical_name via the configured embedding model and upserts
(delete + reinsert, keyed on canonical_name) -- safe to re-run as the
taxonomy grows, not a one-time migration. See docs/scrum/sprint-2-plan.md
ADQ-10.

This JSON file is the bootstrap source for the original seed entries only.
Skill candidates approved later via POST /admin/skill-candidates/{id}/approve
(app/features/taxonomy_admin/service.py) insert straight into the
skill_taxonomy table without ever touching this file -- the DB and this
file are allowed to diverge over time; don't expect this file to be a
complete mirror of the live taxonomy.

Run from backend/: uv run python scripts/seed_skill_taxonomy.py
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import delete

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.models import SkillTaxonomy
from app.database.session import async_session_factory

_SEED_FILE = (
    Path(__file__).resolve().parent.parent
    / "app"
    / "features"
    / "pipeline"
    / "seed_data"
    / "skill_taxonomy.json"
)


async def seed() -> None:
    entries = json.loads(_SEED_FILE.read_text(encoding="utf-8"))
    embeddings = ModelRouter(get_settings()).get_embedding_model()

    async with async_session_factory() as session:
        for entry in entries:
            canonical_name = entry["canonical_name"]
            aliases = entry.get("aliases", [])
            vector = embeddings.embed_query(canonical_name)

            await session.execute(
                delete(SkillTaxonomy).where(SkillTaxonomy.canonical_name == canonical_name)
            )
            session.add(
                SkillTaxonomy(canonical_name=canonical_name, aliases=aliases, embedding=vector)
            )
            print(f"seeded: {canonical_name}")

        await session.commit()

    print(f"done -- {len(entries)} taxonomy entries seeded")


if __name__ == "__main__":
    asyncio.run(seed())
