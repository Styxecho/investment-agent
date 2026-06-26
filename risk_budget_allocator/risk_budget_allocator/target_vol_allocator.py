"""
Target volatility allocator.

Directly optimizes asset weights subject to a target volatility constraint.
Useful when risk-budgeting produces overly bond-heavy portfolios due to
large volatility differences across asset classes.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .schema import (
    AllocationResult,
    AllocationReport,
)
from .covariance import estimate_covariance
from .data_loader import warn_on_missing_prices


class TargetVolAllocator:
    """Target volatility allocator."""

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

        # Expected returns: historical annualized mean
        expected_returns = returns.mean().loc[asset_codes].values * 252

        results: List[AllocationResult] = []
        portfolio_ids = [portfolio_id] if portfolio_id else list(self.portfolios_config.portfolios.keys())

        for pid in portfolio_ids:
            portfolio = self.portfolios_config.portfolios[pid]
            if portfolio.allocator != "target_vol":
                continue
            result = self._allocate_single(
                pid=pid,
                portfolio=portfolio,
                cov=cov.values,
                expected_returns=expected_returns,
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
        expected_returns: np.ndarray,
        target_date: Optional[str],
    ) -> AllocationResult:
        target_vol = portfolio.target_volatility
        vol_cap = portfolio.volatility_cap
        effective_vol = min(target_vol, vol_cap)

        n = len(self.ASSET_CLASSES)

        # Weight constraints
        min_weights = np.zeros(n)
        max_weights = np.ones(n)

        for i, ac in enumerate(self.ASSET_CLASSES):
            if ac in portfolio.weight_constraints:
                c = portfolio.weight_constraints[ac]
                if c.min is not None:
                    min_weights[i] = c.min
                if c.max is not None:
                    max_weights[i] = c.max

        # Objective: minimize cash (i.e., maximize risk asset utilization)
        # while staying within volatility constraint.
        def objective(w):
            return float(np.sum(w))  # maximize -> minimize negative

        # Actually we want to maximize sum(w), so minimize -sum(w)
        def neg_utilization(w):
            return -float(np.sum(w))

        # Volatility constraint
        def vol_constraint(w):
            return effective_vol**2 - float(w @ cov @ w)

        # Sum constraint: risk assets sum to <= 1 (cash absorbs remainder)
        constraints = [
            {"type": "ineq", "fun": vol_constraint},
            {"type": "ineq", "fun": lambda w: 1.0 - np.sum(w)},
        ]

        bounds = [(min_weights[i], max_weights[i]) for i in range(n)]

        # Initial guess: equal weight within bounds
        x0 = np.clip(np.ones(n) / n, min_weights, max_weights)

        result = minimize(
            neg_utilization,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-10},
        )

        w = np.clip(result.x, min_weights, max_weights) if result.x is not None else x0
        risk_total = w.sum()
        cash_weight = max(0.0, 1.0 - risk_total)

        # Normalize risk weights to sum to risk_total (preserve scale)
        if risk_total > 0:
            w = w * (risk_total / w.sum())

        final_weights = {
            "equity": float(w[0]),
            "bond": float(w[1]),
            "commodity": float(w[2]),
            "cash": float(cash_weight),
        }

        # Compute realized volatility
        realized_vol = float(np.sqrt(w @ cov @ w))

        fallback = not result.success
        warning = None
        if fallback:
            warning = "目标波动率优化未收敛，使用初始猜测。"

        return AllocationResult(
            portfolio_id=pid,
            portfolio_name=portfolio.name,
            weights=final_weights,
            raw_weights={ac: float(w[i]) for i, ac in enumerate(self.ASSET_CLASSES)},
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
