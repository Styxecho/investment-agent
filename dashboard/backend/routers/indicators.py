"""
Indicator router
"""
from typing import List, Optional
from fastapi import APIRouter, Query
from dashboard.backend.schemas import (
    IndicatorHistoryResponse,
    IndicatorLatestResponse,
    IndicatorCatalogItem,
)
from dashboard.backend.services.indicator_service import (
    get_indicator_catalog,
    get_indicator_history,
    get_latest_indicators,
)

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("/catalog", response_model=List[IndicatorCatalogItem])
async def indicator_catalog():
    """Get all active indicator definitions"""
    return get_indicator_catalog()


@router.get("/history", response_model=List[IndicatorHistoryResponse])
async def indicator_history(
    codes: str = Query(..., description="Comma-separated indicator codes"),
    start_date: Optional[str] = Query(None, description="Start date (YYYYMMDD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYYMMDD)"),
):
    """Get historical data for specified indicators"""
    code_list = [c.strip() for c in codes.split(",")]
    return get_indicator_history(code_list, start_date, end_date)


@router.get("/latest", response_model=List[IndicatorLatestResponse])
async def indicator_latest():
    """Get latest value for each indicator"""
    return get_latest_indicators()
