# skills/macro_factor/schema.py
"""
宏观因子数据模型
使用Pydantic定义数据契约
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Any
from datetime import datetime


class FactorValue(BaseModel):
    """单个因子值"""
    indicator_code: str = Field(..., description="指标代码")
    publish_date: str = Field(..., description="发布日期 YYYYMMDD")
    factor_type: str = Field(..., description="因子类型: level/change")
    factor_value: Optional[float] = Field(None, description="因子值(Z-score)")
    cycle_value: Optional[float] = Field(None, description="周期项")
    trend_value: Optional[float] = Field(None, description="趋势项")
    is_winsorized: bool = Field(False, description="是否被截断")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y%m%d")
        }


class FactorConfig(BaseModel):
    """因子计算配置"""
    indicator_code: str
    filter_type: str = "one_sided_hp"
    filter_params: Dict[str, Any] = Field(default_factory=lambda: {"lamb": 14400})
    level_window: int = 36
    change_window: int = 48
    winsorize_threshold: float = 3.0
    min_periods_for_zscore: int = 12
    hp_warmup_months: int = 18
    is_active: bool = True


class FactorResult(BaseModel):
    """因子计算结果"""
    indicator_code: str
    date: str
    factors: Dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="因子值字典 {level: x, change: y}"
    )
    cycle: Optional[float] = None
    trend: Optional[float] = None
    
    
class FactorMatrix(BaseModel):
    """多指标因子矩阵（某一日期的所有因子）"""
    date: str
    factors: Dict[str, Dict[str, Optional[float]]] = Field(
        default_factory=dict,
        description="{indicator_code: {level: x, change: y}}"
    )
    
    def get_factor(self, indicator_code: str, factor_type: str = "level") -> Optional[float]:
        """获取指定因子的值"""
        if indicator_code in self.factors:
            return self.factors[indicator_code].get(factor_type)
        return None
    
    def get_category_factors(self, category_map: Dict[str, str]) -> Dict[str, List[float]]:
        """
        按类别聚合因子
        category_map: {indicator_code: category}
        返回: {category: [factor_values]}
        """
        result = {}
        for code, cat in category_map.items():
            val = self.get_factor(code)
            if val is not None:
                if cat not in result:
                    result[cat] = []
                result[cat].append(val)
        return result


class ComputeRequest(BaseModel):
    """批量计算请求"""
    start_date: str = Field(..., pattern=r"^\d{8}$")
    end_date: str = Field(..., pattern=r"^\d{8}$")
    indicator_codes: Optional[List[str]] = Field(None, description="为空则处理所有活跃指标")
    factor_types: List[str] = Field(default=["level", "change"])


class QueryRequest(BaseModel):
    """查询请求"""
    target_date: str = Field(..., pattern=r"^\d{8}$")
    indicator_codes: Optional[List[str]] = None
    factor_types: List[str] = Field(default=["level"])
