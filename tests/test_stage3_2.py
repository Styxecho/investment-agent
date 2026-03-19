# tests/test_ifind_integration.py

from config.enums import AssetType
from skills.market_data.service import market_data_service

def test_stock_data():
    # 使用枚举传递资产类型，安全且智能提示
    df = market_data_service.get_daily_data(
        symbol="000001.SZ",
        start_date="20260316",
        end_date="20260316",
        asset_type=AssetType.STOCK
    )
    print(df.head())

def test_etf_data():
    # 轻松切换资产类型
    df = market_data_service.get_daily_data(
        symbol="510300.SH",
        start_date="20260316",
        end_date="20260316",
        asset_type=AssetType.ETF
    )
    print(df.head())

if __name__ == "__main__":
    try:
        test_stock_data()
        test_etf_data()
    finally:
        # 即使这里不手动调 disconnect，atexit 也会在脚本结束时自动调用
        print("测试完成，等待自动清理...")