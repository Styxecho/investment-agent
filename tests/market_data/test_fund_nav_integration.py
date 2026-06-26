# tests/market_data/test_fund_nav_integration.py
"""
公募基金净值获取集成测试

验证 iFinD API 调用逻辑和参数格式
测试用例：003956.OF 在 2026-04-01 至 2026-04-03 的净值查询
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from skills.market_data.provider.ifind_provider import iFinDProvider
from skills.market_data.service import MarketDataService
from skills.base import SkillContext
from config.enums import AssetType


class TestFundNAVIntegration:
    """基金净值集成测试（Mock 测试）"""
    
    @pytest.fixture
    def mock_ifind_response(self):
        """模拟 iFinD API 返回的数据"""
        # 创建模拟的 DataFrame
        df = pd.DataFrame([
            {
                'time': '2026-04-01',
                'thscode': '003956.OF',
                'ths_unit_nv_fund': 2.1462,
                'ths_accum_unit_nv_fund': 2.1462,
                'ths_adjustment_nv_fund': 2.1462
            },
            {
                'time': '2026-04-02',
                'thscode': '003956.OF',
                'ths_unit_nv_fund': 2.1514,
                'ths_accum_unit_nv_fund': 2.1514,
                'ths_adjustment_nv_fund': 2.1514
            },
            {
                'time': '2026-04-03',
                'thscode': '003956.OF',
                'ths_unit_nv_fund': 2.1354,
                'ths_accum_unit_nv_fund': 2.1354,
                'ths_adjustment_nv_fund': 2.1354
            }
        ])
        
        # 创建 Mock 响应对象
        mock_response = Mock()
        mock_response.data = df
        return mock_response
    
    def test_ifind_api_call_format(self, mock_ifind_response):
        """测试 iFinD API 调用格式"""
        with patch('skills.market_data.provider.ifind_provider.ifd') as mock_ifd:
            # 设置 Mock 返回
            mock_ifd.THS_DS.return_value = mock_ifind_response
            mock_ifd.THS_iFinDLogin.return_value = 0  # Mock 登录成功
            
            # 创建 Provider 实例
            provider = iFinDProvider()
            
            # 调用 API
            df = provider.fetch_fund_nav(
                fund_code='003956.OF',
                start_date='20260401',
                end_date='20260403'
            )
            
            # 验证 API 被正确调用
            mock_ifd.THS_DS.assert_called_once()
            call_args = mock_ifd.THS_DS.call_args
            
            # 验证参数
            assert call_args[1]['thscode'] == '003956.OF'
            assert call_args[1]['jsonIndicator'] == 'ths_unit_nv_fund;ths_accum_unit_nv_fund;ths_adjustment_nv_fund'
            assert call_args[1]['jsonparam'] == ';;', "jsonparam 应该是 ';;'（2 个分号，对应 3 个指标）"
            assert call_args[1]['globalparam'] == 'block:latest'
            assert call_args[1]['begintime'] == '2026-04-01'
            assert call_args[1]['endtime'] == '2026-04-03'
            
            # 验证返回数据
            assert len(df) == 3
            assert 'unit_nav' in df.columns
            
            # 验证净值
            nav_values = df['unit_nav'].tolist()
            assert nav_values == [2.1462, 2.1514, 2.1354]
    
    def test_service_date_range_query(self, mock_ifind_response):
        """测试 Service 层日期范围查询"""
        with patch('skills.market_data.provider.ifind_provider.ifd') as mock_ifd:
            mock_ifd.THS_DS.return_value = mock_ifind_response
            mock_ifd.THS_iFinDLogin.return_value = 0  # Mock 登录成功
            
            # Mock 数据库操作
            with patch('skills.market_data.service.FundRepository') as mock_repo:
                mock_repo_instance = Mock()
                mock_repo_instance.get_fund_nav.return_value = None  # 缓存未命中
                mock_repo.return_value = mock_repo_instance
                
                # Mock TradeCalendar
                with patch('skills.market_data.service.TradeCalendarService') as mock_calendar:
                    mock_calendar_instance = Mock()
                    mock_calendar_instance.get_previous_trading_date.return_value = '20260402'
                    mock_calendar.return_value = mock_calendar_instance
                    
                    # 创建 Service 实例
                    service = MarketDataService()
                
                # 创建上下文（日期范围查询）
                context = SkillContext(
                    target_date='20260403',
                    extra_params={
                        'symbol': '003956.OF',
                        'asset_type': 'fund',
                        'start_date': '20260401',
                        'end_date': '20260403'
                    }
                )
                
                # 调用 Service
                result = service.get_daily_data(
                    context=context,
                    symbol='003956.OF',
                    asset_type=AssetType.FUND
                )
                
                # 验证结果
                assert result.meta.status == 'success'
                assert 'nav_series' in result.data
                assert len(result.data['nav_series']) == 3
                
                # 验证净值
                expected_nav = [2.1462, 2.1514, 2.1354]
                actual_nav = [item['unit_nav'] for item in result.data['nav_series']]
                assert actual_nav == expected_nav
    
    def test_service_single_date_query(self, mock_ifind_response):
        """测试 Service 层单日查询"""
        with patch('skills.market_data.provider.ifind_provider.ifd') as mock_ifd:
            mock_ifd.THS_DS.return_value = mock_ifind_response
            mock_ifd.THS_iFinDLogin.return_value = 0  # Mock 登录成功
            
            # Mock 数据库操作
            with patch('skills.market_data.service.FundRepository') as mock_repo:
                mock_repo_instance = Mock()
                mock_repo_instance.get_fund_nav.return_value = None
                mock_repo.return_value = mock_repo_instance
                
                # Mock TradeCalendar
                with patch('skills.market_data.service.TradeCalendarService') as mock_calendar:
                    mock_calendar_instance = Mock()
                    mock_calendar_instance.get_previous_trading_date.return_value = '20260402'
                    mock_calendar.return_value = mock_calendar_instance
                    
                    # 创建 Service 实例
                    service = MarketDataService()
                
                # 创建上下文（单日查询）
                context = SkillContext(
                    target_date='20260403',
                    extra_params={
                        'symbol': '003956.OF',
                        'asset_type': 'fund'
                    }
                )
                
                # 调用 Service
                result = service.get_daily_data(
                    context=context,
                    symbol='003956.OF',
                    asset_type=AssetType.FUND
                )
                
                # 验证结果
                assert result.meta.status == 'success'
                # 单日查询会返回 T-1 和 T 日数据，验证包含目标日期
                assert result.summary_hint is not None
                assert '20260403' in result.summary_hint or '2.1354' in result.summary_hint

    def test_cache_incomplete_then_update(self, mock_ifind_response):
        """
        测试核心场景：缓存不完整时，从iFinD获取后是否正确更新缓存。
        
        场景设定：
        1. 缓存中最初只有 2026-04-03 这 1 天的数据（且数据是错误的 2.1000）
        2. 查询 20260401-20260403（3 个交易日）
        3. 系统检测到缓存不完整，应丢弃缓存并调用 iFinD
        4. iFinD 返回 3 天完整数据
        5. 验证最终缓存中被更新为 3 条记录，且 04-03 的数据被覆盖为正确的 2.1354
        """
        from data_external.db.engine import SessionLocal
        from data_external.db.models import FundDaily
        from datetime import date
        import skills.market_data.service as service_module
        
        # 1. 清理并准备不完整缓存
        db = SessionLocal()
        try:
            db.query(FundDaily).filter(
                FundDaily.fund_code == '003956.OF',
                FundDaily.trade_date >= date(2026, 4, 1),
                FundDaily.trade_date <= date(2026, 4, 3)
            ).delete(synchronize_session=False)
            db.commit()
            
            # 插入只有 1 天的错误数据
            incomplete = FundDaily(
                fund_code='003956.OF',
                trade_date=date(2026, 4, 3),
                unit_nav=2.1000,  # 错误数据，预期会被覆盖
                accumulated_nav=2.1000,
                adjusted_nav=2.1000,
                data_source='ifind'
            )
            db.add(incomplete)
            db.commit()
        finally:
            db.close()
        
        # 2. Mock iFinD provider（返回 3 天完整数据）
        mock_provider = Mock()
        # 返回标准化后的 DataFrame（与真实 provider.fetch_fund_nav 输出格式一致）
        mock_df = pd.DataFrame([
            {'trade_date': pd.Timestamp('2026-04-01'), 'fund_code': '003956.OF', 'unit_nav': 2.1462, 'accumulated_nav': 2.1462, 'adjusted_nav': 2.1462},
            {'trade_date': pd.Timestamp('2026-04-02'), 'fund_code': '003956.OF', 'unit_nav': 2.1514, 'accumulated_nav': 2.1514, 'adjusted_nav': 2.1514},
            {'trade_date': pd.Timestamp('2026-04-03'), 'fund_code': '003956.OF', 'unit_nav': 2.1354, 'accumulated_nav': 2.1354, 'adjusted_nav': 2.1354},
        ])
        mock_provider.fetch_fund_nav.return_value = mock_df
        mock_provider.connect.return_value = True
        
        # 3. 临时替换全局 provider
        original_provider = service_module.ifind_provider
        service_module.ifind_provider = mock_provider
        
        try:
            service = MarketDataService()
            
            context = SkillContext(
                target_date='20260403',
                extra_params={
                    'symbol': '003956.OF',
                    'asset_type': 'fund',
                    'start_date': '20260401',
                    'end_date': '20260403'
                }
            )
            
            # 4. 执行查询
            result = service.get_daily_data(
                context=context,
                symbol='003956.OF',
                asset_type=AssetType.FUND
            )
            
            # 5. 验证查询结果正确
            assert result.meta.status == 'success', f"查询应成功，实际：{result.meta.message}"
            assert result.meta.source == 'api', "由于缓存不完整，数据来源应为 api"
            assert 'nav_series' in result.data
            assert len(result.data['nav_series']) == 3, f"应返回 3 条记录，实际 {len(result.data['nav_series'])} 条"
            
            # 6. 关键验证：缓存现在应该有 3 条完整记录
            db = SessionLocal()
            try:
                records = db.query(FundDaily).filter(
                    FundDaily.fund_code == '003956.OF',
                    FundDaily.trade_date >= date(2026, 4, 1),
                    FundDaily.trade_date <= date(2026, 4, 3)
                ).order_by(FundDaily.trade_date.asc()).all()
                
                assert len(records) == 3, f"缓存更新后应有 3 条记录，实际有 {len(records)} 条"
                
                # 验证 04-03 的数据已被覆盖为新值
                apr3_record = [r for r in records if r.trade_date == date(2026, 4, 3)][0]
                assert abs(apr3_record.unit_nav - 2.1354) < 0.0001, \
                    f"4月3日缓存数据应被覆盖为 2.1354，实际为 {apr3_record.unit_nav}"
                
                # 验证 04-01 和 04-02 也已插入
                dates = [r.trade_date for r in records]
                assert date(2026, 4, 1) in dates, "4月1日数据应已插入缓存"
                assert date(2026, 4, 2) in dates, "4月2日数据应已插入缓存"
                
            finally:
                db.close()
                
        finally:
            # 7. 恢复原始 provider
            service_module.ifind_provider = original_provider


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
