"""TCO router"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import RecommendationServiceDep, TcoServiceDep
from app.api.schemas.recommendation import (
    CompareRequest,
    CompareResponse,
    RecommendRequest,
    RecommendResponse,
)
from app.api.schemas.tco import TcoCalculateRequest, TcoCalculateResponse

router = APIRouter(prefix="/api/tco", tags=["tco"])


@router.post("/calculate", response_model=TcoCalculateResponse)
async def calculate(
    request: TcoCalculateRequest, service: TcoServiceDep
) -> TcoCalculateResponse:
    """Полный расчёт TCO по 7 компонентам.

    * Если ``modification_id`` отсутствует в каталоге — 404.
    * Если профиль невалиден (например, ``driver_experience_years > age − 16``) — 422.
    """
    return await service.calculate(request)


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(
    request: RecommendRequest, service: RecommendationServiceDep
) -> RecommendResponse:
    """Recommend top-N modifications using hard filters + TOPSIS ranking."""
    return await service.recommend(request)


@router.post("/compare", response_model=CompareResponse)
async def compare(
    request: CompareRequest, service: RecommendationServiceDep
) -> CompareResponse:
    """Compare 2-3 modifications with component-level deltas."""
    return await service.compare(request)
