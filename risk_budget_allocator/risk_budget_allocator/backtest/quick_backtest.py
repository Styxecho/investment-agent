"""
Quick backtest for risk budget allocator.

Performs monthly rolling backtest to validate allocator behavior under historical stress.
Outputs weights, NAV curve, turnover statistics, and a quantitative validation checklist.
"""

import argparse
import os
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ..allocator import AssetAllocator
from ..config import load_config, validate_config
from ..data_loader import load_prices_from_csv


def run_quick_backtest(
    prices: pd.DataFrame,
    config: Dict,
    start_date: str,
    end_date: str,
    rebalance_freq: str = "monthly",
    output_dir: str = "output/allocation",
) -> Dict:
    """
    Run monthly rolling backtest.

    Args:
        prices: Price DataFrame
        config: Validated config dict
        start_date: Start date YYYYMMDD
        end_date: End date YYYYMMDD
        rebalance_freq: "monthly" or "quarterly"
        output_dir: Output directory

    Returns:
        Dictionary with backtest results and validation summary
    """
    prices = prices.loc[start_date:end_date]
    allocator = AssetAllocator(config)

    # Map asset classes to configured codes
    asset_class_to_code = {}
    for asset in config["assets"].assets:
        if asset.asset_class not in asset_class_to_code:
            asset_class_to_code[asset.asset_class] = asset.code

    equity_code = asset_class_to_code.get("equity", "000985.CSI")
    bond_code = asset_class_to_code.get("bond", "CBA00101.CS")
    commodity_code = asset_class_to_code.get("commodity", "AU.SHF")

    # Generate rebalance dates (month end or quarter end)
    if rebalance_freq == "monthly":
        rebalance_dates = prices.resample("ME").last().index
    elif rebalance_freq == "quarterly":
        rebalance_dates = prices.resample("QE").last().index
    else:
        raise ValueError(f"Unknown rebalance frequency: {rebalance_freq}")

    # Filter dates within range
    rebalance_dates = rebalance_dates[
        (rebalance_dates >= prices.index[0]) &
        (rebalance_dates <= prices.index[-1])
    ]

    records = []
    nav = {pid: 1.0 for pid in config["portfolios"].portfolios.keys()}
    prev_weights = {}

    for i, reb_date in enumerate(rebalance_dates):
        # Use data up to reb_date
        available_prices = prices.loc[:reb_date]
        if len(available_prices) < 30:
            continue

        report = allocator.allocate(available_prices, target_date=reb_date.strftime("%Y%m%d"))

        for result in report.results:
            pid = result.portfolio_id
            weights = np.array([
                result.weights.get("equity", 0),
                result.weights.get("bond", 0),
                result.weights.get("commodity", 0),
            ])

            # Compute turnover
            if pid in prev_weights:
                turnover = np.abs(weights - prev_weights[pid]).sum() / 2.0
            else:
                turnover = 0.0

            records.append({
                "date": reb_date,
                "portfolio": pid,
                "equity": weights[0],
                "bond": weights[1],
                "commodity": weights[2],
                "cash": result.weights.get("cash", 0),
                "turnover": turnover,
                "fallback": result.fallback,
            })
            prev_weights[pid] = weights

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("No backtest records generated")

    # Compute NAV
    nav_records = []
    for pid in config["portfolios"].portfolios.keys():
        pid_df = df[df["portfolio"] == pid].copy()
        pid_df["portfolio_return"] = (
            pid_df["equity"].shift(1) * prices.loc[pid_df["date"], equity_code].pct_change().values +
            pid_df["bond"].shift(1) * prices.loc[pid_df["date"], bond_code].pct_change().values +
            pid_df["commodity"].shift(1) * prices.loc[pid_df["date"], commodity_code].pct_change().values
        )
        pid_df["nav"] = (1 + pid_df["portfolio_return"].fillna(0)).cumprod()
        nav_records.append(pid_df)

    nav_df = pd.concat(nav_records, ignore_index=True)

    # Save outputs
    os.makedirs(output_dir, exist_ok=True)
    weights_path = os.path.join(output_dir, f"quick_backtest_{start_date}_{end_date}.csv")
    plot_path = os.path.join(output_dir, f"quick_backtest_{start_date}_{end_date}.png")

    df.to_csv(weights_path, index=False)

    # Plot
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    for pid in config["portfolios"].portfolios.keys():
        pid_nav = nav_df[nav_df["portfolio"] == pid].set_index("date")["nav"]
        axes[0].plot(pid_nav.index, pid_nav.values, label=pid)
    axes[0].set_title("Backtest NAV")
    axes[0].legend()
    axes[0].grid(True)

    for pid in config["portfolios"].portfolios.keys():
        pid_df = df[df["portfolio"] == pid]
        axes[1].plot(pid_df["date"], pid_df["equity"], label=f"{pid}_equity")
    axes[1].set_title("Equity Weight Over Time")
    axes[1].legend()
    axes[1].grid(True)

    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

    # Validation checklist
    validation = _validate_backtest(df, config)

    # Turnover statistics
    turnover_stats = _turnover_statistics(df)

    return {
        "weights_path": weights_path,
        "plot_path": plot_path,
        "validation": validation,
        "turnover_stats": turnover_stats,
        "weights_df": df,
    }


def _validate_backtest(df: pd.DataFrame, config: Dict) -> List[Dict]:
    """Run quantitative validation checklist."""
    checks = []

    portfolios = config["portfolios"].portfolios

    for pid, portfolio in portfolios.items():
        pid_df = df[df["portfolio"] == pid]
        if pid_df.empty:
            continue

        max_equity = portfolio.weight_constraints.get("equity", {}).get("max")
        if max_equity is not None:
            equity_at_limit = (pid_df["equity"] >= max_equity - 0.001).mean()
            checks.append({
                "portfolio": pid,
                "check": f"股票权重未频繁触及上限 ({max_equity:.0%})",
                "condition": equity_at_limit < 0.5,
                "value": f"{equity_at_limit:.1%}",
                "status": "PASS" if equity_at_limit < 0.5 else "FAIL",
            })

        # Fallback checks
        fallback_count = pid_df["fallback"].sum()
        checks.append({
            "portfolio": pid,
            "check": "未触发 fallback",
            "condition": fallback_count == 0,
            "value": str(int(fallback_count)),
            "status": "PASS" if fallback_count == 0 else "FAIL",
        })

        # Commodity bounds
        min_comm = portfolio.weight_constraints.get("commodity", {}).get("min", 0)
        max_comm = portfolio.weight_constraints.get("commodity", {}).get("max", 1)
        commodity_ok = ((pid_df["commodity"] >= min_comm - 0.001) &
                       (pid_df["commodity"] <= max_comm + 0.001)).all()
        checks.append({
            "portfolio": pid,
            "check": f"商品权重在约束区间 [{min_comm:.0%}, {max_comm:.0%}]",
            "condition": commodity_ok,
            "value": "OK" if commodity_ok else "VIOLATED",
            "status": "PASS" if commodity_ok else "FAIL",
        })

    # Compare conservative vs aggressive
    if "conservative" in portfolios and "aggressive" in portfolios:
        cons_df = df[df["portfolio"] == "conservative"]
        agg_df = df[df["portfolio"] == "aggressive"]
        if not cons_df.empty and not agg_df.empty:
            agg_higher = (agg_df["equity"].values > cons_df["equity"].values).mean()
            checks.append({
                "portfolio": "all",
                "check": "激进组合股票权重多数时间高于保守组合",
                "condition": agg_higher > 0.5,
                "value": f"{agg_higher:.1%}",
                "status": "PASS" if agg_higher > 0.5 else "FAIL",
            })

    # Turnover check
    max_turnover = df["turnover"].max()
    checks.append({
        "portfolio": "all",
        "check": "最大单月换手率不超过 30%",
        "condition": max_turnover <= 0.30,
        "value": f"{max_turnover:.1%}",
        "status": "PASS" if max_turnover <= 0.30 else "FAIL",
    })

    return checks


def _turnover_statistics(df: pd.DataFrame) -> Dict[str, float]:
    """Compute turnover distribution statistics."""
    turnover = df["turnover"]
    return {
        "median": float(turnover.median()),
        "p75": float(turnover.quantile(0.75)),
        "p95": float(turnover.quantile(0.95)),
        "max": float(turnover.max()),
    }


def main():
    parser = argparse.ArgumentParser(description="Quick Backtest for Risk Budget Allocator")
    parser.add_argument("--prices", type=str, required=True, help="Path to CSV price file")
    parser.add_argument("--start", type=str, required=True, help="Start date YYYYMMDD")
    parser.add_argument("--end", type=str, required=True, help="End date YYYYMMDD")
    parser.add_argument("--freq", type=str, default="monthly", choices=["monthly", "quarterly"])
    parser.add_argument("--output", type=str, default="output/allocation", help="Output directory")
    parser.add_argument("--config-dir", type=str, default="config/allocation", help="User config directory")

    args = parser.parse_args()

    raw_config = load_config(args.config_dir)
    config = validate_config(raw_config)
    prices = load_prices_from_csv(args.prices)

    results = run_quick_backtest(
        prices=prices,
        config=config,
        start_date=args.start,
        end_date=args.end,
        rebalance_freq=args.freq,
        output_dir=args.output,
    )

    print(f"Backtest completed: {args.start} to {args.end}")
    print(f"Weights saved: {results['weights_path']}")
    print(f"Plot saved: {results['plot_path']}")

    print("\n=== Validation Checklist ===")
    for check in results["validation"]:
        status = "[PASS]" if check["status"] == "PASS" else "[FAIL]"
        print(f"{status} {check['portfolio']} | {check['check']} | value={check['value']}")

    print("\n=== Turnover Statistics ===")
    stats = results["turnover_stats"]
    print(f"Median: {stats['median']:.1%}")
    print(f"75%: {stats['p75']:.1%}")
    print(f"95%: {stats['p95']:.1%}")
    print(f"Max: {stats['max']:.1%}")
    if stats["median"] > 0.15:
        print("Note: Median turnover > 15%. Consider adding rebalance threshold in future.")


if __name__ == "__main__":
    main()
