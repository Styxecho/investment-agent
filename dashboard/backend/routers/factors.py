"""
Factor router
"""
from typing import Optional, List
from fastapi import APIRouter, Query
from dashboard.backend.schemas import (
    FactorDecompositionResponse,
    FactorLatestResponse,
)
from dashboard.backend.services.factor_service import (
    get_factor_decomposition,
    get_latest_factors,
)

router = APIRouter(prefix="/factors", tags=["factors"])


@router.get("/decomposition/{code}", response_model=FactorDecompositionResponse)
async def factor_decomposition(
    code: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYYMMDD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYYMMDD)"),
):
    """Get complete factor decomposition for an indicator"""
    result = get_factor_decomposition(code, start_date, end_date)
    if result is None:
        return {"code": code, "name": code, "category": "unknown", "data": []}
    return result


@router.get("/latest", response_model=List[FactorLatestResponse])
async def factor_latest():
    """Get latest factor values for all indicators"""
    return get_latest_factors()
