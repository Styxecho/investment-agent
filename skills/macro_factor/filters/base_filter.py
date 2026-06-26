# skills/macro_factor/filters/base_filter.py
"""
滤波器抽象基类
所有宏观因子滤波器必须继承此类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd


class BaseFilter(ABC):
    """宏观因子滤波器抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """滤波器唯一标识名称"""
        pass
    
    @abstractmethod
    def fit_transform(self, series: pd.Series, **kwargs) -> Dict[str, pd.Series]:
        """
        对时间序列进行滤波分解
        
        Args:
            series: 输入时间序列（月度频率，DatetimeIndex）
            **kwargs: 额外参数
            
        Returns:
            {
                'cycle': 周期项（去趋势后的波动成分）,
                'trend': 趋势项（长期趋势）
            }
        """
        pass
    
    @abstractmethod
    def get_params(self) -> Dict[str, Any]:
        """返回当前参数，用于持久化到数据库"""
        pass
