import logging
from datetime import UTC, date, datetime
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    AlreadyReviewedError,
    NoPendingReviewError,
    NotFoundError,
    ReviewPersistenceFailedError,
    ValidationFailedError,
)
from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.models import CV as CVModel
from app.database.models import Anomaly as AnomalyModel
from app.database.models import HistoricalDecision as HistoricalDecisionModel
from app.database.models import MatchResult as MatchResultModel
from app.domain.matching import (
    Anomaly,
    AnomalySeverity,
    AnomalyType,
    Citation,
    MatchResult,
    ReviewDecision,
    SubScores,
)
from app.features.pipeline.graph import build_matching_graph
from app.mcp.checkpointer import get_checkpointer_conninfo
from app.mcp.client import get_mcp_client

logger = logging.getLogger(__name__)


class ReportingService:
    """Owns the full match report and the human-in-the-loop review decision.

    An override is written to match_results.reviewer_decision and appended to
    historical_decisions, closing the loop for future scoring calibration —
    see docs/03-agent-pipeline.md.
    """

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router or ModelRouter(get_settings())
        self._mcp_client = get_mcp_client(get_settings())
        self._embeddings = self._router.get_embedding_model()

    async def get_match(self, match_id: UUID, session: AsyncSession) -> MatchResult:
        match_row = await session.get(MatchResultModel, match_id)
        if match_row is None:
            raise NotFoundError(f"Match {match_id} not found")

        anomaly_rows = (
            (await session.execute(select(AnomalyModel).where(AnomalyModel.match_id == match_id)))
            .scalars()
            .all()
        )
        anomalies = [
            Anomaly(
                type=AnomalyType(row.type),
                severity=AnomalySeverity(row.severity),
                description=row.description,
                source_citation=row.source_citation or "",
            )
            for row in anomaly_rows
        ]
        citations = [Citation.model_validate(c) for c in (match_row.citations_json or [])]
        sub_scores = (
            SubScores.model_validate(match_row.sub_scores_json) if match_row.sub_scores_json else None
        )

        return MatchResult(
            match_id=str(match_row.match_id),
            cv_id=str(match_row.cv_id),
            tdr_id=str(match_row.tdr_id),
            position_id=str(match_row.position_id),
            hard_filter_passed=match_row.hard_filter_passed,
            hard_filter_failures=match_row.hard_filter_failures_json or [],
            compatibility_score=(
                float(match_row.compatibility_score)
                if match_row.compatibility_score is not None
                else None
            ),
            sub_scores=sub_scores,
            anomalies=anomalies,
            rationale=match_row.rationale,
            citations=citations,
            reviewer_decision=match_row.reviewer_decision,
            reviewer_id=match_row.reviewer_id,
            reviewer_note=match_row.reviewer_note,
            decided_at=match_row.decided_at,
        )

    async def submit_review(
        self, match_id: UUID, decision: ReviewDecision, note: str | None, session: AsyncSession
    ) -> MatchResult:
        match_row = await session.get(MatchResultModel, match_id)
        if match_row is None:
            raise NotFoundError(f"Match {match_id} not found")

        if match_row.reviewer_decision is not None:
            raise AlreadyReviewedError(f"Match {match_id} has already been reviewed")

        overridden = {ReviewDecision.overridden_to_approve, ReviewDecision.overridden_to_reject}
        if decision in overridden and not (note and note.strip()):
            raise ValidationFailedError("An override decision requires a non-empty note")

        settings = get_settings()
        # Built inline, per call -- mirrors app/worker/matching_tasks.py's
        # _run() pattern rather than adding new DI/lifespan machinery for a
        # connection this route only ever needs once, to resume one paused
        # thread.
        async with AsyncPostgresSaver.from_conn_string(
            get_checkpointer_conninfo(settings.database_url)
        ) as checkpointer:
            graph = build_matching_graph(
                session=session,
                router=self._router,
                mcp_client=self._mcp_client,
                embeddings=self._embeddings,
            ).compile(checkpointer=checkpointer)
            config: RunnableConfig = {"configurable": {"thread_id": str(match_id)}}

            # Pre-check rather than attempt-and-translate -- what LangGraph
            # raises for a stale/missing thread was never verified, so this
            # inspects the thread without resuming it first.
            snapshot = await graph.aget_state(config)

            if not snapshot.next:
                # Graph fully completed -- either it was never paused (and
                # never will be), or a prior call already resumed it and the
                # DB write-back that should have followed never landed
                # (crash, dropped connection, etc). snapshot.values still
                # carrying a recorded decision is what tells these two
                # apart: reviewer_decision is only set on the state once the
                # human_review node has actually processed a resume.
                stranded_decision = (snapshot.values or {}).get("reviewer_decision")
                if stranded_decision is None:
                    raise NoPendingReviewError(
                        f"No pending human_review interrupt for match {match_id}"
                    )

                # Stranded case: the checkpoint thread is already fully
                # consumed, so resuming it again would be a no-op at best.
                # Recover by writing the decision straight to the DB using
                # this request's decision/note, rather than re-invoking.
                if stranded_decision != decision.value:
                    logger.warning(
                        "review.stranded_decision_mismatch match_id=%s "
                        "checkpoint_decision=%s request_decision=%s",
                        match_id,
                        stranded_decision,
                        decision.value,
                    )
            elif not snapshot.interrupts:
                raise NoPendingReviewError(f"No pending human_review interrupt for match {match_id}")
            else:
                await graph.ainvoke(
                    Command(resume={"decision": decision.value, "note": note}), config=config
                )

        try:
            await self._write_back_review_decision(match_row, decision, note, session)
        except Exception as exc:
            # The checkpoint write above (ainvoke, or a prior call's ainvoke
            # in the stranded-recovery branch) is already durable at this
            # point -- only the DB side failed. Surface this loudly: a
            # silent failure here leaves match_results.reviewer_decision as
            # NULL forever, with the graph believing the review is done.
            logger.error(
                "review.write_back_failed match_id=%s thread_id=%s -- LangGraph "
                "checkpoint was already resumed/completed but the DB write-back "
                "failed; match_results.reviewer_decision was NOT persisted",
                match_id,
                config["configurable"]["thread_id"],
            )
            raise ReviewPersistenceFailedError(
                f"Failed to persist review decision for match {match_id} after "
                "the checkpoint thread had already been resumed"
            ) from exc

        return await self.get_match(match_id, session)

    async def _write_back_review_decision(
        self,
        match_row: MatchResultModel,
        decision: ReviewDecision,
        note: str | None,
        session: AsyncSession,
    ) -> None:
        """Persists a review decision to match_results and appends the
        corresponding historical_decisions row.

        Shared by submit_review's normal (just-resumed) path and its
        stranded-recovery path (checkpoint already resumed by a prior call,
        DB write-back never landed) -- both converge here.
        """
        match_row.reviewer_decision = decision.value
        match_row.reviewer_id = "anonymous"
        match_row.reviewer_note = note
        match_row.decided_at = datetime.now(UTC)

        cv_row = await session.get(CVModel, match_row.cv_id)
        assert cv_row is not None  # FK guarantees it exists alongside the match_result

        was_selected = decision in (ReviewDecision.approved, ReviewDecision.overridden_to_approve)
        session.add(
            HistoricalDecisionModel(
                tdr_id=match_row.tdr_id,
                candidate_id=cv_row.candidate_id,
                was_selected=was_selected,
                outcome_note=note,
                decided_at=date.today(),
            )
        )
        await session.commit()
