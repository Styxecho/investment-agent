# skills/portfolio/backtest/engine.py
"""
回测引擎核心
负责数据获取、组合构建、净值计算、再平衡模拟
支持ETF指数替代：上市前使用全收益指数数据，按比例缩放
"""
import pandas as pd
import numpy as np
import sqlite3
import csv
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from pathlib import Path

from sklearn.covariance import LedoitWolf

from data_external.db.repositories import MarketDataRepository, FundRepository
from config.enums import AssetType
from utils.trade_calendar import TradeCalendarService
from utils.logger import logger

from .schema import (
    BacktestRequest,
    BacktestResult,
    BacktestDailyRecord,
    RebalanceEvent,
    PerformanceMetrics,
)
from .risk_parity import build_weights
from .performance import calculate_metrics


# ==================== ETF 元数据管理 ====================

def _get_etf_metadata() -> Dict[str, Dict]:
    """
    从 etf_universe.csv 读取 ETF 元数据
    返回: {etf_code: {index_code, total_fee, listed_date, ...}}
    """
    metadata = {}
    try:
        csv_path = Path('data_external/reference/etf_universe.csv')
        if not csv_path.exists():
            logger.warning(f"[BacktestEngine] ETF元数据文件不存在: {csv_path}")
            return metadata
        
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get('code', '').strip()
                if not code:
                    continue
                metadata[code] = {
                    'code': code,
                    'name': row.get('name', ''),
                    'index_code': row.get('index_code', ''),
                    'total_fee': float(row.get('total_fee', 0)) if row.get('total_fee') else 0.0,
                    'listed_date': row.get('listed_date', ''),
                    'pool_role': row.get('pool_role', ''),
                }
    except Exception as e:
        logger.warning(f"[BacktestEngine] 读取ETF元数据失败: {e}")
    
    return metadata


def _get_index_mapping() -> Dict[str, Dict]:
    """
    从 index_universe.csv 读取指数映射关系
    返回: {price_index_code: {storage_code, index_type, ...}}
    """
    mapping = {}
    try:
        csv_path = Path('data_external/reference/index_universe.csv')
        if not csv_path.exists():
            logger.warning(f"[BacktestEngine] 指数映射文件不存在: {csv_path}")
            return mapping
        
        # 尝试不同编码
        encodings = ['utf-8-sig', 'gbk', 'gb2312', 'utf-8']
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        idx_code = row.get('index_code', '').strip()
                        if not idx_code:
                            continue
                        idx_type = row.get('index_type', 'price')
                        tr_index = row.get('total_return_index', '').strip()
                        
                        # 确定用于存储的代码
                        if idx_type == 'total_return':
                            storage_code = idx_code
                        elif idx_type == 'price' and tr_index:
                            storage_code = tr_index
                        else:
                            storage_code = idx_code
                        
                        mapping[idx_code] = {
                            'storage_code': storage_code,
                            'index_type': idx_type,
                            'index_name': row.get('index_name', ''),
                            'total_return_index': tr_index,
                        }
                break  # 成功读取后跳出循环
            except UnicodeDecodeError:
                continue  # 编码不匹配，尝试下一个
            except Exception as e:
                logger.warning(f"[BacktestEngine] 读取指数映射失败 ({encoding}): {e}")
                break
    except Exception as e:
        logger.warning(f"[BacktestEngine] 读取指数映射失败: {e}")
    
    return mapping


# ==================== 指数数据查询 ====================

def _fetch_index_series(
    index_code: str,
    start_date: str,
    end_date: str,
) -> Optional[pd.Series]:
    """
    从 SQLite index_daily 表获取指数价格序列
    
    :param index_code: 指数代码（存储用的代码，如 h20269.CSI）
    :param start_date: 开始日期 (YYYYMMDD)
    :param end_date: 结束日期 (YYYYMMDD)
    :return: 收盘价序列，index=trade_date
    """
    try:
        db_path = Path('data_external/db/external_data.db')
        if not db_path.exists():
            logger.warning(f"[BacktestEngine] 数据库不存在: {db_path}")
            return None
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 转换日期格式
        start_dt = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
        
        cursor.execute('''
            SELECT trade_date, close_price 
            FROM index_daily 
            WHERE index_code = ? AND trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date ASC
        ''', (index_code, start_dt, end_dt))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        dates = [pd.Timestamp(r[0]) for r in rows]
        prices = [r[1] for r in rows]
        
        return pd.Series(prices, index=dates, name=index_code)
        
    except Exception as e:
        logger.warning(f"[BacktestEngine] 读取指数 {index_code} 数据失败: {e}")
        return None


def _is_in_etf_universe(code: str) -> bool:
    """检查代码是否在ETF池中"""
    metadata = _get_etf_metadata()
    return code in metadata


def _detect_asset_type(code: str) -> AssetType:
    """根据代码后缀和特征推断资产类型"""
    code = str(code).strip().upper()
    if code.endswith(".OF"):
        return AssetType.FUND
    # ETF 判断：沪市 51/56/58 开头，深市 15/16 开头
    prefix = code.split(".")[0]
    if code.endswith(".SH") and prefix[:2] in ("51", "56", "58", "50"):
        return AssetType.ETF
    if code.endswith(".SZ") and prefix[:2] in ("15", "16"):
        return AssetType.ETF
    return AssetType.STOCK


def _fetch_etf_data_with_substitution(
    etf_code: str,
    start_date: str,
    end_date: str,
) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
    """
    获取ETF价格序列，支持指数替代
    
    逻辑：
    1. 先获取ETF实际数据（上市后）
    2. 如果ETF在etf_universe.csv中有定义，且指定了index_code
    3. 尝试获取指数数据用于填补上市前空白
    4. 使用上市日重叠价格计算缩放因子，缩放指数价格后拼接
    
    :return: (price_series, substitution_mask) 或 (None, None)
             substitution_mask: True表示该日使用了指数替代
    """
    # 1. 获取ETF元数据
    etf_meta = _get_etf_metadata().get(etf_code, {})
    index_code = etf_meta.get('index_code', '')
    listed_date_str = etf_meta.get('listed_date', '')
    
    # 2. 获取ETF实际数据（从数据库）
    etf_series = None
    try:
        df = MarketDataRepository.get_daily_data(etf_code, start_date, end_date)
        if df is not None and not df.empty:
            df = df.copy()
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values('trade_date')
            df = df.set_index('trade_date')
            etf_series = df['close']
    except Exception as e:
        logger.warning(f"[BacktestEngine] 读取ETF {etf_code} 数据失败: {e}")
    
    # 3. 如果没有index_code或不属于ETF池，直接返回ETF数据（无替代）
    if not index_code or not listed_date_str:
        if etf_series is not None and not etf_series.empty:
            substitution_mask = pd.Series(False, index=etf_series.index)
            return etf_series, substitution_mask
        return None, None
    
    # 4. 获取指数映射
    index_mapping = _get_index_mapping()
    if index_code not in index_mapping:
        # 找不到指数映射，只能用ETF实际数据
        if etf_series is not None and not etf_series.empty:
            substitution_mask = pd.Series(False, index=etf_series.index)
            return etf_series, substitution_mask
        return None, None
    
    storage_code = index_mapping[index_code]['storage_code']
    
    # 5. 获取指数数据
    index_series = _fetch_index_series(storage_code, start_date, end_date)
    if index_series is None or index_series.empty:
        # 无指数数据，只能用ETF实际数据
        if etf_series is not None and not etf_series.empty:
            substitution_mask = pd.Series(False, index=etf_series.index)
            return etf_series, substitution_mask
        return None, None
    
    # 6. 计算缩放因子
    # 找到ETF首个有效价格和对应日期的指数价格
    if etf_series is not None and not etf_series.empty:
        first_etf_date = etf_series.first_valid_index()
        first_etf_price = etf_series.loc[first_etf_date]
        
        # 在同一天找指数价格
        if first_etf_date in index_series.index:
            index_price_at_listing = index_series.loc[first_etf_date]
            scale_factor = first_etf_price / index_price_at_listing
            logger.info(f"[BacktestEngine] {etf_code} 缩放因子: {scale_factor:.15f} "
                       f"(ETF={first_etf_price:.6f}, Index={index_price_at_listing:.6f} @ {first_etf_date.strftime('%Y-%m-%d')})")
        else:
            # 上市日无指数数据，无法缩放，只能用ETF数据
            substitution_mask = pd.Series(False, index=etf_series.index)
            return etf_series, substitution_mask
    else:
        # 无ETF数据，全部用指数（这种情况不应该发生，但做保护）
        scale_factor = 1.0
        first_etf_date = None
    
    # 7. 缩放指数数据
    scaled_index = index_series * scale_factor
    
    # 8. 合并：上市前用缩放后的指数，上市后用ETF实际数据
    if etf_series is not None and not etf_series.empty:
        # 上市前部分：用缩放指数
        pre_listing_mask = scaled_index.index < first_etf_date
        pre_listing_data = scaled_index[pre_listing_mask]
        
        # 合并
        combined = pd.concat([pre_listing_data, etf_series]).sort_index()
        
        # 生成替代掩码：上市前为True
        substitution_mask = pd.Series(
            [idx < first_etf_date for idx in combined.index],
            index=combined.index
        )
    else:
        # 全部用指数（理论上不会发生）
        combined = scaled_index
        substitution_mask = pd.Series(True, index=combined.index)
    
    # 9. 截断到请求区间
    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date)
    combined = combined[(combined.index >= start_dt) & (combined.index <= end_dt)]
    substitution_mask = substitution_mask[(substitution_mask.index >= start_dt) & (substitution_mask.index <= end_dt)]
    
    return combined, substitution_mask


def _fetch_price_series(
    code: str,
    start_date: str,
    end_date: str,
) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
    """
    获取单只资产的历史价格序列（收盘价/单位净值）
    
    根据资产类型决定获取方式：
    - ETF: 支持指数替代（上市前用全收益指数）
    - 股票: 直接读取
    - 基金: 直接读取净值
    
    :return: (price_series, substitution_mask)
             substitution_mask: True表示该日使用了指数替代（仅ETF可能为True）
    """
    # 检查是否是ETF（必须在etf_universe.csv中定义的才算）
    if _is_in_etf_universe(code):
        return _fetch_etf_data_with_substitution(code, start_date, end_date)
    
    # 非ETF资产：直接读取，无替代
    asset_type = _detect_asset_type(code)
    
    try:
        if asset_type == AssetType.FUND:
            df = FundRepository.get_fund_nav(code, start_date, end_date)
            if df is not None and not df.empty:
                df = df.copy()
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                df = df.sort_values('trade_date')
                df = df.set_index('trade_date')
                series = df['adjusted_nav']
                mask = pd.Series(False, index=series.index)
                return series, mask
        else:
            df = MarketDataRepository.get_daily_data(code, start_date, end_date)
            if df is not None and not df.empty:
                df = df.copy()
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                df = df.sort_values('trade_date')
                df = df.set_index('trade_date')
                series = df['close']
                mask = pd.Series(False, index=series.index)
                return series, mask
    except Exception as e:
        logger.warning(f"[BacktestEngine] 读取 {code} 数据失败: {e}")

    return None, None


def _build_price_matrix(
    codes: List[str],
    start_date: str,
    end_date: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float]]:
    """
    构建多只资产的价格矩阵
    
    适配新的数据存储方式：
    - 数据库中只存储上市后的数据，无占位记录
    - 使用交易日历生成完整日期范围，对各ETF数据 reindex 对齐
    - 缺失的日期自动为 NaN
    - ETF支持指数替代（上市前用全收益指数）
    
    :return: Tuple[price_df, substitution_mask_df, fee_dict]
             - price_df: DataFrame, index=trade_date, columns=codes, 价格数据
             - substitution_mask_df: DataFrame, index=trade_date, columns=codes, True表示该日使用了指数替代
             - fee_dict: Dict[code, total_fee], ETF费率（%/年），非ETF为0
    """
    # 获取ETF元数据
    etf_metadata = _get_etf_metadata()
    
    # 加载上市日期映射
    listed_dates = {}
    try:
        csv_path = Path('data_external/reference/etf_universe.csv')
        if csv_path.exists():
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['code'] in codes:
                        listed_dates[row['code']] = pd.Timestamp(row['listed_date'])
    except Exception as e:
        logger.warning(f"[BacktestEngine] 无法读取ETF上市日期: {e}")
    
    # 获取交易日历，生成完整的日期范围
    calendar = TradeCalendarService()
    trading_days = calendar.get_trading_date_range(start_date, end_date)
    if not trading_days:
        raise ValueError(f"指定区间 {start_date} ~ {end_date} 无交易日")
    full_date_index = pd.to_datetime(trading_days)
    
    price_dict = {}
    mask_dict = {}
    fee_dict = {}
    
    for code in codes:
        series, mask = _fetch_price_series(code, start_date, end_date)
        
        if series is not None and not series.empty:
            # 将价格序列对齐到完整的交易日历
            series.index = pd.to_datetime(series.index)
            series = series.reindex(full_date_index)
            price_dict[code] = series
            
            if mask is not None:
                mask.index = pd.to_datetime(mask.index)
                mask = mask.reindex(full_date_index, fill_value=False)
                mask_dict[code] = mask
            else:
                mask_dict[code] = pd.Series(False, index=full_date_index)
            
            # 记录费率（仅ETF）
            if code in etf_metadata:
                fee_dict[code] = etf_metadata[code].get('total_fee', 0.0)
            else:
                fee_dict[code] = 0.0
        else:
            logger.warning(f"[BacktestEngine] {code} 无历史数据，将跳过")

    if not price_dict:
        raise ValueError("所有资产均无法获取历史数据")

    price_df = pd.DataFrame(price_dict)
    price_df.index = pd.to_datetime(price_df.index)
    
    substitution_mask_df = pd.DataFrame(mask_dict)
    substitution_mask_df.index = pd.to_datetime(substitution_mask_df.index)
    
    # 将价格为0的视为缺失数据（停牌等情况）
    price_df = price_df.replace(0, pd.NA)
    
    # 第二层过滤：移除所有资产价格都是 NaN 的日期行（节假日等无数据日）
    # 这是基于数据可用性的兜底逻辑
    valid_rows = price_df.notna().any(axis=1)
    if not valid_rows.all():
        removed_dates = price_df.index[~valid_rows]
        logger.debug(f"[BacktestEngine] 移除 {len(removed_dates)} 个无数据日期: {removed_dates[:5].tolist()}...")
        price_df = price_df[valid_rows]
        substitution_mask_df = substitution_mask_df.loc[price_df.index]
    
    return price_df, substitution_mask_df, fee_dict


def _estimate_covariance(returns_df: pd.DataFrame) -> np.ndarray:
    """
    估计年化协方差矩阵。
    先尝试样本协方差，若非正定则 fallback 到 Ledoit-Wolf 收缩估计。
    """
    clean_returns = returns_df.dropna()
    if clean_returns.empty or clean_returns.shape[1] == 0:
        raise ValueError("收益率数据为空，无法估计协方差")

    # 样本协方差（年化）
    sample_cov = clean_returns.cov().values * 252.0

    # 检查正定性
    try:
        eigvals = np.linalg.eigvalsh(sample_cov)
        if np.min(eigvals) > 1e-12:
            return sample_cov
    except Exception:
        pass

    # Fallback：Ledoit-Wolf
    logger.info("[BacktestEngine] 样本协方差非正定，使用 Ledoit-Wolf 收缩估计")
    lw = LedoitWolf()
    lw.fit(clean_returns.values)
    cov = lw.covariance_ * 252.0
    return cov


def _get_rebalance_dates(
    price_index: pd.DatetimeIndex,
    freq: str,
) -> List[date]:
    """
    根据价格序列的交易日索引，生成再平衡执行日期列表
    规则：月末/季末的**下一个交易日**执行
    """
    if freq == "none":
        return []

    all_dates = pd.Series(price_index).dt.date.tolist()
    date_set = set(all_dates)

    rebalance_dates = []
    for i, d in enumerate(all_dates):
        # 判断是否是月末/季末
        is_month_end = False
        is_quarter_end = False

        current_dt = pd.Timestamp(d)
        if i + 1 < len(all_dates):
            next_dt = pd.Timestamp(all_dates[i + 1])
            if next_dt.month != current_dt.month:
                is_month_end = True
            if is_month_end and current_dt.month in (3, 6, 9, 12):
                is_quarter_end = True
        else:
            # 最后一天视为月末
            is_month_end = True
            if current_dt.month in (3, 6, 9, 12):
                is_quarter_end = True

        should_rebalance = False
        if freq == "monthly" and is_month_end:
            should_rebalance = True
        if freq == "quarterly" and is_quarter_end:
            should_rebalance = True

        if should_rebalance:
            # 执行日为下一个交易日
            if i + 1 < len(all_dates):
                exec_date = all_dates[i + 1]
            else:
                exec_date = d
            rebalance_dates.append(exec_date)

    # 去重并保持有序
    seen = set()
    unique_dates = []
    for d in rebalance_dates:
        if d not in seen:
            seen.add(d)
            unique_dates.append(d)

    return unique_dates


def _calculate_turnover_annualized(
    rebalance_events: List[RebalanceEvent],
    total_trading_days: int,
) -> float:
    """计算年化换手率"""
    if not rebalance_events or total_trading_days <= 0:
        return 0.0
    total_turnover = sum(e.turnover for e in rebalance_events)
    # 年化 = 总换手率 / (总天数 / 252)
    years = total_trading_days / 252.0
    return total_turnover / years if years > 0 else 0.0


class BacktestEngine:
    """回测引擎"""

    def run(self, request: BacktestRequest) -> BacktestResult:
        try:
            return self._run_core(request)
        except Exception as e:
            logger.exception(f"[BacktestEngine] 回测失败: {e}")
            return BacktestResult(
                request=request,
                metrics=PerformanceMetrics(
                    cumulative_return=0.0,
                    annualized_return=0.0,
                    annualized_volatility=0.0,
                    max_drawdown=0.0,
                    sharpe_ratio=0.0,
                    calmar_ratio=0.0,
                    sortino_ratio=0.0,
                    win_rate_monthly=0.0,
                    annualized_turnover=0.0,
                ),
                daily_records=[],
                rebalance_events=[],
                error_message=str(e),
            )

    def _run_core(self, request: BacktestRequest) -> BacktestResult:
        all_codes = [a.code for a in request.assets]
        user_weights = [a.weight for a in request.assets]
        start_date = request.start_date
        end_date = request.end_date
        method = request.method
        freq = request.rebalance_freq
        lookback = request.lookback_days
        initial_nav = request.initial_nav

        # 1. 获取价格矩阵（支持指数替代）
        calendar = TradeCalendarService()
        trading_days = calendar.get_trading_date_range(start_date, end_date)
        if not trading_days:
            raise ValueError(f"指定区间 {start_date} ~ {end_date} 无交易日")

        # 估算需要的最早日期（lookback + 缓冲）
        earliest_needed = pd.Timestamp(start_date) - pd.Timedelta(days=lookback + 60)
        earliest_needed_str = earliest_needed.strftime("%Y%m%d")

        price_df, substitution_mask_df, fee_dict = _build_price_matrix(
            all_codes, earliest_needed_str, end_date
        )
        if price_df.empty:
            raise ValueError("无法获取任何资产的有效价格数据")

        # 只使用有数据的资产
        codes = list(price_df.columns)
        
        # 1.5 分离现金资产和风险资产
        # 从 etf_universe.csv 读取 pool_role 标记
        etf_metadata = _get_etf_metadata()
        cash_codes = [c for c in codes if etf_metadata.get(c, {}).get('pool_role') == 'cash']
        risk_codes = [c for c in codes if c not in cash_codes]
        
        logger.info(f"[BacktestEngine] 资产分类: 风险资产 {len(risk_codes)} 只, 现金替代 {len(cash_codes)} 只")
        if cash_codes:
            logger.info(f"[BacktestEngine] 现金替代资产: {cash_codes}")
        
        # 2. 确定每个资产的首个有效数据日期
        first_valid_dates = {}
        for col in price_df.columns:
            first_valid = price_df[col].first_valid_index()
            if first_valid is not None:
                first_valid_dates[col] = first_valid
        
        # 3. 确定回测期间的交易日和再平衡日期
        backtest_start = pd.Timestamp(start_date)
        backtest_end = pd.Timestamp(end_date)
        price_df = price_df[(price_df.index >= backtest_start) & (price_df.index <= backtest_end)]
        substitution_mask_df = substitution_mask_df[
            (substitution_mask_df.index >= backtest_start) & 
            (substitution_mask_df.index <= backtest_end)
        ]
        
        # 计算收益率（用于协方差估计）
        returns_df = price_df.pct_change().dropna()

        if price_df.empty:
            raise ValueError("回测区间内无有效价格数据")

        rebalance_dates = _get_rebalance_dates(price_df.index, freq)
        logger.info(f"[BacktestEngine] 回测区间: {start_date} ~ {end_date}, 再平衡次数: {len(rebalance_dates)}")

        # 4. 初始化组合状态
        n_all_assets = len(codes)
        current_weights = np.zeros(n_all_assets)
        nav = initial_nav

        daily_records: List[BacktestDailyRecord] = []
        rebalance_events: List[RebalanceEvent] = []

        # 辅助函数：获取当日有数据的资产列表
        def get_available_assets(date_idx):
            """返回当日有有效数据的资产代码列表"""
            available = []
            for code in codes:
                if code in first_valid_dates and date_idx >= first_valid_dates[code]:
                    if not pd.isna(price_df.loc[date_idx, code]):
                        available.append(code)
            return available

        # 辅助函数：计算目标权重（仅对风险资产计算，现金资产获得剩余权重）
        def calculate_target_weights(available_codes, hist_returns_df):
            """对可用资产计算目标权重
            
            模式A：仅对风险资产计算风险平价，现金资产获得剩余权重
            """
            if not available_codes:
                return {code: 0.0 for code in codes}
            
            # 分离可用的风险资产和现金资产
            available_risk = [c for c in available_codes if c in risk_codes]
            available_cash = [c for c in available_codes if c in cash_codes]
            
            # 如果没有可用的风险资产，全部给现金（或等权）
            if not available_risk:
                full_weights = {code: 0.0 for code in codes}
                if available_cash:
                    for c in available_cash:
                        full_weights[c] = 1.0 / len(available_cash)
                return full_weights
            
            n_risk = len(available_risk)
            
            # 对风险资产计算权重
            if hist_returns_df.shape[0] < 30:
                # 数据不足，等权
                risk_weights = np.ones(n_risk) / n_risk
            else:
                try:
                    # 只使用可用风险资产的数据
                    risk_returns = hist_returns_df[available_risk].dropna()
                    if risk_returns.shape[1] == 0 or risk_returns.shape[0] < 30:
                        risk_weights = np.ones(n_risk) / n_risk
                    else:
                        cov = _estimate_covariance(risk_returns)
                        if method == "risk_parity":
                            risk_weights = build_weights("risk_parity", cov)
                        elif method == "risk_parity_target_vol":
                            risk_weights = build_weights("risk_parity_target_vol", cov, target_volatility=request.target_volatility)
                        elif method == "equal_weight":
                            risk_weights = build_weights("equal_weight", cov)
                        elif method == "user_defined":
                            # 过滤用户权重到可用风险资产
                            user_w = []
                            for c in available_risk:
                                if c in all_codes:
                                    idx = all_codes.index(c)
                                    w = user_weights[idx] if user_weights[idx] is not None else 0.0
                                else:
                                    w = 0.0
                                user_w.append(w)
                            user_w = np.array(user_w, dtype=float)
                            user_w = np.maximum(user_w, 0)
                            if user_w.sum() > 0:
                                risk_weights = user_w / user_w.sum()
                            else:
                                risk_weights = np.ones(n_risk) / n_risk
                        else:
                            risk_weights = np.ones(n_risk) / n_risk
                except Exception as e:
                    logger.warning(f"[BacktestEngine] 权重计算失败: {e}，使用等权")
                    risk_weights = np.ones(n_risk) / n_risk
            
            # 构建完整权重字典
            full_weights = {code: 0.0 for code in codes}
            
            # 风险资产权重
            for i, code in enumerate(available_risk):
                full_weights[code] = risk_weights[i]
            
            # 现金资产获得剩余权重（模式A）
            risk_sum = sum(full_weights[c] for c in available_risk)
            remaining = 1.0 - risk_sum
            
            if available_cash and remaining > 0:
                # 剩余权重平均分配给现金资产
                for c in available_cash:
                    full_weights[c] = remaining / len(available_cash)
            
            return full_weights

        # 5. 首日权重设定
        first_date = price_df.index[0]
        first_available = get_available_assets(first_date)
        
        if method == "user_defined":
            # 过滤用户权重到首日可用资产
            target = np.array([user_weights[i] if user_weights[i] is not None else 0.0 for i in range(n_all_assets)], dtype=float)
            target = np.maximum(target, 0)
            # 只保留首日可用的资产
            for i, code in enumerate(codes):
                if code not in first_available:
                    target[i] = 0
            if target.sum() > 0:
                target = target / target.sum()
            else:
                target = np.zeros(n_all_assets)
            current_weights = target.copy()
        elif method == "equal_weight":
            target = np.zeros(n_all_assets)
            for code in first_available:
                target[codes.index(code)] = 1.0 / len(first_available)
            current_weights = target.copy()
        elif method == "risk_parity_target_vol":
            lookback_end = first_date
            lookback_start = lookback_end - pd.Timedelta(days=lookback)
            hist_returns = returns_df[returns_df.index >= lookback_start]
            target_weights_dict = calculate_target_weights(first_available, hist_returns)
            current_weights = np.array([target_weights_dict.get(code, 0.0) for code in codes])
        else:
            # risk_parity
            lookback_end = first_date
            lookback_start = lookback_end - pd.Timedelta(days=lookback)
            hist_returns = returns_df[returns_df.index >= lookback_start]
            target_weights_dict = calculate_target_weights(first_available, hist_returns)
            current_weights = np.array([target_weights_dict.get(code, 0.0) for code in codes])

        # 6. 逐日模拟
        for i, (date_idx, row_prices) in enumerate(price_df.iterrows()):
            trade_date_str = date_idx.strftime("%Y%m%d")
            
            # 获取当日可用资产
            available_today = get_available_assets(date_idx)
            
            # 当日收益率（基于前一日收盘权重）
            if i == 0:
                daily_ret = 0.0
                asset_rets = {code: 0.0 for code in codes}
            else:
                prev_prices = price_df.iloc[i - 1]
                prev_date = price_df.index[i - 1]
                asset_rets = {}
                
                for code in codes:
                    prev_p = prev_prices[code]
                    curr_p = row_prices[code]
                    
                    if pd.isna(prev_p) or pd.isna(curr_p) or prev_p <= 0:
                        asset_rets[code] = 0.0
                        continue
                    
                    raw_ret = (curr_p / prev_p) - 1.0
                    
                    # 费率扣除：如果当日或前一日使用了指数替代，扣除ETF费率
                    is_substituted = (
                        substitution_mask_df.loc[date_idx, code] or 
                        substitution_mask_df.loc[prev_date, code]
                    )
                    if is_substituted and fee_dict.get(code, 0) > 0:
                        # 扣除年化费率 / 365
                        daily_fee = fee_dict[code] / 100.0 / 365.0
                        raw_ret -= daily_fee
                    
                    asset_rets[code] = raw_ret
                
                portfolio_ret = sum(
                    current_weights[codes.index(code)] * asset_rets[code] 
                    for code in codes
                )
                nav = nav * (1.0 + portfolio_ret)
                daily_ret = portfolio_ret

            # 记录当日市值权重
            if i == 0:
                market_weights = {code: float(current_weights[codes.index(code)]) for code in codes}
            else:
                market_weights = {}
                for code in codes:
                    if 1.0 + daily_ret > 1e-12:
                        mw = current_weights[codes.index(code)] * (1.0 + asset_rets[code]) / (1.0 + daily_ret)
                    else:
                        mw = current_weights[codes.index(code)]
                    market_weights[code] = float(mw)

            daily_records.append(BacktestDailyRecord(
                trade_date=trade_date_str,
                nav=round(nav, 6),
                daily_return=round(daily_ret, 6),
                asset_weights=market_weights,
                asset_returns={k: round(v, 6) for k, v in asset_rets.items()},
            ))

            # 更新 current_weights 为当日收盘后的市值权重
            if i > 0:
                current_weights = np.array([market_weights[code] for code in codes])

            # 再平衡判断
            current_date = date_idx.date()
            if current_date in rebalance_dates and i > 0:
                # 计算目标权重（仅对可用资产）
                lookback_end = date_idx
                lookback_start = lookback_end - pd.Timedelta(days=lookback)
                hist_returns = returns_df[returns_df.index >= lookback_start]
                
                available_now = get_available_assets(date_idx)
                target_weights_dict = calculate_target_weights(available_now, hist_returns)
                target_weights = np.array([target_weights_dict.get(code, 0.0) for code in codes])
                
                # 计算换手率
                turnover = 0.5 * np.sum(np.abs(target_weights - current_weights))
                
                rebalance_events.append(RebalanceEvent(
                    trade_date=trade_date_str,
                    target_weights={code: round(float(target_weights[codes.index(code)]), 6) for code in codes},
                    prev_weights={code: round(float(current_weights[codes.index(code)]), 6) for code in codes},
                    turnover=round(turnover, 6),
                ))
                
                current_weights = target_weights.copy()

        # 7. 计算绩效指标
        nav_series = pd.Series([r.nav for r in daily_records], index=pd.to_datetime([r.trade_date for r in daily_records]))
        ann_turnover = _calculate_turnover_annualized(rebalance_events, len(daily_records))
        metrics = calculate_metrics(nav_series, ann_turnover)

        return BacktestResult(
            request=request,
            metrics=metrics,
            daily_records=daily_records,
            rebalance_events=rebalance_events,
        )
