"""AdéquIA MCP server -- two tools consumed as direct client calls from
matching-pipeline node code (Sprint 3 decision 2, not an LLM tool-calling
loop). Runs as its own long-lived process (see docker-compose.yml's `mcp`
service), so it manages its own DB sessions the same way the standalone
backfill scripts do (app/database/session.py's async_session_factory),
not via FastAPI's request-scoped dependency.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import select

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.models import HistoricalDecision, TDR
from app.database.session import async_session_factory
from app.features.pipeline.nodes.normalize_skills import (
    _rerank_taxonomy_candidates,
    _retrieve_top_k_taxonomy,
)

mcp = FastMCP(
    "adequia",
    host="0.0.0.0",
    port=8100,
    # FastMCP's DNS-rebinding protection validates the Host/Origin headers
    # against an allowlist. Its own default (host="127.0.0.1") only
    # allowlists localhost, which rejects every real request here --
    # api/worker reach this server over the docker-compose network as
    # `http://mcp:8100`, not localhost. Keep protection enabled, just
    # extend the allowlist to the one hostname this server is actually
    # reachable at.
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["mcp:8100", "127.0.0.1:*", "localhost:*"],
        allowed_origins=["http://mcp:8100", "http://127.0.0.1:*", "http://localhost:*"],
    ),
)


@mcp.tool()
async def lookup_skill_taxonomy(term: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Look up the closest skill_taxonomy entries for a free-text term.

    Thin wrapper around normalize_skills.py's existing, tested retrieval +
    rerank -- reuses the same embedding/rerank logic the matching pipeline
    already relies on, not a reimplementation.
    """
    embeddings = ModelRouter(get_settings()).get_embedding_model()

    async with async_session_factory() as session:
        candidates = await _retrieve_top_k_taxonomy(
            term, session=session, embeddings=embeddings, k=top_k
        )

    ranked = _rerank_taxonomy_candidates(term, candidates)
    return [
        {
            "skill_id": str(taxonomy_row.skill_id),
            "canonical_name": taxonomy_row.canonical_name,
            "aliases": taxonomy_row.aliases or [],
            "similarity": similarity,
        }
        for taxonomy_row, similarity in ranked
    ]


@mcp.tool()
async def lookup_historical_decisions(
    sector: str, position_title: str | None = None
) -> list[dict[str, Any]]:
    """Look up past reviewer decisions for TDRs in the same sector.

    Joins historical_decisions -> tdrs on shared `sector` -- the only
    feasible signal given the current schema has no position-level or
    embedding-indexed granularity (Sprint 3 decision 2). `position_title`
    is accepted for future narrowing but unused today -- the table has no
    position-level column to filter on yet. Returns an empty list when
    there's no history, which is the common case right now since nothing
    writes to this table yet.
    """
    async with async_session_factory() as session:
        stmt = (
            select(HistoricalDecision, TDR)
            .join(TDR, HistoricalDecision.tdr_id == TDR.tdr_id)
            .where(TDR.sector == sector)
        )
        rows = (await session.execute(stmt)).all()

    return [
        {
            "tdr_id": str(tdr.tdr_id),
            "was_selected": decision.was_selected,
            "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
            "outcome_note": decision.outcome_note,
        }
        for decision, tdr in rows
    ]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
