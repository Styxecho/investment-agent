# skills/portfolio/schema.py
"""
Portfolio Skill Data Schemas
基于 PyPortfolioOpt 理念：简单、实用、Pandas 友好。
定义输入输出数据契约，不包含业务逻辑。
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any
from datetime import date, datetime
from config.enums import AssetType
from config.types import DateStr


# ==============================================================================
# 0. 通用工具函数 (关键修改：返回 date 对象，而不是 str)
# ==============================================================================

def parse_date_input(v: Any) -> date:
    """
    将任意支持的日期输入转换为标准的 datetime.date 对象。

    输入支持：
    - date / datetime / pd.Timestamp
    - str: "YYYYMMDD"
    - str: "YYYY-MM-DD"

    输出：
    - datetime.date 对象 (符合 DateStr 的底层类型要求)
    """
    if v is None:
        raise ValueError("日期不能为空")

    # 1. 如果已经是 date 对象，直接返回
    if isinstance(v, date) and not isinstance(v, datetime):
        return v

    # 2. 处理 datetime 或 pd.Timestamp -> 转为 date
    if isinstance(v, datetime):
        return v.date()

    # 显式处理 Pandas Timestamp
    try:
        import pandas as pd
        if isinstance(v, pd.Timestamp):
            return v.date()
    except ImportError:
        pass

    # 3. 处理字符串
    if isinstance(v, str):
        v = v.strip()
        if not v:
            raise ValueError("日期字符串不能为空")

        # 情况 A: YYYYMMDD (紧凑格式)
        if len(v) == 8 and v.isdigit():
            return datetime.strptime(v, "%Y%m%d").date()

        # 情况 B: YYYY-MM-DD (ISO 格式)
        if len(v) == 10 and v[4] == '-' and v[7] == '-':
            return datetime.strptime(v, "%Y-%m-%d").date()

        raise ValueError(f"无法识别的日期格式: '{v}'. 期望: 'YYYYMMDD' 或 'YYYY-MM-DD'.")

    # 4. 兜底策略
    try:
        # 尝试转为字符串再解析
        str_v = str(v)
        if len(str_v) == 8 and str_v.isdigit():
            return datetime.strptime(str_v, "%Y%m%d").date()
        if '-' in str_v:
            return datetime.fromisoformat(str_v).date()
    except Exception:
        pass

    raise ValueError(f"不支持的日期类型: {type(v)}, 值: {v}")


# ==============================================================================
# 1. 输入模型 (Inputs)
# ==============================================================================

class Position(BaseModel):
    """单个资产的持仓头寸。"""
    # 类型注解严格使用 DateStr
    trade_date: DateStr = Field(..., description="持仓日期 (YYYYMMDD)")
    asset_code: str = Field(..., description="资产代码")
    asset_name: Optional[str] = Field(None, description="资产名称")
    asset_type: AssetType = Field(..., description="资产类型")
    volume: float = Field(..., description="持仓数量")
    cost_price: float = Field(..., description="持仓成本价")
    currency: str = "CNY"

    # 验证器：在赋值前将任意输入转换为 DateStr
    @field_validator('trade_date', mode='before')
    @classmethod
    def validate_trade_date(cls, v):
        return parse_date_input(v)


class MarketData(BaseModel):
    """
    单个资产的市场行情数据。
    注意：价格字段可能是缺失的 (None)，需要在 Calculator 中处理填充逻辑。
    """
    trade_date: DateStr = Field(..., description="交易日期 (YYYYMMDD)")
    asset_code: str = Field(..., description="资产代码")
    asset_type: AssetType = Field(..., description="资产类型")

    # 修正点 1: 类型改为 Optional[float]，允许为 None
    # 修正点 2: Field 默认值设为 None，表示非必填
    close_price: Optional[float] = Field(None, description="收盘价/单位净值")

    # 修正点 3: 确保 pre_close_price 也是 Optional (你之前可能已经对了，但检查一下)
    pre_close_price: Optional[float] = Field(None, description="昨日收盘价/单位净值 (用于计算日涨跌)")

    # 如果你需要保留验证器，保持不变
    @field_validator('trade_date', mode='before')
    @classmethod
    def validate_trade_date(cls, v):
        # 假设你已经在文件顶部定义了 parse_date_input 函数
        return parse_date_input(v)


# ==============================================================================
# 2. 输出模型 - 个股/基层级
# ==============================================================================

class AssetMetrics(BaseModel):
    """计算后的单资产指标。"""
    trade_date: DateStr = Field(..., description="计算日期 (YYYYMMDD)")
    asset_code: str
    asset_name: Optional[str] = None
    asset_type: AssetType = Field(..., description="资产类型")

    volume: float
    current_price: float
    cost_price: float
    market_value: float
    cost_value: float
    pnl_cumulated: float
    pnl_daily: float = Field(default=0.0)
    weight: float
    contribution_to_daily_pnl: float
    contribution_to_daily_return: float

    @field_validator('trade_date', mode='before')
    @classmethod
    def validate_trade_date(cls, v):
        return parse_date_input(v)


# ==============================================================================
# 3. 输出模型 - 组合层级
# ==============================================================================

class PortfolioSnapshot(BaseModel):
    """组合单日截面分析结果。"""
    trade_date: DateStr = Field(..., description="交易日期 (YYYYMMDD)")

    total_market_value: float
    total_cost_value: float
    total_pnl_cumulated: float
    daily_pnl: float = Field(default=0.0)
    daily_return: float = Field(default=0.0)
    net_value: float = Field(default=1.0)
    positions: List[AssetMetrics]
    currency: str = "CNY"
    position_count: int

    @field_validator('trade_date', mode='before')
    @classmethod
    def validate_trade_date(cls, v):
        return parse_date_input(v)


class PortfolioTimeSeries(BaseModel):
    """组合时序分析结果（多日）。"""
    snapshots: List[PortfolioSnapshot]
    start_date: DateStr = Field(..., description="开始日期 (YYYYMMDD)")
    end_date: DateStr = Field(..., description="结束日期 (YYYYMMDD)")
    total_days: int = Field(..., description="总天数")

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def validate_dates(cls, v):
        if v is None or v == "":
            # 如果允许空值，这里可能需要返回 None 或抛出错误，取决于 Field 定义
            # 如果 Field 没有 default，这里必须返回有效值或让 Pydantic 报错
            # 这里假设必须有值
            raise ValueError("日期不能为空")
        return parse_date_input(v)