"""
Report generation for risk budget allocator.
"""

import os
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .schema import AllocationReport, AllocationResult


def generate_report(report: AllocationReport, output_dir: str) -> Dict[str, str]:
    """
    Generate CSV and Markdown reports.

    Args:
        report: AllocationReport
        output_dir: Output directory

    Returns:
        Dictionary with paths to generated files
    """
    os.makedirs(output_dir, exist_ok=True)
    target_date = report.target_date or report.generated_date

    csv_path = os.path.join(output_dir, f"allocation_{target_date}.csv")
    md_path = os.path.join(output_dir, f"allocation_report_{target_date}.md")

    _write_csv(report, csv_path)
    _write_markdown(report, md_path)

    return {"csv": csv_path, "markdown": md_path}


def _write_csv(report: AllocationReport, path: str) -> None:
    """Write allocation CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "portfolio", "equity", "bond", "commodity", "cash",
            "generated_date", "target_date", "fallback", "warning"
        ])
        for result in report.results:
            writer.writerow([
                result.portfolio_id,
                f"{result.weights.get('equity', 0):.4f}",
                f"{result.weights.get('bond', 0):.4f}",
                f"{result.weights.get('commodity', 0):.4f}",
                f"{result.weights.get('cash', 0):.4f}",
                report.generated_date,
                report.target_date or "",
                str(result.fallback).lower(),
                result.warning or "",
            ])


def _write_markdown(report: AllocationReport, path: str) -> None:
    """Write allocation Markdown report."""
    lines = []
    lines.append("# 月度风险预算配置报告")
    lines.append("")
    lines.append(f"生成日期：{report.generated_date}")
    if report.target_date:
        lines.append(f"目标日期：{report.target_date}")
    lines.append(f"历史窗口：{report.lookback_days} 个交易日")
    lines.append(f"协方差估计方法：{report.covariance_method}")
    lines.append("")

    for result in report.results:
        lines.append(f"## {result.portfolio_name} ({result.portfolio_id})")
        lines.append("")
        lines.append(
            f"风险预算：股票 {result.risk_budget['equity']:.0%} / "
            f"债券 {result.risk_budget['bond']:.0%} / "
            f"商品 {result.risk_budget['commodity']:.0%}"
        )
        lines.append("")
        lines.append("| 资产类别 | 最终权重 | 风险预算权重 | 代理指数 |")
        lines.append("|---|---|---|---|")

        asset_class_names = {
            "equity": "股票",
            "bond": "债券",
            "commodity": "商品",
            "cash": "现金",
        }

        for ac in ["equity", "bond", "commodity", "cash"]:
            final = result.weights.get(ac, 0)
            raw = result.raw_weights.get(ac, 0) if ac != "cash" else 0
            raw_str = f"{raw:.2%}" if ac != "cash" else "-"
            lines.append(
                f"| {asset_class_names.get(ac, ac)} | {final:.2%} | "
                f"{raw_str} | - |"
            )

        lines.append("")

    lines.append("## 风险提示")
    lines.append("")
    fallback_count = sum(1 for r in report.results if r.fallback)
    if fallback_count > 0:
        lines.append(f"- 本次计算有 {fallback_count} 个组合触发了 fallback，请检查约束条件。")
    else:
        lines.append("- 本次计算未触发 fallback。")
    lines.append(
        f"- 配置结果基于历史 {report.lookback_days} 日收益率协方差（{report.covariance_method}）"
        "和风险预算模型，不代表未来表现。"
    )
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
