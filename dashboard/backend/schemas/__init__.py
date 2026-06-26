"""
Pydantic schemas for API responses
"""
from typing import List, Optional, Dict
from pydantic import BaseModel


# ========== Indicator Schemas ==========

class IndicatorHistoryItem(BaseModel):
    date: str
    value: float


class IndicatorCatalogItem(BaseModel):
    code: str
    name: str
    category: str
    frequency: str
    unit: Optional[str] = None
    description: Optional[str] = None


class IndicatorHistoryResponse(BaseModel):
    code: str
    name: str
    category: str
    frequency: str
    unit: Optional[str] = None
    data: List[IndicatorHistoryItem]


class IndicatorLatestResponse(BaseModel):
    code: str
    name: str
    category: str
    latest_date: str
    latest_value: float
    unit: Optional[str] = None


# ========== Factor Schemas ==========

class FactorDecompositionItem(BaseModel):
    date: str
    raw_value: float
    cycle_value: Optional[float] = None
    trend_value: Optional[float] = None
    zscore: Optional[float] = None
    deviation: Optional[float] = None
    threshold: Optional[float] = None
    raw_direction: Optional[str] = None
    trend_direction: Optional[str] = None


class FactorDecompositionResponse(BaseModel):
    code: str
    name: str
    category: str
    filter_method: Optional[str] = None
    filter_params: Optional[str] = None
    data: List[FactorDecompositionItem]


class FactorLatestResponse(BaseModel):
    code: str
    name: str
    category: str
    latest_date: str
    zscore: Optional[float] = None
    cycle: Optional[float] = None
    trend: Optional[float] = None
    deviation: Optional[float] = None
    direction: Optional[str] = None


# ========== State Schemas ==========

class DimensionState(BaseModel):
    level: str
    direction: str
    state: str
    raw_values: Dict[str, Optional[float]]
    factor_values: Dict[str, Optional[float]]


class MacroStateSnapshot(BaseModel):
    date: str
    regime: str
    growth: DimensionState
    inflation: DimensionState
    liquidity: DimensionState
    warnings: List[str]
    methodology_version: str


class RegimeTransitionItem(BaseModel):
    date: str
    regime: str
    duration_months: int


class StateHistoryItem(BaseModel):
    date: str
    regime: str
    growth_state: str
    inflation_state: str
    liquidity_state: str
    warnings: List[str] = []


# ========== Analysis Schemas ==========

class NarrativeResponse(BaseModel):
    date: str
    regime: str
    overview: str
    growth_detail: str
    inflation_detail: str
    liquidity_detail: str
    warnings: List[str]
    historical_context: Optional[str] = None
    strategy_implication: Optional[str] = None


class DataStatusItem(BaseModel):
    indicator_code: str
    indicator_name: str
    latest_date: Optional[str] = None
    record_count: int
    status: str  # "up_to_date" | "lagging" | "missing"


class DataStatusResponse(BaseModel):
    overall_status: str
    indicators: List[DataStatusItem]
    db_latest_date: Optional[str] = None
    expected_latest_date: Optional[str] = None
