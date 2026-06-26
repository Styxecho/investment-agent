"""
Risk Budget Allocator implementation.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .schema import AllocationResult, AllocationReport
from .covariance import estimate_covariance
from .risk_budget import risk_budget_weights
from .constraints import parse_constraints, apply_bounds_and_normalize
from .data_loader import warn_on_missing_prices


class RiskBudgetAllocator:
    """Risk budget allocator with target volatility scaling."""

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
            if portfolio.allocator != "risk_budget":
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
        """Allocate for a single portfolio."""
        risk_budget = np.array([
            portfolio.risk_budget.equity,
            portfolio.risk_budget.bond,
            portfolio.risk_budget.commodity,
        ])

        target_vol = portfolio.target_volatility
        vol_cap = portfolio.volatility_cap

        # Step 1: Solve risk budget for relative weights
        w_rb, fallback = risk_budget_weights(
            cov_matrix=cov,
            risk_budget=risk_budget,
        )

        # Step 2: Compute theoretical volatility
        sigma_rb = float(np.sqrt(w_rb @ cov @ w_rb))

        # Step 3: Scale to target volatility
        if sigma_rb > target_vol and sigma_rb > 0:
            scale = target_vol / sigma_rb
        else:
            scale = 1.0

        # Step 4: Apply volatility cap
        if sigma_rb > vol_cap and sigma_rb > 0:
            scale = min(scale, vol_cap / sigma_rb)

        w_scaled = w_rb * scale

        # Step 5: Apply weight constraints
        min_weights, max_weights = parse_constraints(
            portfolio.weight_constraints,
            self.ASSET_CLASSES,
        )

        w_constrained = apply_bounds_and_normalize(
            w_scaled,
            min_weights=min_weights,
            max_weights=max_weights,
            total=w_scaled.sum(),
        )

        # Step 6: Cash absorbs remainder
        risk_total = w_constrained.sum()
        cash_weight = max(0.0, 1.0 - risk_total)

        final_weights = {
            "equity": float(w_constrained[0]),
            "bond": float(w_constrained[1]),
            "commodity": float(w_constrained[2]),
            "cash": float(cash_weight),
        }

        raw_weight_dict = {
            ac: float(w_rb[i])
            for i, ac in enumerate(self.ASSET_CLASSES)
        }

        warning = None
        if fallback:
            warning = (
                "本次配置因风险预算求解器未收敛，采用 fallback 方式生成，"
                "结果可能偏离风险预算最优解。"
            )

        return AllocationResult(
            portfolio_id=pid,
            portfolio_name=portfolio.name,
            weights=final_weights,
            raw_weights=raw_weight_dict,
            risk_budget={
                "equity": portfolio.risk_budget.equity,
                "bond": portfolio.risk_budget.bond,
                "commodity": portfolio.risk_budget.commodity,
            },
            fallback=fallback,
            warning=warning,
            target_date=target_date,
            covariance_method=self.assets_config.risk_model.covariance_method,
        )
