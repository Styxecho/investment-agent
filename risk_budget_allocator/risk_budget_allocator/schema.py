"""
Risk Budget Allocator - Pydantic schema definitions.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date


class AssetConfig(BaseModel):
    """Asset configuration."""
    code: str = Field(..., description="Asset code, e.g. 000985.CSI")
    name: str = Field(..., description="Asset display name")
    asset_class: str = Field(..., description="Asset class: equity/bond/commodity")
    description: Optional[str] = Field(None, description="Asset description")


class RiskBudgetConfig(BaseModel):
    """Risk budget allocation across asset classes."""
    equity: float = Field(..., ge=0, le=1, description="Equity risk budget")
    bond: float = Field(..., ge=0, le=1, description="Bond risk budget")
    commodity: float = Field(..., ge=0, le=1, description="Commodity risk budget")

    @field_validator("equity", "bond", "commodity")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Risk budget components must be non-negative")
        return v

    @field_validator("equity", "bond", "commodity")
    @classmethod
    def validate_sum(cls, v: float, info) -> float:
        return v


class WeightConstraint(BaseModel):
    """Weight constraint for an asset class."""
    min: Optional[float] = Field(None, ge=0, le=1, description="Minimum weight")
    max: Optional[float] = Field(None, ge=0, le=1, description="Maximum weight")

    @field_validator("max")
    @classmethod
    def validate_max_ge_min(cls, v: Optional[float], info) -> Optional[float]:
        if v is not None and info.data.get("min") is not None and v < info.data["min"]:
            raise ValueError("max must be greater than or equal to min")
        return v


class PortfolioConfig(BaseModel):
    """Portfolio configuration."""
    name: str = Field(..., description="Portfolio display name")
    description: Optional[str] = Field(None, description="Portfolio description")
    allocator: str = Field("risk_budget", description="Allocator type: risk_budget / target_vol / manual")
    risk_budget: Optional[RiskBudgetConfig] = Field(None, description="Risk budget allocation")
    fixed_weights: Optional[Dict[str, float]] = Field(None, description="Fixed weights for manual allocator")
    target_volatility: Optional[float] = Field(None, gt=0, le=1, description="Target annualized volatility")
    volatility_cap: Optional[float] = Field(None, gt=0, le=1, description="Hard cap on annualized volatility")
    weight_constraints: Dict[str, WeightConstraint] = Field(
        default_factory=dict, description="Weight constraints by asset class"
    )

    @field_validator("allocator")
    @classmethod
    def validate_allocator(cls, v: str) -> str:
        allowed = {"risk_budget", "target_vol", "manual"}
        if v not in allowed:
            raise ValueError(f"allocator must be one of {allowed}")
        return v

    @field_validator("volatility_cap")
    @classmethod
    def validate_vol_cap(cls, v: Optional[float], info) -> Optional[float]:
        target = info.data.get("target_volatility")
        if v is not None and target is not None and v < target:
            raise ValueError("volatility_cap must be greater than or equal to target_volatility")
        return v

    @model_validator(mode="after")
    def validate_allocator_params(self):
        if self.allocator in {"risk_budget", "target_vol"}:
            if self.target_volatility is None:
                raise ValueError(f"{self.allocator} allocator requires target_volatility")
            if self.risk_budget is None:
                raise ValueError(f"{self.allocator} allocator requires risk_budget")
        if self.allocator == "manual":
            if self.fixed_weights is None:
                raise ValueError("manual allocator requires fixed_weights")
        return self


class DataConfig(BaseModel):
    """Data loading configuration."""
    source: str = Field("dataframe", description="Data source: dataframe/csv")
    lookback_days: int = Field(120, ge=30, description="Lookback window in trading days")
    price_field: str = Field("close_price", description="Price field name")


class RiskModelConfig(BaseModel):
    """Risk model configuration."""
    covariance_method: str = Field("sample", description="Covariance estimation method")
    ewma_halflife: int = Field(30, ge=1, description="EWMA half-life in trading days")
    annualization: int = Field(252, ge=1, description="Annualization factor")


class AssetsConfig(BaseModel):
    """Assets configuration."""
    assets: List[AssetConfig] = Field(..., description="List of assets")
    data: DataConfig = Field(default_factory=DataConfig)
    risk_model: RiskModelConfig = Field(default_factory=RiskModelConfig)


class PortfoliosConfig(BaseModel):
    """Portfolios configuration."""
    portfolios: Dict[str, PortfolioConfig] = Field(..., description="Portfolio definitions")


class AllocationRequest(BaseModel):
    """Allocation request."""
    prices: Any = Field(..., description="Price DataFrame")
    target_date: Optional[str] = Field(None, description="Target date in YYYYMMDD format")
    portfolio_id: Optional[str] = Field(None, description="Portfolio ID to compute")


class AllocationResult(BaseModel):
    """Allocation result for a single portfolio."""
    portfolio_id: str = Field(..., description="Portfolio ID")
    portfolio_name: str = Field(..., description="Portfolio display name")
    weights: Dict[str, float] = Field(..., description="Final weights by asset class")
    raw_weights: Dict[str, float] = Field(..., description="Raw risk budget weights before cash adjustment")
    risk_budget: Dict[str, float] = Field(..., description="Target risk budget")
    fallback: bool = Field(False, description="Whether fallback was triggered")
    warning: Optional[str] = Field(None, description="Warning message if fallback triggered")
    target_date: Optional[str] = Field(None, description="Target date")
    covariance_method: str = Field("sample", description="Covariance estimation method used")


class AllocationReport(BaseModel):
    """Full allocation report for all portfolios."""
    generated_date: str = Field(..., description="Report generation date")
    target_date: Optional[str] = Field(None, description="Allocation target date")
    lookback_days: int = Field(120, description="Lookback window used")
    covariance_method: str = Field("sample", description="Covariance estimation method used")
    results: List[AllocationResult] = Field(..., description="Allocation results")
