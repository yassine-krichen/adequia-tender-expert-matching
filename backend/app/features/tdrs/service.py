from fastapi import UploadFile

from app.domain.tdr import TDR


class TdrsService:
    """Owns TDR ingestion, section-localized extraction, and triggering matching runs."""

    async def upload_tdr(self, file: UploadFile) -> TDR:
        raise NotImplementedError

    async def get_tdr(self, tdr_id: str) -> TDR:
        raise NotImplementedError

    async def run_matching(self, tdr_id: str) -> None:
        """Kicks off the matching pipeline for every position on this TDR.

        Coarse retrieval shortlists ~8-10 candidates per position before the
        full graph runs — see docs/01-architecture.md two-phase matching.
        """
        raise NotImplementedError
