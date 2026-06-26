"""
Compare rolling backtest: Risk Budget vs Target Volatility allocator.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "risk_budget_allocator"))

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from risk_budget_allocator import RiskBudgetAllocator
from risk_budget_allocator.config import load_config, validate_config
from risk_budget_allocator.target_vol_allocator import TargetVolAllocator
from skills.portfolio.allocation.data_adapter import load_index_prices


def run_comparison(start_date: str, end_date: str):
    raw_config = load_config("config/allocation")
    config = validate_config(raw_config)

    codes = [a.code for a in config["assets"].assets]
    prices = load_index_prices(codes, start_date="20140101", end_date=end_date)

    rebalance_dates = prices.resample("ME").last().index
    rebalance_dates = rebalance_dates[
        (rebalance_dates >= pd.Timestamp(start_date)) &
        (rebalance_dates <= pd.Timestamp(end_date))
    ]

    rb_allocator = RiskBudgetAllocator(config)
    tv_allocator = TargetVolAllocator(config)

    records = []
    for reb_date in rebalance_dates:
        window = prices.loc[:reb_date]
        if len(window) < 60:
            continue

        target = reb_date.strftime("%Y%m%d")

        rb_report = rb_allocator.allocate(window, target_date=target)
        tv_report = tv_allocator.allocate(window, target_date=target)

        for r in rb_report.results:
            records.append({
                "date": reb_date,
                "portfolio": r.portfolio_id,
                "method": "risk_budget",
                **r.weights,
            })

        for r in tv_report.results:
            records.append({
                "date": reb_date,
                "portfolio": r.portfolio_id,
                "method": "target_vol",
                **r.weights,
            })

    df = pd.DataFrame(records)

    # Compute realized rolling volatilities (ex-post, using next 21 days)
    # Simplified: use concurrent window vol
    vol_records = []
    for reb_date in rebalance_dates:
        hist_window = prices.loc[prices.index <= reb_date].iloc[-252:]
        if len(hist_window) < 60:
            continue
        rets = hist_window.pct_change().dropna()
        for method in ["risk_budget", "target_vol"]:
            for pid in ["conservative", "balanced", "aggressive"]:
                row = df[(df["date"] == reb_date) & (df["portfolio"] == pid) & (df["method"] == method)]
                if row.empty:
                    continue
                w = np.array([row["equity"].values[0], row["bond"].values[0], row["commodity"].values[0]])
                cov = rets[["000985.CSI", "CBA00601.CS", "AU.SHF"]].cov() * 252
                vol = np.sqrt(w @ cov.values @ w)
                vol_records.append({
                    "date": reb_date,
                    "portfolio": pid,
                    "method": method,
                    "realized_vol": vol,
                })

    vol_df = pd.DataFrame(vol_records)

    # Output statistics
    print("\n=== Mean Allocation ===")
    summary = df.groupby(["portfolio", "method"])[["equity", "bond", "commodity", "cash"]].mean()
    print(summary)

    print("\n=== Realized Volatility Statistics ===")
    vol_summary = vol_df.groupby(["portfolio", "method"])["realized_vol"].agg(["mean", "min", "max", "std"])
    print(vol_summary)

    # Plot
    output_dir = Path("output/allocation")
    output_dir.mkdir(exist_ok=True)

    fig, axes = plt.subplots(3, 2, figsize=(16, 14))

    portfolios = ["conservative", "balanced", "aggressive"]
    for i, pid in enumerate(portfolios):
        for j, method in enumerate(["risk_budget", "target_vol"]):
            pid_df = df[(df["portfolio"] == pid) & (df["method"] == method)].sort_values("date")
            ax = axes[i, j]
            ax.stackplot(pid_df["date"], pid_df["equity"], pid_df["bond"],
                        pid_df["commodity"], pid_df["cash"],
                        labels=["Equity", "Bond", "Commodity", "Cash"])
            ax.set_title(f"{pid} - {method}")
            ax.set_ylim(0, 1)
            if i == 0 and j == 0:
                ax.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig(output_dir / "comparison_weights_2021_2026.png")
    plt.close()

    # Plot realized volatility
    fig, ax = plt.subplots(figsize=(12, 6))
    for pid in portfolios:
        for method in ["risk_budget", "target_vol"]:
            pid_vol = vol_df[(vol_df["portfolio"] == pid) & (vol_df["method"] == method)].sort_values("date")
            ax.plot(pid_vol["date"], pid_vol["realized_vol"], label=f"{pid}_{method}")
    ax.set_title("Realized Volatility Over Time")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "comparison_volatility_2021_2026.png")
    plt.close()

    df.to_csv(output_dir / "comparison_weights_2021_2026.csv", index=False)
    vol_df.to_csv(output_dir / "comparison_volatility_2021_2026.csv", index=False)

    print(f"\nOutputs saved to {output_dir}")


if __name__ == "__main__":
    run_comparison("20210101", "20260624")
