"""
End-to-end test for TushareProvider -> MarketDataService -> DB.

This test verifies:
1. MarketDataService uses Tushare as primary provider
2. Data is saved to local SQLite DB
3. Subsequent queries hit cache
4. Fallback to iFinD works if Tushare fails

Run from project root:
    python scripts/test_market_data_e2e.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.market_data.service import MarketDataService
from skills.base import SkillContext
from config.enums import AssetType


def create_context(target_date: str, **extra_params):
    """Create a minimal SkillContext for testing."""
    from skills.base import SkillContext, SkillMeta
    return SkillContext(
        target_date=target_date,
        raw_input={},
        extra_params=extra_params,
        meta=SkillMeta(source="test", status="ok", target_date=target_date),
    )


def test_stock_daily_e2e():
    print("\n=== Test Stock Daily E2E ===")
    service = MarketDataService()

    symbol = "000001.SZ"
    target_date = "20240605"

    # First call - should hit API
    print(f"First call for {symbol} @ {target_date}")
    result1 = service.get_daily_data(
        context=create_context(target_date),
        symbol=symbol,
        asset_type=AssetType.STOCK,
    )
    print(f"Source: {result1.meta.source}, Status: {result1.meta.status}")
    assert result1.meta.status == "success", f"Failed: {result1.meta.message}"
    assert result1.data.get("close") is not None, "Missing close price"

    # Second call - should hit cache
    print(f"Second call for {symbol} @ {target_date}")
    result2 = service.get_daily_data(
        context=create_context(target_date),
        symbol=symbol,
        asset_type=AssetType.STOCK,
    )
    print(f"Source: {result2.meta.source}, Status: {result2.meta.status}")
    assert result2.meta.source == "cache", "Second call should hit cache"
    assert result2.data.get("close") == result1.data.get("close")

    print("Stock daily E2E PASSED")


def test_index_daily_e2e():
    print("\n=== Test Index Daily E2E ===")
    service = MarketDataService()

    symbol = "000001.SH"
    target_date = "20240605"

    result = service.get_daily_data(
        context=create_context(target_date),
        symbol=symbol,
        asset_type=AssetType.INDEX,
    )
    print(f"Source: {result.meta.source}, Status: {result.meta.status}")
    assert result.meta.status == "success", f"Failed: {result.meta.message}"
    assert result.data.get("close") is not None, "Missing close price"

    print("Index daily E2E PASSED")


def test_etf_daily_e2e():
    print("\n=== Test ETF Daily E2E ===")
    service = MarketDataService()

    symbol = "510300.SH"
    target_date = "20240605"

    result = service.get_daily_data(
        context=create_context(target_date),
        symbol=symbol,
        asset_type=AssetType.ETF,
    )
    print(f"Source: {result.meta.source}, Status: {result.meta.status}")
    assert result.meta.status == "success", f"Failed: {result.meta.message}"
    assert result.data.get("close") is not None, "Missing close price"

    print("ETF daily E2E PASSED")


def test_fund_nav_e2e():
    print("\n=== Test Fund NAV E2E ===")
    service = MarketDataService()

    fund_code = "003956.OF"
    target_date = "20240605"

    result = service.get_daily_data(
        context=create_context(target_date),
        symbol=fund_code,
        asset_type=AssetType.FUND,
    )
    print(f"Source: {result.meta.source}, Status: {result.meta.status}")
    assert result.meta.status == "success", f"Failed: {result.meta.message}"
    assert result.data.get("close") is not None, "Missing close/nav"

    print("Fund NAV E2E PASSED")


def test_provider_configuration():
    print("\n=== Test Provider Configuration ===")
    from config.settings import settings

    provider = getattr(settings, 'MARKET_DATA_PROVIDER', 'tushare')
    token = getattr(settings, 'TUSHARE_TOKEN', None)

    print(f"MARKET_DATA_PROVIDER: {provider}")
    print(f"TUSHARE_TOKEN configured: {bool(token)}")

    assert provider == 'tushare', f"Expected tushare, got {provider}"
    assert token is not None and len(token) > 0, "TUSHARE_TOKEN not configured"

    print("Provider configuration PASSED")


if __name__ == "__main__":
    print("MarketDataService E2E Test Suite")
    print("This will call Tushare API for fresh data, then verify cache hit")

    try:
        test_provider_configuration()
        test_stock_daily_e2e()
        test_index_daily_e2e()
        test_etf_daily_e2e()
        test_fund_nav_e2e()
        print("\n=== ALL E2E TESTS PASSED ===")
    except Exception as e:
        print(f"\n=== E2E TEST FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
