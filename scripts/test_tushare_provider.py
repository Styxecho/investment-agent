"""
Test script for TushareProvider.

Before running:
1. Add to your .env file:
   TUSHARE_TOKEN=your_real_token
   MARKET_DATA_PROVIDER=tushare
2. Run this script from project root:
   python scripts/test_tushare_provider.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.market_data.provider.tushare_provider import tushare_provider
from config.enums import AssetType


def test_stock_daily():
    print("\n=== Test Stock Daily ===")
    df = tushare_provider.fetch_history(
        symbol="000001.SZ",
        start_date="20240601",
        end_date="20240610",
        asset_type=AssetType.STOCK,
    )
    print(f"Rows: {len(df)}")
    print(df.head())
    assert not df.empty, "Stock daily data should not be empty"
    assert "close" in df.columns, "Missing close column"
    assert "pre_close" in df.columns, "Missing pre_close column"
    print("Stock daily test PASSED")


def test_index_daily():
    print("\n=== Test Index Daily ===")
    df = tushare_provider.fetch_history(
        symbol="000001.SH",
        start_date="20240601",
        end_date="20240610",
        asset_type=AssetType.INDEX,
    )
    print(f"Rows: {len(df)}")
    print(df.head())
    assert not df.empty, "Index daily data should not be empty"
    assert "close" in df.columns, "Missing close column"
    print("Index daily test PASSED")


def test_etf_daily():
    print("\n=== Test ETF Daily ===")
    df = tushare_provider.fetch_history(
        symbol="510300.SH",
        start_date="20240601",
        end_date="20240610",
        asset_type=AssetType.ETF,
    )
    print(f"Rows: {len(df)}")
    print(df.head())
    assert not df.empty, "ETF daily data should not be empty"
    assert "close" in df.columns, "Missing close column"
    print("ETF daily test PASSED")


def test_fund_nav():
    print("\n=== Test Fund NAV ===")
    df = tushare_provider.fetch_fund_nav(
        fund_code="003956.OF",
        start_date="20240601",
        end_date="20240610",
    )
    print(f"Rows: {len(df)}")
    print(df.head())
    assert not df.empty, "Fund NAV data should not be empty"
    assert "unit_nav" in df.columns, "Missing unit_nav column"
    print("Fund NAV test PASSED")


def test_batch_symbols():
    print("\n=== Test Batch Symbols ===")
    df = tushare_provider.fetch_history(
        symbol=["000001.SZ", "000002.SZ"],
        start_date="20240601",
        end_date="20240610",
        asset_type=AssetType.STOCK,
    )
    print(f"Rows: {len(df)}")
    print(df["scrt_code"].value_counts())
    assert not df.empty, "Batch data should not be empty"
    print("Batch symbols test PASSED")


if __name__ == "__main__":
    print("TushareProvider Test Suite")
    print("Make sure TUSHARE_TOKEN is set in your .env file")

    try:
        test_stock_daily()
        test_index_daily()
        test_etf_daily()
        test_fund_nav()
        test_batch_symbols()
        print("\n=== ALL TESTS PASSED ===")
    except Exception as e:
        print(f"\n=== TEST FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
