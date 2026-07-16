import asyncio
import logging
import sys
from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

from langchain_core.embeddings import Embeddings
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from redis import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.llm.router import ExtractionRouter, ModelRouter
from app.config.settings import get_settings
from app.database.models import TDR as TDRModel
from app.database.models import Anomaly as AnomalyModel
from app.database.models import ExpertPosition as ExpertPositionModel
from app.database.models import MatchResult as MatchResultModel
from app.database.session import async_session_factory
from app.domain.cv import CandidateCV
from app.domain.tdr import ExpertPosition
from app.features.matching.coarse_retrieval import shortlist_candidates
from app.features.pipeline.graph import build_matching_graph
from app.features.pipeline.nodes.normalize_skills import normalize_position_skills
from app.features.pipeline.state import PipelineState
from app.mcp.checkpointer import get_checkpointer_conninfo
from app.mcp.client import get_mcp_client

if sys.platform == "win32":
    # psycopg's async mode can't run on Windows' default ProactorEventLoop
    # (confirmed: raises psycopg.InterfaceError). Only affects local `uv
    # run` on Windows dev machines -- the Linux worker container uses the
    # default selector-based loop already.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = logging.getLogger(__name__)

# Only needed for the lifetime of one matching run -- same TTL rationale as
# app/worker/tasks.py's extraction progress key.
_PROGRESS_TTL_SECONDS = 3600

MatchingProgressCallback = Callable[[str, int, int], None]


def matching_progress_key(tdr_id: str) -> str:
    return f"tdr:{tdr_id}:matching_progress"


def make_redis_matching_progress_reporter(
    redis_client: Redis, tdr_id: str
) -> MatchingProgressCallback:
    def report(status: str, positions_done: int, positions_total: int) -> None:
        redis_client.hset(
            matching_progress_key(tdr_id),
            mapping={"status": status, "positions_done": positions_done, "positions_total": positions_total},
        )
        redis_client.expire(matching_progress_key(tdr_id), _PROGRESS_TTL_SECONDS)

    return report


async def run_matching_job(
    tdr_id: str,
    *,
    session: AsyncSession,
    router: ExtractionRouter,
    mcp_client: MultiServerMCPClient,
    checkpointer: AsyncPostgresSaver,
    embeddings: Embeddings,
    on_progress: MatchingProgressCallback,
) -> None:
    """Runs coarse retrieval for every position on this TDR, then the
    compiled matching graph (normalize_skills -> score -> detect_anomalies
    -> generate_report) for every shortlisted candidate. The TDR row and
    its positions already exist (extraction already ran) -- this only ever
    inserts/replaces match_results/anomalies rows, never touches the TDR
    itself.

    Re-run safe: existing match_results for a position are deleted before
    that position's fresh matches are inserted (no unique constraint to
    upsert against, same delete-then-insert idempotency as the taxonomy
    seed script). anomalies rows cascade-delete alongside their match_result
    (migration 0007), no separate delete needed here.
    """
    tdr_row = await session.get(TDRModel, UUID(tdr_id))
    assert tdr_row is not None, f"TDR {tdr_id} must exist before matching is enqueued"

    positions = (
        (
            await session.execute(
                select(ExpertPositionModel).where(ExpertPositionModel.tdr_id == UUID(tdr_id))
            )
        )
        .scalars()
        .all()
    )

    # One compiled graph serves every position/candidate in this run --
    # normalized_position_skills/required_sector_vector/sector now travel
    # via each candidate's initial state dict rather than being closed over
    # as factory args, so there's no need to rebuild the graph per position.
    graph = build_matching_graph(
        session=session, router=router, mcp_client=mcp_client, embeddings=embeddings
    ).compile(checkpointer=checkpointer)

    try:
        on_progress("processing", 0, len(positions))
        for index, position_row in enumerate(positions):
            position = ExpertPosition.model_validate(position_row.requirements_json)
            shortlist = await shortlist_candidates(position, session=session, embeddings=embeddings)

            # Position-scoped, not candidate-scoped -- computed once here
            # and reused for every candidate below, instead of
            # re-querying the taxonomy / re-embedding the same position
            # text once per candidate (see score.py's _skill_score/
            # _sector_score_with_span docstrings).
            normalized_position_skills = await normalize_position_skills(
                position, session=session, embeddings=embeddings
            )
            required_sector_vector = (
                embeddings.embed_query(position.required_sector_experience)
                if position.required_sector_experience
                else None
            )

            await session.execute(
                delete(MatchResultModel).where(
                    MatchResultModel.position_id == position_row.position_id
                )
            )
            for cv_row in shortlist:
                cv = CandidateCV.model_validate(cv_row.extracted_json)

                match_id = uuid4()
                # Deliberately partial -- normalize_skills/score/detect_anomalies/
                # generate_report fill in the rest (hard_filter_passed,
                # sub_scores, rationale, ...) via LangGraph's shallow-merge
                # partial-return convention. PipelineState has no NotRequired
                # keys, so mypy would otherwise demand a full literal here.
                initial_state = cast(
                    PipelineState,
                    {
                        "cv_extracted": cv,
                        "position": position,
                        "cv_raw_text": cv_row.raw_text,
                        "tdr_raw_text": tdr_row.raw_text or "",
                        "normalized_position_skills": normalized_position_skills,
                        "required_sector_vector": required_sector_vector,
                        "sector": tdr_row.sector,
                        "hard_filter_failures": [],
                        "anomalies": [],
                        "citations": [],
                        "needs_human_review": False,
                    },
                )
                # ADQ-24: the graph now ends in human_review's interrupt(),
                # not generate_report -- ainvoke() returns as soon as that
                # interrupt fires, with every field below already computed
                # and an extra "__interrupt__" key riding along (unread
                # here). final_state reflects "state as of the pending
                # human_review interrupt," not a fully finished run.
                final_state = await graph.ainvoke(
                    initial_state, config={"configurable": {"thread_id": str(match_id)}}
                )

                session.add(
                    MatchResultModel(
                        match_id=match_id,
                        cv_id=cv_row.cv_id,
                        tdr_id=UUID(tdr_id),
                        position_id=position_row.position_id,
                        hard_filter_passed=final_state["hard_filter_passed"],
                        hard_filter_failures_json=final_state["hard_filter_failures"],
                        compatibility_score=final_state["compatibility_score"],
                        sub_scores_json=(
                            final_state["sub_scores"].model_dump(mode="json")
                            if final_state["sub_scores"]
                            else None
                        ),
                        rationale=final_state["rationale"],
                        citations_json=[c.model_dump(mode="json") for c in final_state["citations"]],
                    )
                )
                # No relationship() is declared between MatchResultModel and
                # AnomalyModel (match_id is a plain FK column), so the
                # unit-of-work has no dependency info to order these two
                # inserts within a flush. Without this explicit flush, the
                # *next* candidate's normalize_skills SELECT autoflushes and
                # can insert this candidate's anomalies before its
                # match_results row, violating anomalies_match_id_fkey.
                await session.flush()
                session.add_all(
                    [
                        AnomalyModel(
                            match_id=match_id,
                            type=anomaly.type.value,
                            severity=anomaly.severity.value,
                            description=anomaly.description,
                            source_citation=anomaly.source_citation,
                        )
                        for anomaly in final_state["anomalies"]
                    ]
                )
            await session.commit()
            on_progress("processing", index + 1, len(positions))
    except Exception as exc:
        await session.rollback()
        on_progress("failed", 0, len(positions))
        logger.warning("matching.job_failed tdr_id=%s error=%s", tdr_id, type(exc).__name__)
        return

    on_progress("done", len(positions), len(positions))


async def _run(tdr_id: str) -> None:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    router = ModelRouter(settings)
    mcp_client = get_mcp_client(settings)
    on_progress = make_redis_matching_progress_reporter(redis_client, tdr_id)

    async with AsyncPostgresSaver.from_conn_string(
        get_checkpointer_conninfo(settings.database_url)
    ) as checkpointer:
        async with async_session_factory() as session:
            await run_matching_job(
                tdr_id,
                session=session,
                router=router,
                mcp_client=mcp_client,
                checkpointer=checkpointer,
                embeddings=router.get_embedding_model(),
                on_progress=on_progress,
            )


def run_matching(tdr_id: str) -> None:
    """RQ entry point. See app/worker/tasks.py's run_tdr_extraction for why
    this wraps in asyncio.run.
    """
    asyncio.run(_run(tdr_id))
