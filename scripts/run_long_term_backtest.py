"""
Long-term rolling backtest for risk budget allocator.

Monthly rebalancing, tracks NAV, drawdown, turnover, and realized volatility
for conservative, balanced, and aggressive portfolios.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "risk_budget_allocator"))

import argparse
import json
from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from risk_budget_allocator import AssetAllocator
from risk_budget_allocator.config import load_config, validate_config
from skills.portfolio.allocation.data_adapter import load_index_prices


def run_backtest(
    start_date: str,
    end_date: str,
    rebalance_freq: str = "monthly",
    output_dir: str = "output/allocation/backtest",
):
    raw_config = load_config("config/allocation")
    config = validate_config(raw_config)

    codes = [a.code for a in config["assets"].assets]
    prices = load_index_prices(codes, start_date="20150106", end_date=end_date)

    asset_class_to_code = {a.asset_class: a.code for a in config["assets"].assets}
    equity_code = asset_class_to_code["equity"]
    bond_code = asset_class_to_code["bond"]
    commodity_code = asset_class_to_code["commodity"]

    prices = prices.loc[start_date:end_date]

    if rebalance_freq == "monthly":
        rebalance_dates = prices.resample("ME").last().index
    elif rebalance_freq == "quarterly":
        rebalance_dates = prices.resample("QE").last().index
    else:
        raise ValueError(f"Unknown rebalance frequency: {rebalance_freq}")

    rebalance_dates = rebalance_dates[
        (rebalance_dates >= prices.index[0]) &
        (rebalance_dates <= prices.index[-1])
    ]

    allocator = AssetAllocator(config)
    portfolio_ids = list(config["portfolios"].portfolios.keys())

    weight_records: List[Dict] = []
    for reb_date in rebalance_dates:
        window = prices.loc[:reb_date]
        if len(window) < 60:
            continue

        target = reb_date.strftime("%Y%m%d")
        report = allocator.allocate(window, target_date=target)

        for r in report.results:
            weight_records.append({
                "date": reb_date,
                "portfolio": r.portfolio_id,
                "equity": r.weights.get("equity", 0.0),
                "bond": r.weights.get("bond", 0.0),
                "commodity": r.weights.get("commodity", 0.0),
                "cash": r.weights.get("cash", 0.0),
                "fallback": r.fallback,
            })

    weights_df = pd.DataFrame(weight_records)
    if weights_df.empty:
        raise ValueError("No backtest records generated")

    weights_df = weights_df.sort_values(["portfolio", "date"]).reset_index(drop=True)

    # Build NAV series: use daily returns between rebalance dates with weights held constant
    nav_records = []
    for pid in portfolio_ids:
        pid_weights = weights_df[weights_df["portfolio"] == pid].copy()
        if pid_weights.empty:
            continue

        # Expand to daily
        pid_nav = pd.DataFrame(index=prices.index)
        pid_nav["portfolio"] = pid
        pid_nav["equity_weight"] = np.nan
        pid_nav["bond_weight"] = np.nan
        pid_nav["commodity_weight"] = np.nan
        pid_nav["cash_weight"] = np.nan

        for _, row in pid_weights.iterrows():
            mask = pid_nav.index >= row["date"]
            pid_nav.loc[mask, "equity_weight"] = row["equity"]
            pid_nav.loc[mask, "bond_weight"] = row["bond"]
            pid_nav.loc[mask, "commodity_weight"] = row["commodity"]
            pid_nav.loc[mask, "cash_weight"] = row["cash"]

        # Forward fill initial period
        pid_nav = pid_nav.ffill()

        rets = prices.pct_change()
        pid_nav["portfolio_return"] = (
            pid_nav["equity_weight"].shift(1) * rets[equity_code] +
            pid_nav["bond_weight"].shift(1) * rets[bond_code] +
            pid_nav["commodity_weight"].shift(1) * rets[commodity_code] +
            pid_nav["cash_weight"].shift(1) * 0.0
        )
        pid_nav["nav"] = (1 + pid_nav["portfolio_return"].fillna(0)).cumprod()
        pid_nav["date"] = pid_nav.index
        nav_records.append(pid_nav.reset_index(drop=True))

    nav_df = pd.concat(nav_records, ignore_index=True)

    # Compute metrics
    metrics = {}
    for pid in portfolio_ids:
        pid_nav = nav_df[nav_df["portfolio"] == pid].set_index("date")["nav"].sort_index()
        pid_rets = pid_nav.pct_change().dropna()

        ann_ret = (pid_nav.iloc[-1] / pid_nav.iloc[0]) ** (252 / len(pid_nav)) - 1
        ann_vol = pid_rets.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan

        peak = pid_nav.cummax()
        dd = (pid_nav - peak) / peak
        max_dd = dd.min()
        calmar = ann_ret / abs(max_dd) if max_dd < 0 else np.nan

        metrics[pid] = {
            "annualized_return": float(ann_ret),
            "annualized_volatility": float(ann_vol),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_dd),
            "calmar": float(calmar),
        }

    # Turnover
    turnover_records = []
    for pid in portfolio_ids:
        pid_weights = weights_df[weights_df["portfolio"] == pid].copy()
        pid_weights["prev_equity"] = pid_weights["equity"].shift(1)
        pid_weights["prev_bond"] = pid_weights["bond"].shift(1)
        pid_weights["prev_commodity"] = pid_weights["commodity"].shift(1)

        pid_weights["turnover"] = (
            abs(pid_weights["equity"] - pid_weights["prev_equity"]) +
            abs(pid_weights["bond"] - pid_weights["prev_bond"]) +
            abs(pid_weights["commodity"] - pid_weights["prev_commodity"])
        ) / 2.0

        turnover_records.append(pid_weights)

    turnover_df = pd.concat(turnover_records, ignore_index=True)

    # Realized volatility at each rebalance date using next 21 days
    vol_records = []
    for pid in portfolio_ids:
        pid_weights = weights_df[weights_df["portfolio"] == pid].copy()
        for _, row in pid_weights.iterrows():
            reb_date = row["date"]
            future = prices.loc[reb_date:].iloc[:21]
            if len(future) < 10:
                continue
            fut_rets = future.pct_change().dropna()
            if len(fut_rets) < 5:
                continue
            w = np.array([row["equity"], row["bond"], row["commodity"]])
            cov = fut_rets[[equity_code, bond_code, commodity_code]].cov() * 252
            if cov.isna().any().any():
                continue
            vol = float(np.sqrt(w @ cov.values @ w))
            vol_records.append({
                "date": reb_date,
                "portfolio": pid,
                "realized_vol_21d": vol,
            })

    vol_df = pd.DataFrame(vol_records)

    # Save outputs
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    weights_df.to_csv(Path(output_dir) / "backtest_weights.csv", index=False)
    nav_df.to_csv(Path(output_dir) / "backtest_nav.csv", index=False)
    turnover_df.to_csv(Path(output_dir) / "backtest_turnover.csv", index=False)
    vol_df.to_csv(Path(output_dir) / "backtest_realized_vol.csv", index=False)

    with open(Path(output_dir) / "backtest_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    # Plot weights
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    for i, pid in enumerate(["conservative", "balanced", "aggressive"]):
        pid_w = weights_df[weights_df["portfolio"] == pid].sort_values("date")
        ax = axes[i]
        ax.stackplot(
            pid_w["date"],
            pid_w["equity"],
            pid_w["bond"],
            pid_w["commodity"],
            pid_w["cash"],
            labels=["Equity", "Bond", "Commodity", "Cash"],
            colors=["#d62728", "#2ca02c", "#ff7f0e", "#7f7f7f"],
        )
        ax.set_title(f"{pid} Weights")
        ax.set_ylim(0, 1)
        if i == 0:
            ax.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(Path(output_dir) / "backtest_weights.png")
    plt.close()

    # Plot NAV
    fig, ax = plt.subplots(figsize=(12, 6))
    for pid in portfolio_ids:
        pid_nav = nav_df[nav_df["portfolio"] == pid].set_index("date")["nav"].sort_index()
        ax.plot(pid_nav.index, pid_nav.values, label=pid)
    ax.set_title("Portfolio NAV")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(Path(output_dir) / "backtest_nav.png")
    plt.close()

    # Plot drawdown
    fig, ax = plt.subplots(figsize=(12, 6))
    for pid in portfolio_ids:
        pid_nav = nav_df[nav_df["portfolio"] == pid].set_index("date")["nav"].sort_index()
        peak = pid_nav.cummax()
        dd = (pid_nav - peak) / peak
        ax.plot(dd.index, dd.values, label=pid)
    ax.set_title("Drawdown")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(Path(output_dir) / "backtest_drawdown.png")
    plt.close()

    # Plot realized volatility
    fig, ax = plt.subplots(figsize=(12, 6))
    for pid in portfolio_ids:
        pid_vol = vol_df[vol_df["portfolio"] == pid].sort_values("date")
        if not pid_vol.empty:
            ax.plot(pid_vol["date"], pid_vol["realized_vol_21d"], label=pid)
    ax.set_title("Realized Volatility (21-day forward, annualized)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(Path(output_dir) / "backtest_realized_vol.png")
    plt.close()

    return {
        "metrics": metrics,
        "weights_df": weights_df,
        "nav_df": nav_df,
        "turnover_df": turnover_df,
        "vol_df": vol_df,
        "output_dir": output_dir,
    }


def main():
    parser = argparse.ArgumentParser(description="Long-term backtest for risk budget allocator")
    parser.add_argument("--start", type=str, default="20150106", help="Start date YYYYMMDD")
    parser.add_argument("--end", type=str, default="20260626", help="End date YYYYMMDD")
    parser.add_argument("--freq", type=str, default="monthly", choices=["monthly", "quarterly"])
    parser.add_argument("--output", type=str, default="output/allocation/backtest", help="Output directory")
    args = parser.parse_args()

    results = run_backtest(args.start, args.end, args.freq, args.output)

    print(f"Backtest completed: {args.start} to {args.end}")
    print(f"Outputs saved to: {args.output}")
    print("\n=== Performance Metrics ===")
    for pid, m in results["metrics"].items():
        print(f"\n{pid}:")
        print(f"  Annualized Return: {m['annualized_return']:.2%}")
        print(f"  Annualized Volatility: {m['annualized_volatility']:.2%}")
        print(f"  Sharpe: {m['sharpe']:.2f}")
        print(f"  Max Drawdown: {m['max_drawdown']:.2%}")
        print(f"  Calmar: {m['calmar']:.2f}")

    print("\n=== Turnover Statistics ===")
    stats = results["turnover_df"].groupby("portfolio")["turnover"].agg(["median", "mean", "max"])
    print(stats)

    print("\n=== Realized Volatility Statistics ===")
    stats = results["vol_df"].groupby("portfolio")["realized_vol_21d"].agg(["median", "mean", "std", "max"])
    print(stats)


if __name__ == "__main__":
    main()
