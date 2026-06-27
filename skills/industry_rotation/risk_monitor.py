# skills/industry_rotation/risk_monitor.py
"""
Phase 2.5 持仓期风险监控引擎

职责：
1. 日频快速触发（无豁免）：极端跌幅平仓
2. 周频防线（首周新仓豁免）：趋势结构、MACD动能、拥挤度

严格遵循 docs/roadmap/Phase_2.4&2.5_Methodology_Summary.md V5.0。
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    """风险监控参数"""
    # 日频快速触发
    daily_drop_limit: float = 0.07          # 单日跌幅 > 7% 平仓
    consecutive_drop_days: int = 3          # 连续N日跌幅 > 2%
    consecutive_drop_daily: float = 0.02    # 每日跌幅阈值
    consecutive_drop_cumulative: float = 0.08  # 累计跌幅阈值
    
    # 周频防线
    ma_short: int = 20
    ma_mid: int = 60
    
    # 拥挤防线
    crowding_window_short: int = 5
    crowding_window_long: int = 60
    crowding_threshold: float = 1.5
    crowding_consecutive_weeks: int = 4
    crowding_reduce_ratio: float = 0.5


class RiskMonitor:
    """持仓期风险监控引擎"""
    
    def __init__(self, config: Optional[RiskConfig] = None):
        self.cfg = config or RiskConfig()
    
    def check_daily(
        self,
        position: Dict[str, Any],
        df_daily: pd.DataFrame,
        current_date: str
    ) -> Optional[str]:
        """
        日频快速触发检查
        
        Args:
            position: 持仓项，含 index_code / trade_code / current_weight
            df_daily: 该行业日频数据（到 current_date 为止）
            current_date: 当前日期 YYYYMMDD
        
        Returns:
            触发信号，未触发返回 None
        """
        code = position.get('trade_code', position['index_code'])
        df = df_daily[df_daily['trade_date'] <= pd.Timestamp(current_date)].copy()
        if len(df) < 2:
            return None
        
        df = df.sort_values('trade_date')
        
        # 统一列名
        if 'close_price' in df.columns:
            df['close'] = df['close_price']
        if 'pre_close_price' in df.columns and 'pre_close' not in df.columns:
            df['pre_close'] = df['pre_close_price']
        
        latest = df.iloc[-1]
        
        # 计算当日收益率
        daily_return = latest['close'] / latest['pre_close'] - 1 if latest['pre_close'] > 0 else 0
        
        # 条件1：单日跌幅 > 7%
        if daily_return < -self.cfg.daily_drop_limit:
            logger.warning(f"[{code}] 日频触发：单日跌幅 {daily_return:.2%} > {self.cfg.daily_drop_limit:.2%}")
            return '日频-单日大跌平仓'
        
        # 条件2：连续3日每日跌幅 > 2% 且累计 > 8%
        if len(df) >= self.cfg.consecutive_drop_days:
            recent = df.tail(self.cfg.consecutive_drop_days)
            daily_rets = recent['close'].pct_change().dropna()
            if len(daily_rets) == self.cfg.consecutive_drop_days - 1:
                if all(daily_rets < -self.cfg.consecutive_drop_daily):
                    cumulative = (recent['close'].iloc[-1] / recent['close'].iloc[0] - 1)
                    if cumulative < -self.cfg.consecutive_drop_cumulative:
                        logger.warning(
                            f"[{code}] 日频触发：连续{self.cfg.consecutive_drop_days}日下跌，"
                            f"累计 {cumulative:.2%}"
                        )
                        return '日频-连续阴跌平仓'
        
        return None
    
    def check_weekly(
        self,
        position: Dict[str, Any],
        df_daily: pd.DataFrame,
        current_date: str,
        weeks_held: int,
        cross_sectional: Optional[pd.DataFrame] = None
    ) -> Optional[Tuple[str, float]]:
        """
        周频防线检查（首周新仓豁免）
        
        Args:
            position: 持仓项
            df_daily: 该行业日频数据
            current_date: 当前日期 YYYYMMDD
            weeks_held: 已持仓周数（首周=0）
            cross_sectional: 当日全市场截面数据，用于拥挤度Z-score
        
        Returns:
            (信号, 目标权重比例)，未触发返回 None
        """
        # 首周豁免
        if weeks_held <= 0:
            return None
        
        code = position.get('trade_code', position['index_code'])
        df = df_daily[df_daily['trade_date'] <= pd.Timestamp(current_date)].copy()
        if len(df) < self.cfg.ma_mid:
            return None
        
        df = df.sort_values('trade_date')
        
        # 统一列名
        if 'close_price' in df.columns:
            df['close'] = df['close_price']
        
        latest = df.iloc[-1]
        
        # 1. 趋势结构防线：MA20 < MA60
        if latest['ma20'] < latest['ma60']:
            logger.warning(f"[{code}] 周频触发：MA20 < MA60，平仓")
            return ('周频-趋势死叉平仓', 0.0)
        
        # 2. 动能防线：MACD死叉 且 DIF < 0
        if latest['macd_dif'] < latest['macd_dea'] and latest['macd_dif'] < 0:
            logger.warning(f"[{code}] 周频触发：MACD死叉且DIF<0，平仓")
            return ('周频-动能衰竭平仓', 0.0)
        
        # 3. 拥挤防线
        crowding_score = self._calculate_crowding(df, cross_sectional)
        if crowding_score is not None and crowding_score > self.cfg.crowding_threshold:
            logger.warning(f"[{code}] 周频触发：拥挤度 {crowding_score:.2f} > {self.cfg.crowding_threshold}")
            # 减仓50%
            return ('周频-拥挤减仓', position.get('current_weight', 0) * (1 - self.cfg.crowding_reduce_ratio))
        
        return None
    
    def _calculate_crowding(
        self,
        df_industry: pd.DataFrame,
        cross_sectional: Optional[pd.DataFrame] = None
    ) -> Optional[float]:
        """
        计算拥挤度得分
        
        Crowding_score = 0.5 * Z(相对成交额) + 0.5 * Z(成交额占比)
        - 相对成交额 = 过去5日日均成交额 / 过去60日日均成交额
        - 成交额占比 = 行业过去5日日均成交额 / 全市场过去5日日均成交额
        
        若无 cross_sectional，仅使用相对成交额（系数仍为1）
        """
        df = df_industry.copy().sort_values('trade_date')
        if len(df) < self.cfg.crowding_window_long:
            return None
        
        recent = df.tail(self.cfg.crowding_window_short)
        long_term = df.tail(self.cfg.crowding_window_long)
        
        avg_amount_short = recent['amount'].mean()
        avg_amount_long = long_term['amount'].mean()
        
        if avg_amount_long == 0:
            return None
        
        relative_amount = avg_amount_short / avg_amount_long
        
        # 如果无截面数据，仅使用相对成交额
        if cross_sectional is None or cross_sectional.empty:
            return relative_amount - 1.0  # 简单偏离
        
        # 截面Z-score
        cs = cross_sectional.copy()
        cs['relative_amount'] = cs['amount_short'] / cs['amount_long']
        cs['amount_share'] = cs['amount_short'] / cs['amount_short'].sum()
        
        z_relative = self._zscore(cs['relative_amount'])
        z_share = self._zscore(cs['amount_share'])
        
        # 找到当前行业的 Z-score
        current_code = df_industry['index_code'].iloc[-1] if 'index_code' in df_industry.columns else None
        if current_code and current_code in cs.index:
            z_rel = z_relative.loc[current_code]
            z_sh = z_share.loc[current_code]
        else:
            #  fallback：用相对成交额近似
            z_rel = (relative_amount - cs['relative_amount'].mean()) / cs['relative_amount'].std() if cs['relative_amount'].std() > 0 else 0
            z_sh = 0
        
        return 0.5 * z_rel + 0.5 * z_sh
    
    @staticmethod
    def _zscore(s: pd.Series) -> pd.Series:
        """计算Z-score，标准差为0时返回0"""
        std = s.std()
        if std == 0 or pd.isna(std):
            return pd.Series(0, index=s.index)
        return (s - s.mean()) / std
    
    def is_week_end(self, current_date: str, df_daily: pd.DataFrame) -> bool:
        """
        判断当前日期是否为一周的最后一个交易日
        
        简单规则：本周下一个交易日不在数据中（下周一无数据）或本周已跨自然周
        实际回测中由 BacktestEngine 按每周最后一个交易日调用
        """
        current = pd.Timestamp(current_date)
        future = df_daily[df_daily['trade_date'] > current]
        if future.empty:
            return True
        
        next_date = future.iloc[0]['trade_date']
        # 如果下一个交易日跨自然周，则当前是本周最后一个交易日
        return next_date.week > current.week or next_date.year > current.year
