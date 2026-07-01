from fastapi import UploadFile

from app.domain.cv import CandidateCV


class CandidatesService:
    """Owns CV ingestion and the candidate roster.

    Re-uploading a CV triggers re-extraction and re-embedding for that
    candidate only — see docs/05-frontend-dashboard.md.
    """

    async def upload_cv(self, file: UploadFile) -> CandidateCV:
        raise NotImplementedError

    async def list_candidates(self) -> list[CandidateCV]:
        raise NotImplementedError
