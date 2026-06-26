"""
Run long-period rolling backtest for risk budget allocator using DB data.
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
from skills.portfolio.allocation.data_adapter import load_index_prices


def run_backtest(start_date: str, end_date: str, output_dir: str = "output/allocation"):
    raw_config = load_config("config/allocation")
    config = validate_config(raw_config)

    codes = [a.code for a in config["assets"].assets]
    prices = load_index_prices(codes, start_date="20140101", end_date=end_date)

    print("Prices loaded:", prices.shape)
    print("Date range:", prices.index[0], "to", prices.index[-1])
    print("\nAsset volatilities (annualized):")
    print(prices.pct_change().std() * np.sqrt(252))

    # Monthly rebalance dates
    rebalance_dates = prices.resample("ME").last().index
    rebalance_dates = rebalance_dates[
        (rebalance_dates >= pd.Timestamp(start_date)) &
        (rebalance_dates <= pd.Timestamp(end_date))
    ]

    allocator = RiskBudgetAllocator(config)

    records = []
    for reb_date in rebalance_dates:
        window = prices.loc[:reb_date]
        if len(window) < 60:
            continue

        report = allocator.allocate(window, target_date=reb_date.strftime("%Y%m%d"))

        for r in report.results:
            records.append({
                "date": reb_date,
                "portfolio": r.portfolio_id,
                "equity": r.weights["equity"],
                "bond": r.weights["bond"],
                "commodity": r.weights["commodity"],
                "cash": r.weights["cash"],
                "fallback": r.fallback,
            })

    df = pd.DataFrame(records)
    if df.empty:
        print("No records generated")
        return

    # Compute NAV
    nav_records = []
    for pid in df["portfolio"].unique():
        pid_df = df[df["portfolio"] == pid].copy().sort_values("date")
        pid_dates = pid_df["date"].values

        # Find nearest available trading dates for each rebalance date
        available_dates = prices.index
        nearest_idx = available_dates.get_indexer(pd.DatetimeIndex(pid_dates), method="ffill")
        nearest_dates = available_dates[nearest_idx]

        # Portfolio return using previous month weights
        port_returns = []
        for i, reb_date in enumerate(pid_df["date"]):
            if i == 0:
                port_returns.append(0.0)
                continue
            prev_date = nearest_dates[i - 1]
            curr_date = nearest_dates[i]
            if curr_date <= prev_date:
                port_returns.append(0.0)
                continue

            prev_weights = pid_df.iloc[i - 1]
            price_window = prices.loc[prev_date:curr_date]
            if len(price_window) < 2:
                port_returns.append(0.0)
                continue

            period_ret = price_window.iloc[-1] / price_window.iloc[0] - 1
            port_ret = (
                prev_weights["equity"] * period_ret["000985.CSI"] +
                prev_weights["bond"] * period_ret["CBA00101.CS"] +
                prev_weights["commodity"] * period_ret["AU.SHF"]
            )
            port_returns.append(port_ret)

        pid_df["portfolio_return"] = port_returns
        pid_df["nav"] = (1 + pid_df["portfolio_return"]).cumprod()
        nav_records.append(pid_df)

    nav_df = pd.concat(nav_records, ignore_index=True)

    # Save weights
    import os
    os.makedirs(output_dir, exist_ok=True)
    weights_path = Path(output_dir) / f"backtest_weights_{start_date}_{end_date}.csv"
    df.to_csv(weights_path, index=False)

    # Plot weights
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))

    for i, pid in enumerate(["conservative", "balanced", "aggressive"]):
        pid_df = df[df["portfolio"] == pid].sort_values("date")
        axes[i].stackplot(pid_df["date"], pid_df["equity"], pid_df["bond"],
                         pid_df["commodity"], pid_df["cash"],
                         labels=["Equity", "Bond", "Commodity", "Cash"])
        axes[i].set_title(f"{pid} Asset Allocation Over Time")
        axes[i].legend(loc="upper left")
        axes[i].set_ylim(0, 1)
        axes[i].grid(True, alpha=0.3)

    plt.tight_layout()
    weights_plot_path = Path(output_dir) / f"backtest_weights_{start_date}_{end_date}.png"
    plt.savefig(weights_plot_path)
    plt.close()

    # Plot NAV
    fig, ax = plt.subplots(figsize=(12, 6))
    for pid in df["portfolio"].unique():
        pid_nav = nav_df[nav_df["portfolio"] == pid].sort_values("date")
        ax.plot(pid_nav["date"], pid_nav["nav"], label=pid)
    ax.set_title("Portfolio NAV")
    ax.legend()
    ax.grid(True, alpha=0.3)
    nav_plot_path = Path(output_dir) / f"backtest_nav_{start_date}_{end_date}.png"
    plt.savefig(nav_plot_path)
    plt.close()

    # Summary statistics
    print("\n=== Allocation Statistics ===")
    for pid in ["conservative", "balanced", "aggressive"]:
        pid_df = df[df["portfolio"] == pid]
        if pid_df.empty:
            continue
        print(f"\n{pid}:")
        print("  Equity:    mean=%.1f%%, min=%.1f%%, max=%.1f%%" %
              (pid_df["equity"].mean()*100, pid_df["equity"].min()*100, pid_df["equity"].max()*100))
        print("  Bond:      mean=%.1f%%, min=%.1f%%, max=%.1f%%" %
              (pid_df["bond"].mean()*100, pid_df["bond"].min()*100, pid_df["bond"].max()*100))
        print("  Commodity: mean=%.1f%%, min=%.1f%%, max=%.1f%%" %
              (pid_df["commodity"].mean()*100, pid_df["commodity"].min()*100, pid_df["commodity"].max()*100))

    # Turnover
    print("\n=== Turnover Statistics ===")
    for pid in df["portfolio"].unique():
        pid_df = df[df["portfolio"] == pid].sort_values("date")
        risk_cols = ["equity", "bond", "commodity"]
        turnover = pid_df[risk_cols].diff().abs().sum(axis=1) / 2
        turnover = turnover.iloc[1:]  # exclude first month
        print(f"{pid}: median={turnover.median():.1%}, p75={turnover.quantile(0.75):.1%}, "
              f"p95={turnover.quantile(0.95):.1%}, max={turnover.max():.1%}")

    print(f"\nOutputs saved to {output_dir}")


if __name__ == "__main__":
    run_backtest("20210101", "20260624")
