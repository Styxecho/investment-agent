"""
Manual fixed-weight allocator.

Outputs user-defined fixed weights with optional cash floor and bounds.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .schema import AllocationResult, AllocationReport
from .covariance import estimate_covariance
from .constraints import parse_constraints, apply_bounds_and_normalize
from .data_loader import warn_on_missing_prices


class ManualAllocator:
    """Manual fixed-weight allocator."""

    ASSET_CLASSES: Tuple[str, ...] = ("equity", "bond", "commodity")

    def __init__(self, config: Dict):
        self.assets_config = config["assets"]
        self.portfolios_config = config["portfolios"]
        self.asset_class_to_code = self._build_asset_class_map()

    def _build_asset_class_map(self) -> Dict[str, str]:
        mapping = {}
        for asset in self.assets_config.assets:
            if asset.asset_class not in mapping:
                mapping[asset.asset_class] = asset.code
        return mapping

    def allocate(
        self,
        prices: pd.DataFrame,
        target_date: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> AllocationReport:
        if target_date is None:
            target_date = prices.index[-1].strftime("%Y%m%d")

        lookback_days = self.assets_config.data.lookback_days
        if len(prices) > lookback_days:
            price_window = prices.iloc[-lookback_days:]
        else:
            price_window = prices

        asset_codes = [self.asset_class_to_code[ac] for ac in self.ASSET_CLASSES]
        warn_on_missing_prices(price_window, asset_codes, context=f"lookback window (last {lookback_days} days)")

        returns = price_window.pct_change().dropna()
        cov = estimate_covariance(
            returns,
            method=self.assets_config.risk_model.covariance_method,
            ewma_halflife=self.assets_config.risk_model.ewma_halflife,
            annualization=self.assets_config.risk_model.annualization,
        )

        cov = cov.loc[asset_codes, asset_codes]

        results: List[AllocationResult] = []
        portfolio_ids = [portfolio_id] if portfolio_id else list(self.portfolios_config.portfolios.keys())

        for pid in portfolio_ids:
            portfolio = self.portfolios_config.portfolios[pid]
            if portfolio.allocator != "manual":
                continue
            result = self._allocate_single(
                pid=pid,
                portfolio=portfolio,
                cov=cov.values,
                target_date=target_date,
            )
            results.append(result)

        return AllocationReport(
            generated_date=datetime.now().strftime("%Y%m%d"),
            target_date=target_date,
            lookback_days=lookback_days,
            covariance_method=self.assets_config.risk_model.covariance_method,
            results=results,
        )

    def _allocate_single(
        self,
        pid: str,
        portfolio,
        cov: np.ndarray,
        target_date: Optional[str],
    ) -> AllocationResult:
        fixed = portfolio.fixed_weights
        w = np.array([fixed["equity"], fixed["bond"], fixed["commodity"]])

        # Apply bounds
        min_weights, max_weights = parse_constraints(
            portfolio.weight_constraints,
            self.ASSET_CLASSES,
        )

        w = apply_bounds_and_normalize(
            w,
            min_weights=min_weights,
            max_weights=max_weights,
            total=w.sum(),
        )

        # Cash absorbs remainder
        risk_total = w.sum()
        cash_weight = max(0.0, 1.0 - risk_total)

        final_weights = {
            "equity": float(w[0]),
            "bond": float(w[1]),
            "commodity": float(w[2]),
            "cash": float(cash_weight),
        }

        return AllocationResult(
            portfolio_id=pid,
            portfolio_name=portfolio.name,
            weights=final_weights,
            raw_weights={ac: float(w[i]) for i, ac in enumerate(self.ASSET_CLASSES)},
            risk_budget={
                "equity": fixed["equity"],
                "bond": fixed["bond"],
                "commodity": fixed["commodity"],
            },
            fallback=False,
            warning=None,
            target_date=target_date,
            covariance_method=self.assets_config.risk_model.covariance_method,
        )
