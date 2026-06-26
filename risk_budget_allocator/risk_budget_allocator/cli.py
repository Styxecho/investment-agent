"""
Command line interface for risk budget allocator.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from .allocator import AssetAllocator
from .config import load_config, validate_config, init_user_config
from .data_loader import load_prices_from_csv, load_prices_from_dataframe
from .report import generate_report


def main():
    parser = argparse.ArgumentParser(description="Risk Budget Asset Allocation")
    parser.add_argument("--init", action="store_true", help="Initialize user config files")
    parser.add_argument("--date", type=str, default=None, help="Target date in YYYYMMDD format")
    parser.add_argument("--output", type=str, default="output/allocation", help="Output directory")
    parser.add_argument("--portfolio", type=str, default=None, help="Compute only this portfolio")
    parser.add_argument("--config-dir", type=str, default="config/allocation", help="User config directory")
    parser.add_argument("--prices", type=str, default=None, help="Path to CSV price file")

    args = parser.parse_args()

    if args.init:
        init_user_config(args.config_dir)
        print(f"User config initialized at: {args.config_dir}")
        print("Please edit user_assets.yaml and user_portfolios.yaml to customize.")
        return

    # Load config
    raw_config = load_config(args.config_dir)
    config = validate_config(raw_config)

    # Load prices
    if args.prices:
        prices = load_prices_from_csv(args.prices)
    else:
        # Try to load example/sample prices or use provided integration
        sample_path = Path(__file__).parent.parent / "examples" / "sample_prices.csv"
        if sample_path.exists():
            prices = load_prices_from_csv(str(sample_path))
        else:
            print("Error: No price data provided. Use --prices or run within investment-agent.")
            sys.exit(1)

    # Validate prices have required asset codes
    required_codes = [asset.code for asset in config["assets"].assets]
    missing = [code for code in required_codes if code not in prices.columns]
    if missing:
        print(f"Error: Missing required asset codes in price data: {missing}")
        sys.exit(1)

    # Allocate
    allocator = AssetAllocator(config)
    target_date = args.date
    if target_date is None:
        target_date = prices.index[-1].strftime("%Y%m%d")

    report = allocator.allocate(
        prices=prices,
        target_date=target_date,
        portfolio_id=args.portfolio,
    )

    # Generate report
    paths = generate_report(report, args.output)

    # Print summary
    print(f"Allocation generated for target date: {target_date}")
    for result in report.results:
        print(f"\n{result.portfolio_name}:")
        print(f"  股票: {result.weights.get('equity', 0):.2%}")
        print(f"  债券: {result.weights.get('bond', 0):.2%}")
        print(f"  商品: {result.weights.get('commodity', 0):.2%}")
        print(f"  现金: {result.weights.get('cash', 0):.2%}")
        if result.fallback:
            print(f"  警告: {result.warning}")

    print(f"\nOutput saved to:")
    print(f"  CSV: {paths['csv']}")
    print(f"  Markdown: {paths['markdown']}")


if __name__ == "__main__":
    main()
