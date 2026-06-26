# skills/portfolio/backtest/performance.py
"""
通用绩效指标计算模块
可独立于回测引擎使用，任意净值序列均可调用
"""
import pandas as pd
import numpy as np
from typing import Optional

from .schema import PerformanceMetrics


def calculate_metrics(nav_series: pd.Series, turnover: float = 0.0) -> PerformanceMetrics:
    """
    基于净值序列计算标准化绩效指标

    :param nav_series: pd.Series，index 为日期，values 为每日净值
    :param turnover: 年化换手率（可选）
    :return: PerformanceMetrics
    """
    if nav_series.empty or len(nav_series) < 2:
        return PerformanceMetrics(
            cumulative_return=0.0,
            annualized_return=0.0,
            annualized_volatility=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            calmar_ratio=0.0,
            sortino_ratio=0.0,
            win_rate_monthly=0.0,
            annualized_turnover=turnover,
        )

    daily_returns = nav_series.pct_change().dropna()
    if daily_returns.empty:
        return PerformanceMetrics(
            cumulative_return=0.0,
            annualized_return=0.0,
            annualized_volatility=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            calmar_ratio=0.0,
            sortino_ratio=0.0,
            win_rate_monthly=0.0,
            annualized_turnover=turnover,
        )

    total_return = nav_series.iloc[-1] / nav_series.iloc[0] - 1.0
    n_days = len(daily_returns)

    # 年化因子：按 252 个交易日
    ann_factor = 252.0

    ann_return = (1.0 + total_return) ** (ann_factor / n_days) - 1.0 if n_days > 0 else 0.0
    ann_vol = daily_returns.std() * np.sqrt(ann_factor)

    # 最大回撤
    running_max = nav_series.cummax()
    drawdown = (nav_series - running_max) / running_max
    max_dd = drawdown.min()

    # 夏普比率（无风险利率 = 0）
    sharpe = ann_return / ann_vol if ann_vol > 1e-12 else 0.0

    # 卡玛比率
    calmar = ann_return / abs(max_dd) if max_dd < -1e-12 else 0.0

    # 索提诺比率（下行波动率）
    downside_returns = daily_returns[daily_returns < 0]
    downside_vol = downside_returns.std() * np.sqrt(ann_factor) if not downside_returns.empty else 0.0
    sortino = ann_return / downside_vol if downside_vol > 1e-12 else 0.0

    # 月度正收益比例
    monthly_returns = daily_returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)
    win_rate = (monthly_returns > 0).mean() if not monthly_returns.empty else 0.0

    return PerformanceMetrics(
        cumulative_return=round(total_return, 4),
        annualized_return=round(ann_return, 4),
        annualized_volatility=round(ann_vol, 4),
        max_drawdown=round(max_dd, 4),
        sharpe_ratio=round(sharpe, 4),
        calmar_ratio=round(calmar, 4),
        sortino_ratio=round(sortino, 4),
        win_rate_monthly=round(win_rate, 4),
        annualized_turnover=round(turnover, 4),
    )


def calculate_turnover(rebalance_events: list) -> float:
    """
    基于再平衡事件计算年化换手率
    :param rebalance_events: RebalanceEvent 列表
    :return: 年化换手率（所有再平衡日换手率之和 / 年数）
    """
    if not rebalance_events:
        return 0.0
    total_turnover = sum(e.turnover for e in rebalance_events)
    # 根据再平衡事件覆盖的交易年数估算
    # 简化：假设每次再平衡事件间隔为月度，年化 = 总换手率 / (总天数 / 252)
    # 这里直接用 sum(turnover) 作为近似年化换手率
    # 更精确的做法需要知道每个事件的时间跨度
    return total_turnover
