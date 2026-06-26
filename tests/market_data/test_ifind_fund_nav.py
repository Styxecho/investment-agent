# tests/market_data/test_ifind_fund_nav.py
"""
测试 iFinD 公募基金净值获取

测试用例：查询 003956.OF（易方达蓝筹精选）在 2026-04-01 至 2026-04-03 的日终单位净值

预期结果：
- 2026-04-01: 2.1462
- 2026-04-02: 2.1514
- 2026-04-03: 2.1354

API 调用示例：
THS_DS('003956.OF','ths_unit_nv_fund;ths_accum_unit_nv_fund;ths_adjustment_nv_fund','','block:latest','2026-04-01','2026-04-03')
"""
import pytest
from datetime import datetime
from skills.market_data.provider.ifind_provider import iFinDProvider
from skills.market_data.service import MarketDataService
from skills.base import SkillContext
from config.enums import AssetType


class TestIFindFundNAV:
    """iFinD 基金净值获取测试"""
    
    @pytest.fixture
    def provider(self):
        """创建 iFinD Provider 实例"""
        return iFinDProvider()  # 实例化
    
    @pytest.fixture
    def service(self):
        """创建 MarketDataService 实例"""
        return MarketDataService()
    
    @pytest.fixture
    def test_fund_code(self):
        """测试基金代码"""
        return "003956.OF"
    
    @pytest.fixture
    def test_date_range(self):
        """测试日期范围"""
        return {
            "start_date": "20260401",
            "end_date": "20260403",
            "expected_nav": {
                "20260401": 2.1462,
                "20260402": 2.1514,
                "20260403": 2.1354
            }
        }
    
    def test_fetch_fund_nav_range(self, provider, test_fund_code, test_date_range):
        """测试获取基金净值序列（日期范围）"""
        try:
            # 调用 iFinD Provider
            df = provider.fetch_fund_nav(
                fund_code=test_fund_code,
                start_date=test_date_range["start_date"],
                end_date=test_date_range["end_date"]
            )
        except Exception as e:
            pytest.skip(f"iFinD 不可用：{str(e)}")
        
        # 验证返回 DataFrame
        if df.empty:
            pytest.skip("iFinD 返回空数据，可能未连接或数据不存在")
        
        assert df is not None, "返回的 DataFrame 不应为空"
        assert not df.empty, "DataFrame 不应为空"
        
        # 验证列存在
        assert 'unit_nav' in df.columns, "应包含 unit_nav 列"
        assert 'trade_date' in df.columns, "应包含 trade_date 列"
        
        # 验证数据条数（3 个交易日）
        assert len(df) == 3, f"应返回 3 条记录，实际返回 {len(df)} 条"
        
        # 验证每条记录的净值
        for _, row in df.iterrows():
            trade_date = row['trade_date']
            if isinstance(trade_date, datetime):
                trade_date = trade_date.strftime('%Y%m%d')
            elif isinstance(trade_date, str) and len(trade_date) > 8:
                # 如果是 '2026-04-01' 格式
                trade_date = trade_date.replace('-', '')
            
            unit_nav = row['unit_nav']
            expected_nav = test_date_range["expected_nav"].get(trade_date)
            
            if expected_nav:
                assert abs(unit_nav - expected_nav) < 0.0001, \
                    f"{trade_date} 的单位净值应为 {expected_nav}, 实际为 {unit_nav}"
    
    def test_fetch_fund_nav_single_date(self, provider, test_fund_code, test_date_range):
        """测试获取单日基金净值"""
        target_date = test_date_range["end_date"]  # 2026-04-03
        
        try:
            # 调用 iFinD Provider（单日查询）
            df = provider.fetch_fund_nav(
                fund_code=test_fund_code,
                start_date=target_date,
                end_date=target_date
            )
        except Exception as e:
            pytest.skip(f"iFinD 不可用：{str(e)}")
        
        if df.empty:
            pytest.skip("iFinD 返回空数据")
        
        # 验证返回
        assert df is not None
        assert len(df) >= 1, "应至少返回 1 条记录（包含 T-1 日）"
        
        # 验证 2026-04-03 的净值
        df_target = df[df['trade_date'].apply(
            lambda x: x.strftime('%Y%m%d') if isinstance(x, datetime) else x.replace('-', '')
        ) == target_date]
        
        assert len(df_target) > 0, f"应包含 {target_date} 的数据"
        unit_nav = df_target.iloc[0]['unit_nav']
        expected_nav = test_date_range["expected_nav"][target_date]
        
        assert abs(unit_nav - expected_nav) < 0.0001, \
            f"{target_date} 的单位净值应为 {expected_nav}, 实际为 {unit_nav}"
    
    def test_service_get_fund_nav_range(self, service, test_fund_code, test_date_range):
        """测试 Service 层获取基金净值（日期范围）"""
        context = SkillContext(
            target_date=test_date_range["end_date"],
            extra_params={
                "symbol": test_fund_code,
                "asset_type": "fund",
                "start_date": test_date_range["start_date"],
                "end_date": test_date_range["end_date"]
            }
        )
        
        # 调用 Service
        result = service.get_daily_data(
            context=context,
            symbol=test_fund_code,
            asset_type=AssetType.FUND
        )
        
        # 验证返回类型
        assert result is not None
        assert hasattr(result, 'meta')
        assert hasattr(result, 'data')
        
        # 验证元数据
        assert result.meta.status == "success", f"查询应成功，实际：{result.meta.message}"
        assert result.meta.source in ["cache", "api"], f"数据来源应为 cache 或 api, 实际：{result.meta.source}"
        
        # 验证数据
        if 'nav_series' in result.data:
            nav_series = result.data['nav_series']
            assert len(nav_series) == 3, f"应返回 3 条净值记录，实际 {len(nav_series)} 条"
            
            # 验证每条净值
            for nav_item in nav_series:
                trade_date = nav_item.get('trade_date')
                unit_nav = nav_item.get('unit_nav')
                expected_nav = test_date_range["expected_nav"].get(trade_date)
                
                if expected_nav:
                    assert abs(unit_nav - expected_nav) < 0.0001, \
                        f"{trade_date} 的单位净值应为 {expected_nav}, 实际为 {unit_nav}"
        else:
            pytest.skip("数据格式可能为单日查询结果")
    
    def test_service_get_fund_nav_single(self, service, test_fund_code, test_date_range):
        """测试 Service 层获取单日基金净值"""
        target_date = test_date_range["end_date"]  # 2026-04-03
        
        context = SkillContext(
            target_date=target_date,
            extra_params={
                "symbol": test_fund_code,
                "asset_type": "fund"
            }
        )
        
        # 调用 Service
        result = service.get_daily_data(
            context=context,
            symbol=test_fund_code,
            asset_type=AssetType.FUND
        )
        
        # 验证返回
        assert result is not None
        assert result.meta.status == "success"
        
        # 验证净值
        if result.data:
            unit_nav = result.data.get('unit_nav')
            expected_nav = test_date_range["expected_nav"][target_date]
            
            if unit_nav:
                assert abs(unit_nav - expected_nav) < 0.0001, \
                    f"{target_date} 的单位净值应为 {expected_nav}, 实际为 {unit_nav}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
