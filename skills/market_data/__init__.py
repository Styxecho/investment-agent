# skills/market_data/__init__.py
from .skill_definition import GetMarketDataSkill

# 实例化一个全局单例，供外部直接使用
get_market_data_skill = GetMarketDataSkill()

__all__ = ["get_market_data_skill", "GetMarketDataSkill"]