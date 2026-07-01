from typing import Any

from fastapi import APIRouter

from app.features.metrics.service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])
service = MetricsService()


@router.get("")
async def get_current_metrics() -> dict[str, Any]:
    return await service.get_current_metrics()
