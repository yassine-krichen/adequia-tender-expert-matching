from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.models import TDR as TDRModel
from app.database.models import ExpertPosition as ExpertPositionModel
from app.domain.tdr import TDR
from app.features.pipeline.nodes.extract import extract_tdr
from app.features.pipeline.nodes.ingest import extract_raw_text


class TdrsService:
    """Owns TDR ingestion, section-localized extraction, and triggering matching runs."""

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router or ModelRouter(get_settings())

    async def upload_tdr(self, file: UploadFile, session: AsyncSession) -> TDR:
        file_bytes = await file.read()
        filename = file.filename or "upload"

        raw_text = extract_raw_text(file_bytes, filename)
        tdr_id = uuid4()
        tdr = extract_tdr(
            raw_text,
            tdr_id=str(tdr_id),
            source_file_path=filename,
            router=self._router,
            embeddings=self._router.get_embedding_model(),
        )

        session.add(
            TDRModel(
                tdr_id=tdr_id,
                mission_title=tdr.mission_title,
                client=tdr.client,
                sector=tdr.sector,
                deadline=tdr.deadline,
                raw_text=raw_text,
                source_file_path=filename,
                extracted_json=tdr.model_dump(mode="json"),
            )
        )
        # Flush before adding positions — without a relationship() between
        # TDR and ExpertPosition, SQLAlchemy's unit-of-work doesn't
        # guarantee FK-safe insert ordering, and can emit the position
        # insert first, violating expert_positions_tdr_id_fkey.
        await session.flush()
        for position in tdr.positions:
            session.add(
                ExpertPositionModel(
                    position_id=UUID(position.position_id),
                    tdr_id=tdr_id,
                    position_title=position.position_title,
                    requirements_json=position.model_dump(mode="json"),
                )
            )
        await session.commit()

        return tdr

    async def get_tdr(self, tdr_id: str) -> TDR:
        raise NotImplementedError

    async def run_matching(self, tdr_id: str) -> None:
        """Kicks off the matching pipeline for every position on this TDR.

        Coarse retrieval shortlists ~8-10 candidates per position before the
        full graph runs — see docs/01-architecture.md two-phase matching.
        """
        raise NotImplementedError
