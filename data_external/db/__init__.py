# data_external/db/__init__.py
from .engine import init_db
from .repositories import MarketDataRepository

# 自动初始化
init_db()

__all__ = ["MarketDataRepository"]