from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.features.taxonomy_admin.schemas import (
    ApproveSkillCandidateRequest,
    RejectSkillCandidateRequest,
    SkillCandidateSummary,
)
from app.features.taxonomy_admin.service import TaxonomyAdminService

# No auth on this router, consistent with the rest of this app's explicit
# no-auth-in-scope design -- internal admin surface only.
router = APIRouter(prefix="/admin/skill-candidates", tags=["taxonomy-admin"])
service = TaxonomyAdminService()


@router.get("", response_model=list[SkillCandidateSummary])
async def list_skill_candidates(
    status: str = "pending", session: AsyncSession = Depends(get_db_session)
) -> list[SkillCandidateSummary]:
    return await service.list_candidates(session, status=status)


@router.post("/{candidate_id}/approve", status_code=204)
async def approve_skill_candidate(
    candidate_id: UUID,
    body: ApproveSkillCandidateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await service.approve(candidate_id, body.canonical_name, body.aliases, session)


@router.post("/{candidate_id}/reject", status_code=204)
async def reject_skill_candidate(
    candidate_id: UUID,
    body: RejectSkillCandidateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await service.reject(candidate_id, body.note, session)
