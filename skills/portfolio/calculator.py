# skills/portfolio/calculator.py
"""
Portfolio Calculation Engine (Multi-Day Vectorized Version)
支持单日或多日批量计算。
核心逻辑：DataFrame Merge (on date+code) -> GroupBy(date) -> Vectorized Calc。
"""

import pandas as pd
import numpy as np
from typing import List, Union
from datetime import date, datetime
from config.enums import AssetType
from utils.logger import logger

from .schema import (
    Position,
    MarketData,
    AssetMetrics,
    PortfolioSnapshot,
    PortfolioTimeSeries
)


def calculate_portfolio_timeseries(
        positions: List[Position],
        market_data: List[MarketData]
) -> PortfolioTimeSeries:
    """
    Args:
        positions: 多日持仓列表 (必须包含 trade_date)
        market_data: 多日行情列表 (必须包含 trade_date)

    Returns:
        PortfolioTimeSeries: 包含每日快照的时序对象
    """
    if not positions:
        return PortfolioTimeSeries(snapshots=[], start_date="", end_date="", total_days=0)

    # 1. 数据准备
    df_pos = pd.DataFrame([p.model_dump() for p in positions])
    df_mkt = pd.DataFrame([m.model_dump() for m in market_data])

    if df_mkt.empty:
        # 无行情数据，无法计算
        return PortfolioTimeSeries(snapshots=[], start_date="", end_date="", total_days=0)

    # 2. 多键合并 (Multi-Key Merge)
    # 关键点：on=['trade_date', 'asset_code']
    # 这样只有 日期和代码 都匹配的行才会在一起
    merge_keys = ['trade_date', 'asset_code']

    # 选择需要的行情列，避免列名冲突 (asset_type 两边都有，重命名一下)
    mkt_cols = ['trade_date', 'asset_code', 'close_price', 'pre_close_price', 'asset_type']
    df_mkt_subset = df_mkt[mkt_cols].rename(columns={'asset_type': 'mkt_asset_type'})

    df = df_pos.merge(
        df_mkt_subset,
        on=merge_keys,
        how='left'
    )

    # 3. 数据清洗与填充
    # 逻辑优先级：
    # 1. 若 close_price 和 pre_close_price 同时缺失 -> 视为严重数据错误，抛出异常或记录致命错误。
    # 2. 若仅 close_price 缺失 (但 pre_close 存在) -> 用 pre_close 填充 close，使 (close - pre_close) = 0，当日盈亏为0。
    # 3. 若仅 pre_close_price 缺失 (但 close 存在) -> 用 close 填充 pre_close，使 (close - pre_close) = 0，当日盈亏为0 (如新股上市首日)。

    # 检查是否双缺
    missing_both_mask = df['close_price'].isna() & df['pre_close_price'].isna()
    if missing_both_mask.any():
        missing_count = missing_both_mask.sum()
        # 提取部分样本信息用于日志，避免日志过长
        sample_missing = df.loc[missing_both_mask, ['trade_date', 'asset_code', 'asset_name']].head(5)
        missing_dates = df.loc[missing_both_mask, 'trade_date'].unique().tolist()
        missing_codes = df.loc[missing_both_mask, 'asset_code'].unique().tolist()
        error_msg = (
            f"关键数据缺失：发现 {missing_count} 条记录的 close_price 和 pre_close_price 均为空。"
            f"样本数据:\n{sample_missing.to_string()}"
            f"涉及日期总数: {len(missing_dates)}, 涉及代码总数: {len(missing_codes)}"
        )

        # 1. 记录错误日志 (会写入文件和控制台)
        logger.error(error_msg)

        # 2. 抛出异常中断计算 (防止脏数据产生错误的净值)
        raise ValueError(f"数据完整性校验失败: {missing_count} 条关键行情数据缺失。详见日志。")

    # 情况 A: close_price 缺失，但 pre_close_price 存在 -> 用 pre_close 填充 close
    mask_close_missing = df['close_price'].isna()
    if mask_close_missing.any():
        count = mask_close_missing.sum()
        logger.debug(f"发现 {count} 条记录 close_price 缺失，已使用 pre_close_price 填充 (视为当日无涨跌)。")
        df.loc[mask_close_missing, 'close_price'] = df.loc[mask_close_missing, 'pre_close_price']

    # 情况 B: pre_close_price 缺失，但 close_price 存在 -> 用 close 填充 pre_close
    # 注意：fillna 只会填充 NaN 值，不会影响已有值
    mask_pre_close_missing = df['pre_close_price'].isna()
    if mask_pre_close_missing.any():
        count = mask_pre_close_missing.sum()
        logger.debug(f"发现 {count} 条记录 pre_close_price 缺失，已使用 close_price 填充 (视为新股或数据补全)。")
        df['pre_close_price'] = df['pre_close_price'].fillna(df['close_price'])

    # 4. 分组计算 (GroupBy Apply)
    # 我们将计算逻辑封装在一个内部函数中，然后 apply 到每个 date 组
    def calc_daily_group(group_df: pd.DataFrame) -> PortfolioSnapshot:
        trade_date = group_df['trade_date'].iloc[0]

        # --- 向量化计算 (同之前逻辑) ---
        group_df['market_value'] = group_df['volume'] * group_df['close_price']
        group_df['cost_value'] = group_df['volume'] * group_df['cost_price']
        group_df['pnl_cumulated'] = group_df['market_value'] - group_df['cost_value']
        group_df['pnl_daily'] = group_df['volume'] * (group_df['close_price'] - group_df['pre_close_price'])

        total_mv = group_df['market_value'].sum()
        total_cv = group_df['cost_value'].sum()
        total_pnl_cum = group_df['pnl_cumulated'].sum()
        total_pnl_day = group_df['pnl_daily'].sum()

        if total_mv == 0:
            # 构造空快照
            return _create_empty_snapshot(trade_date)

        group_df['weight'] = group_df['market_value'] / total_mv

        # 归因计算
        group_df['asset_start_val'] = group_df['market_value'] - group_df['pnl_daily']
        group_df['asset_ret_pct'] = np.where(
            group_df['asset_start_val'] != 0,
            (group_df['pnl_daily'] / group_df['asset_start_val']) * 100,
            0.0
        )
        group_df['contrib_pnl'] = group_df['pnl_daily']
        group_df['contrib_ret'] = group_df['weight'] * group_df['asset_ret_pct']

        # 组合收益率
        port_start_val = total_mv - total_pnl_day
        daily_ret_pct = (total_pnl_day / port_start_val * 100) if port_start_val != 0 else 0.0
        net_val = (total_mv / total_cv) if total_cv != 0 else 1.0

        # 构建 Positions 列表
        pos_list = []
        for _, row in group_df.iterrows():
            pos_list.append(AssetMetrics(
                trade_date=trade_date,
                asset_code=row['asset_code'],
                asset_name=row['asset_name'],
                asset_type=row['asset_type'],  # 来自 Position
                volume=row['volume'],
                current_price=row['close_price'],
                cost_price=row['cost_price'],
                market_value=row['market_value'],
                cost_value=row['cost_value'],
                pnl_cumulated=row['pnl_cumulated'],
                pnl_daily=row['pnl_daily'],
                weight=row['weight'],
                contribution_to_daily_pnl=row['contrib_pnl'],
                contribution_to_daily_return=row['contrib_ret']
            ))

        return PortfolioSnapshot(
            trade_date=trade_date,
            total_market_value=total_mv,
            total_cost_value=total_cv,
            total_pnl_cumulated=total_pnl_cum,
            daily_pnl=total_pnl_day,
            daily_return=daily_ret_pct,
            net_value=net_val,
            positions=pos_list,
            currency="CNY",
            position_count=len(pos_list)
        )

    # 执行分组应用
    # sort=False 保持原始顺序，或者 sort=True 按日期排序
    grouped = df.groupby('trade_date', sort=True)
    snapshots = [calc_daily_group(group) for _, group in grouped]

    # 5. 构建最终结果
    if not snapshots:
        return PortfolioTimeSeries(snapshots=[], start_date="", end_date="", total_days=0)

    return PortfolioTimeSeries(
        snapshots=snapshots,
        start_date=snapshots[0].trade_date,
        end_date=snapshots[-1].trade_date,
        total_days=len(snapshots)
    )


def _create_empty_snapshot(trade_date: str) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        trade_date=trade_date,
        total_market_value=0.0,
        total_cost_value=0.0,
        total_pnl_cumulated=0.0,
        daily_pnl=0.0,
        daily_return=0.0,
        net_value=1.0,
        positions=[],
        currency="CNY",
        position_count=0
    )


# 兼容旧接口：如果用户只想算一天，可以包一层
def calculate_portfolio_snapshot(
        positions: List[Position],
        market_data: List[MarketData]
) -> PortfolioSnapshot:
    """
    兼容接口：仅返回第一天的快照。
    推荐直接使用 calculate_portfolio_timeseries。
    """
    ts = calculate_portfolio_timeseries(positions, market_data)
    if not ts.snapshots:
        return _create_empty_snapshot("")
    return ts.snapshots[0]