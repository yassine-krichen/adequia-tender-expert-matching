from fastapi import APIRouter

from app.features.metrics.schemas import MetricsSnapshot
from app.features.metrics.service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])
service = MetricsService()


@router.get("", response_model=MetricsSnapshot)
async def get_current_metrics() -> MetricsSnapshot:
    return await service.get_current_metrics()
