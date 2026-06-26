"""
Generate monthly asset allocation for investment-agent.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from skills.portfolio.allocation.integration import generate_monthly_allocation


def main():
    parser = argparse.ArgumentParser(description="Generate monthly asset allocation")
    parser.add_argument("--date", type=str, default=None, help="Target date in YYYYMMDD format")
    parser.add_argument("--output", type=str, default="output/allocation", help="Output directory")
    parser.add_argument("--config-dir", type=str, default="config/allocation", help="User config directory")
    parser.add_argument("--portfolio", type=str, default=None, help="Compute only this portfolio")

    args = parser.parse_args()

    try:
        result = generate_monthly_allocation(
            target_date=args.date,
            output_dir=args.output,
            config_dir=args.config_dir,
            portfolio_id=args.portfolio,
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    report = result["report"]
    paths = result["paths"]

    print(f"Allocation generated for target date: {report.target_date}")
    for r in report.results:
        print(f"\n{r.portfolio_name}:")
        print(f"  股票: {r.weights.get('equity', 0):.2%}")
        print(f"  债券: {r.weights.get('bond', 0):.2%}")
        print(f"  商品: {r.weights.get('commodity', 0):.2%}")
        print(f"  现金: {r.weights.get('cash', 0):.2%}")
        if r.fallback:
            print(f"  警告: {r.warning}")

    print(f"\nOutput saved:")
    print(f"  CSV: {paths['csv']}")
    print(f"  Markdown: {paths['markdown']}")


if __name__ == "__main__":
    main()
