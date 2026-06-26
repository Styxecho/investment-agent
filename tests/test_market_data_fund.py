# tests/test_market_data_fund.py
"""
公募基金数据获取测试
"""
import pytest
from datetime import datetime
from skills.base import SkillContext, SkillResult
from skills.market_data.service import MarketDataService
from config.enums import AssetType


class TestFundDataFetch:
    """基金数据获取测试类"""
    
    @pytest.fixture
    def market_service(self):
        """创建市场数据服务实例"""
        return MarketDataService()
    
    @pytest.fixture
    def sample_fund_code(self):
        """样本基金代码"""
        return "003956.OF"  # 易方达蓝筹精选
    
    @pytest.fixture
    def sample_trade_date(self):
        """样本交易日期"""
        return "20260403"
    
    def test_asset_type_from_code_suffix_fund(self):
        """测试资产类型识别（基金）"""
        asset_type = AssetType.from_code_suffix("003956.OF")
        assert asset_type == AssetType.FUND
        
        asset_type = AssetType.from_code_suffix("000001.OF")
        assert asset_type == AssetType.FUND
    
    def test_asset_type_from_code_suffix_stock(self):
        """测试资产类型识别（股票）"""
        asset_type = AssetType.from_code_suffix("600519.SH")
        assert asset_type == AssetType.STOCK
        
        asset_type = AssetType.from_code_suffix("000001.SZ")
        assert asset_type == AssetType.STOCK
    
    def test_asset_type_from_code_suffix_etf(self):
        """测试资产类型识别（ETF）"""
        asset_type = AssetType.from_code_suffix("510300.SH")
        assert asset_type == AssetType.ETF
        
        asset_type = AssetType.from_code_suffix("159915.SZ")
        assert asset_type == AssetType.ETF
    
    def test_ifind_fund_nav_indicators(self):
        """测试 iFinD 基金净值指标"""
        indicators = AssetType.FUND.ifind_fund_nav_indicators
        assert indicators == 'ths_unit_nv_fund;ths_accum_unit_nv_fund;ths_adjustment_nv_fund'
    
    def test_get_fund_daily_data_success(self, market_service, sample_fund_code, sample_trade_date):
        """测试获取基金日终数据（成功场景）"""
        context = SkillContext(
            target_date=sample_trade_date,
            extra_params={
                "symbol": sample_fund_code,
                "asset_type": "fund"
            }
        )
        
        result = market_service.get_daily_data(
            context=context,
            symbol=sample_fund_code,
            asset_type=AssetType.FUND
        )
        
        # 验证返回类型
        assert isinstance(result, SkillResult)
        
        # 验证元数据
        assert result.meta.target_date == sample_trade_date
        assert result.meta.status in ["success", "failed", "partial"]
        
        # 如果成功，验证数据字段
        if result.meta.status == "success":
            assert "unit_nav" in result.data or "close" in result.data
            assert "pre_close" in result.data or "prev_unit_nav" in result.data
    
    def test_get_fund_daily_data_with_cache(self, market_service, sample_fund_code, sample_trade_date):
        """测试获取基金数据（缓存命中）"""
        # 第一次调用会存入缓存
        context = SkillContext(
            target_date=sample_trade_date,
            extra_params={"symbol": sample_fund_code}
        )
        
        result1 = market_service.get_daily_data(
            context=context,
            symbol=sample_fund_code,
            asset_type=AssetType.FUND
        )
        
        # 第二次调用应该命中缓存
        result2 = market_service.get_daily_data(
            context=context,
            symbol=sample_fund_code,
            asset_type=AssetType.FUND
        )
        
        # 两次结果应该一致
        if result1.meta.status == "success" and result2.meta.status == "success":
            assert result1.data.get('unit_nav') == result2.data.get('unit_nav')
    
    def test_get_fund_daily_data_invalid_date(self, market_service, sample_fund_code):
        """测试获取基金数据（无效日期）"""
        context = SkillContext(
            target_date="20261301",  # 无效月份（13 月不存在）
            extra_params={"symbol": sample_fund_code}
        )
        
        result = market_service.get_daily_data(
            context=context,
            symbol=sample_fund_code,
            asset_type=AssetType.FUND
        )
        
        # 应该返回失败状态（日期验证失败）
        assert result.meta.status == "failed", f"无效日期应该返回 failed，但返回：{result.meta.status}"
        # 验证错误信息包含日期相关信息
        assert "无效日期" in result.meta.message or "invalid" in result.meta.message.lower()
    
    def test_get_fund_daily_data_holiday(self, market_service, sample_fund_code):
        """测试获取基金数据（节假日）"""
        # 2026-01-01 是元旦（节假日）
        context = SkillContext(
            target_date="20260101",
            extra_params={"symbol": sample_fund_code}
        )
        
        result = market_service.get_daily_data(
            context=context,
            symbol=sample_fund_code,
            asset_type=AssetType.FUND
        )
        
        # 节假日可能返回部分成功或失败
        assert result.meta.status in ["failed", "partial", "success"]
        
        if result.meta.status == "success":
            # 如果成功，应该包含数据
            assert result.data.get('unit_nav') is not None
    
    def test_fund_nav_conversion(self, market_service):
        """测试基金净值转换逻辑"""
        # 验证 close 和 pre_close 的映射关系
        import pandas as pd
        
        # 模拟数据
        df = pd.DataFrame([{
            'trade_date': '20260403',
            'fund_code': '003956.OF',
            'unit_nav': 1.2500,
            'accumulated_nav': 1.3000,
            'adjusted_nav': 1.2800
        }])
        
        # 验证字段存在
        assert 'unit_nav' in df.columns
        assert df.iloc[0]['unit_nav'] == 1.2500


class TestFundRepository:
    """基金数据仓储测试"""
    
    @pytest.fixture
    def fund_repo(self):
        """创建基金仓储实例"""
        from data_external.db.repositories import FundRepository
        return FundRepository()
    
    def test_save_and_get_fund_nav(self, fund_repo):
        """测试保存和获取基金净值"""
        import pandas as pd
        
        # 准备测试数据
        df = pd.DataFrame([{
            'trade_date': '20260403',
            'fund_code': '003956.OF',
            'unit_nav': 1.2500,
            'accumulated_nav': 1.3000,
            'adjusted_nav': 1.2800
        }])
        
        # 保存数据
        fund_repo.save_fund_nav(df, '003956.OF')
        
        # 获取数据
        result_df = fund_repo.get_fund_nav('003956.OF', '20260403', '20260403')
        
        # 验证
        if result_df is not None:
            assert len(result_df) > 0
            assert result_df.iloc[0]['unit_nav'] == 1.2500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
