# skills/macro_factor/filters/hp_filter.py
"""
单边HP滤波器实现
使用 statsmodels UnobservedComponents 实现单边（因果）HP滤波
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

from .base_filter import BaseFilter

logger = logging.getLogger(__name__)


class OneSidedHPFilter(BaseFilter):
    """
    单边HP滤波器
    
    特点：
    1. 无未来信息泄露（因果性）
    2. 前N个月使用双边HP作为预热期
    3. 之后使用UnobservedComponents进行单边递归估计
    
    参数：
        lamb: 平滑参数，月度数据标准值14400
        warmup_months: 预热期月数，默认18
    """
    
    def __init__(self, lamb: float = 14400, warmup_months: int = 18):
        self.lamb = lamb
        self.warmup_months = warmup_months
    
    @property
    def name(self) -> str:
        return "one_sided_hp"
    
    def fit_transform(self, series: pd.Series, **kwargs) -> Dict[str, pd.Series]:
        """
        执行单边HP滤波
        
        Args:
            series: 月度时间序列（DatetimeIndex）
            
        Returns:
            {'cycle': 周期项, 'trend': 趋势项}
        """
        n = len(series)
        trend = pd.Series(index=series.index, dtype=float)
        cycle = pd.Series(index=series.index, dtype=float)
        
        # 预热期：使用双边HP
        warmup = min(self.warmup_months, max(n // 4, 6))  # 至少6个月，不超过1/4数据
        
        if warmup > 0:
            try:
                from statsmodels.tsa.filters.hp_filter import hpfilter
                cycle_init, trend_init = hpfilter(series.iloc[:warmup], lamb=self.lamb)
                cycle.iloc[:warmup] = cycle_init.values
                trend.iloc[:warmup] = trend_init.values
            except Exception as e:
                logger.warning(f"预热期HP滤波失败: {e}，使用简单均值代替")
                mean_val = series.iloc[:warmup].mean()
                trend.iloc[:warmup] = mean_val
                cycle.iloc[:warmup] = series.iloc[:warmup].values - mean_val
        
        # 单边递归期：使用UnobservedComponents
        if n > warmup:
            try:
                from statsmodels.tsa.statespace.structural import UnobservedComponents
                
                for t in range(warmup, n):
                    # 只用0:t+1的数据
                    sub_series = series.iloc[:t+1]
                    
                    # 拟合local linear trend模型
                    model = UnobservedComponents(
                        sub_series,
                        level='local linear trend',
                        cycle=True,
                        cycle_period_bounds=(6, 96)
                    )
                    
                    try:
                        result = model.fit(disp=False)
                        # 提取最后一期的趋势和周期
                        trend.iloc[t] = result.level.iloc[-1]
                        cycle.iloc[t] = result.cycle.iloc[-1]
                    except Exception as e:
                        # 如果拟合失败，使用简单平滑
                        logger.debug(f"t={t} 模型拟合失败，使用EMA代替: {e}")
                        ema_trend = sub_series.ewm(span=12, adjust=False).mean().iloc[-1]
                        trend.iloc[t] = ema_trend
                        cycle.iloc[t] = sub_series.iloc[-1] - ema_trend
                        
            except ImportError:
                logger.warning("statsmodels未安装，使用EMA代替HP滤波")
                trend = series.ewm(span=12, adjust=False).mean()
                cycle = series - trend
        
        return {
            'cycle': cycle,
            'trend': trend
        }
    
    def get_params(self) -> Dict[str, Any]:
        return {
            "lamb": self.lamb,
            "warmup_months": self.warmup_months
        }


class TwoSidedHPFilter(BaseFilter):
    """
    双边HP滤波器（仅用于历史复盘/debug）
    注意：非因果，有未来信息泄露，不适合实时应用
    """
    
    def __init__(self, lamb: float = 14400):
        self.lamb = lamb
    
    @property
    def name(self) -> str:
        return "two_sided_hp"
    
    def fit_transform(self, series: pd.Series, **kwargs) -> Dict[str, pd.Series]:
        from statsmodels.tsa.filters.hp_filter import hpfilter
        cycle, trend = hpfilter(series, lamb=self.lamb)
        return {
            'cycle': cycle,
            'trend': trend
        }
    
    def get_params(self) -> Dict[str, Any]:
        return {"lamb": self.lamb}
