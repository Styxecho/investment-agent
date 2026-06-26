"""
State router
"""
from typing import List, Optional
from fastapi import APIRouter, Query
from dashboard.backend.schemas import (
    MacroStateSnapshot,
    StateHistoryItem,
    RegimeTransitionItem,
)
from dashboard.backend.services.state_service import (
    get_state_history,
    get_latest_state,
    get_state_by_date,
    get_regime_transitions,
)

router = APIRouter(prefix="/states", tags=["states"])


@router.get("/history", response_model=List[StateHistoryItem])
async def state_history(
    start_date: Optional[str] = Query(None, description="Start date (YYYYMMDD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYYMMDD)"),
):
    """Get macro state history"""
    return get_state_history(start_date, end_date)


@router.get("/latest", response_model=Optional[MacroStateSnapshot])
async def state_latest():
    """Get latest macro state"""
    return get_latest_state()


@router.get("/regime-transitions", response_model=List[RegimeTransitionItem])
async def regime_transitions():
    """Get regime transition history"""
    return get_regime_transitions()


# NOTE: This must be LAST to avoid matching /history, /latest, /regime-transitions
@router.get("/{date}", response_model=Optional[MacroStateSnapshot])
async def state_by_date(date: str):
    """Get macro state for specific date"""
    return get_state_by_date(date)
