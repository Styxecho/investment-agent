"""
Compare Risk Budget Allocator vs Target Volatility Allocator vs Unified AssetAllocator.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "risk_budget_allocator"))

import pandas as pd
import numpy as np

from risk_budget_allocator import AssetAllocator
from risk_budget_allocator.config import load_config, validate_config
from risk_budget_allocator.risk_budget_allocator_class import RiskBudgetAllocator
from risk_budget_allocator.target_vol_allocator import TargetVolAllocator
from skills.portfolio.allocation.data_adapter import load_index_prices


def compare_allocators():
    raw_config = load_config("config/allocation")
    config = validate_config(raw_config)

    codes = [a.code for a in config["assets"].assets]
    prices = load_index_prices(codes)

    print("Prices loaded:", prices.shape)
    print("Date range:", prices.index[0].date(), "to", prices.index[-1].date())

    target_date = prices.index[-1].strftime("%Y%m%d")

    print("\n" + "="*80)
    print("UNIFIED ASSET ALLOCATOR (default)")
    print("="*80)
    unified = AssetAllocator(config)
    unified_report = unified.allocate(prices, target_date=target_date)
    for r in unified_report.results:
        print("\n%s:" % r.portfolio_name)
        print("  Equity:    %.2f%%" % (r.weights['equity'] * 100))
        print("  Bond:      %.2f%%" % (r.weights['bond'] * 100))
        print("  Commodity: %.2f%%" % (r.weights['commodity'] * 100))
        print("  Cash:      %.2f%%" % (r.weights['cash'] * 100))
        print("  Fallback:  %s" % r.fallback)

    print("\n" + "="*80)
    print("RISK BUDGET ALLOCATOR")
    print("="*80)
    rb_allocator = RiskBudgetAllocator(config)
    rb_report = rb_allocator.allocate(prices, target_date=target_date)
    for r in rb_report.results:
        print("\n%s:" % r.portfolio_name)
        print("  Equity:    %.2f%%" % (r.weights['equity'] * 100))
        print("  Bond:      %.2f%%" % (r.weights['bond'] * 100))
        print("  Commodity: %.2f%%" % (r.weights['commodity'] * 100))
        print("  Cash:      %.2f%%" % (r.weights['cash'] * 100))
        print("  Fallback:  %s" % r.fallback)

    print("\n" + "="*80)
    print("TARGET VOLATILITY ALLOCATOR")
    print("="*80)
    tv_allocator = TargetVolAllocator(config)
    tv_report = tv_allocator.allocate(prices, target_date=target_date)
    for r in tv_report.results:
        print("\n%s:" % r.portfolio_name)
        print("  Equity:    %.2f%%" % (r.weights['equity'] * 100))
        print("  Bond:      %.2f%%" % (r.weights['bond'] * 100))
        print("  Commodity: %.2f%%" % (r.weights['commodity'] * 100))
        print("  Cash:      %.2f%%" % (r.weights['cash'] * 100))
        print("  Fallback:  %s" % r.fallback)


if __name__ == "__main__":
    compare_allocators()
