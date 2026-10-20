from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CV as CVModel
from app.database.models import Candidate as CandidateModel
from app.database.models import MatchResult as MatchResultModel
from app.domain.matching import SubScores
from app.features.matching.schemas import MatchResultWithCandidate


class MatchingService:
    """Reads ranked match results produced by the pipeline for a given position.

    Write-side orchestration (coarse retrieval -> normalize_skills ->
    score, persisting match_results) lives in
    app/worker/matching_tasks.py, not here -- this service is read-only.
    """

    async def list_matches_for_position(
        self, position_id: UUID, session: AsyncSession
    ) -> list[MatchResultWithCandidate]:
        stmt = (
            select(MatchResultModel, CandidateModel.full_name)
            .join(CVModel, CVModel.cv_id == MatchResultModel.cv_id)
            .join(CandidateModel, CandidateModel.candidate_id == CVModel.candidate_id)
            .where(MatchResultModel.position_id == position_id)
            .order_by(MatchResultModel.compatibility_score.desc().nulls_last())
        )
        rows = (await session.execute(stmt)).all()
        return [
            MatchResultWithCandidate(
                match_id=str(match.match_id),
                cv_id=str(match.cv_id),
                tdr_id=str(match.tdr_id),
                position_id=str(match.position_id),
                hard_filter_passed=match.hard_filter_passed,
                hard_filter_failures=match.hard_filter_failures_json or [],
                compatibility_score=(
                    float(match.compatibility_score)
                    if match.compatibility_score is not None
                    else None
                ),
                sub_scores=(
                    SubScores.model_validate(match.sub_scores_json)
                    if match.sub_scores_json
                    else None
                ),
                rationale=match.rationale,
                candidate_full_name=full_name,
            )
            for match, full_name in rows
        ]
