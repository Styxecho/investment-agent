"""
Integration layer for risk budget allocator within investment-agent.
"""

import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from risk_budget_allocator import AssetAllocator, load_config, validate_config, generate_report

from .data_adapter import load_index_prices


def generate_monthly_allocation(
    target_date: Optional[str] = None,
    output_dir: str = "output/allocation",
    config_dir: str = "config/allocation",
    portfolio_id: Optional[str] = None,
) -> dict:
    """
    Generate monthly allocation using investment-agent data.

    Args:
        target_date: Target date in YYYYMMDD format
        output_dir: Output directory
        config_dir: User config directory
        portfolio_id: If specified, only compute this portfolio

    Returns:
        Dictionary with report and file paths
    """
    # Load config
    raw_config = load_config(config_dir)
    config = validate_config(raw_config)

    # Load prices from DB
    asset_codes = [asset.code for asset in config["assets"].assets]
    prices = load_index_prices(asset_codes, price_field=config["assets"].data.price_field)

    if prices.empty:
        raise ValueError("No price data found in database")

    # Generate allocation
    allocator = AssetAllocator(config)
    report = allocator.allocate(
        prices=prices,
        target_date=target_date,
        portfolio_id=portfolio_id,
    )

    # Generate report
    paths = generate_report(report, output_dir)

    return {
        "report": report,
        "paths": paths,
    }
