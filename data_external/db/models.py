# data_external/db/models.py
from sqlalchemy import Column, String, Float, Integer, Date, UniqueConstraint
from .engine import Base

class StockDaily(Base):
    __tablename__ = "stock_daily"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    amount = Column(Float, nullable=True)
    __table_args__ = (UniqueConstraint('symbol', 'trade_date', name='uix_symbol_date'),)

class StockRealtime(Base):
    __tablename__ = "stock_realtime"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    update_time = Column(String(20), nullable=False)
    current_price = Column(Float, nullable=True)
    change_percent = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    # 其他字段略...