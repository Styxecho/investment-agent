"""
Unified asset allocation entry point.

Dispatches to the appropriate allocator based on portfolio configuration:
- risk_budget: RiskBudgetAllocator
- target_vol: TargetVolAllocator
- manual: ManualAllocator
"""

import pandas as pd
from typing import Dict, Optional

from .schema import AllocationReport
from .risk_budget_allocator_class import RiskBudgetAllocator
from .target_vol_allocator import TargetVolAllocator
from .manual_allocator import ManualAllocator


class AssetAllocator:
    """Unified allocator that dispatches per portfolio."""

    def __init__(self, config: Dict):
        self.config = config
        self._rb = RiskBudgetAllocator(config)
        self._tv = TargetVolAllocator(config)
        self._manual = ManualAllocator(config)

    def allocate(
        self,
        prices: pd.DataFrame,
        target_date: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> AllocationReport:
        """
        Generate allocation for one or all portfolios.

        Args:
            prices: DataFrame of asset prices, columns=asset codes
            target_date: Target date string in YYYYMMDD format
            portfolio_id: If specified, only compute this portfolio

        Returns:
            AllocationReport
        """
        portfolios = self.config["portfolios"].portfolios
        ids = [portfolio_id] if portfolio_id else list(portfolios.keys())

        # Group portfolios by allocator type
        by_allocator = {"risk_budget": [], "target_vol": [], "manual": []}
        for pid in ids:
            allocator_type = portfolios[pid].allocator
            by_allocator[allocator_type].append(pid)

        all_results = []

        for pid in by_allocator["risk_budget"]:
            report = self._rb.allocate(prices, target_date=target_date, portfolio_id=pid)
            all_results.extend(report.results)

        for pid in by_allocator["target_vol"]:
            report = self._tv.allocate(prices, target_date=target_date, portfolio_id=pid)
            all_results.extend(report.results)

        for pid in by_allocator["manual"]:
            report = self._manual.allocate(prices, target_date=target_date, portfolio_id=pid)
            all_results.extend(report.results)

        # Sort by portfolio_id for consistent output
        all_results.sort(key=lambda r: r.portfolio_id)

        if target_date is None:
            target_date = prices.index[-1].strftime("%Y%m%d")

        return AllocationReport(
            generated_date=report.generated_date,
            target_date=target_date,
            lookback_days=self.config["assets"].data.lookback_days,
            covariance_method=self.config["assets"].risk_model.covariance_method,
            results=all_results,
        )
