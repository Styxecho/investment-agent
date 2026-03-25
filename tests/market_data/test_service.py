# tests/market_data/test_service.py
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import os

# 导入被测试的类
from skills.market_data.service import MarketDataService
from skills.base import SkillContext, SkillResult, SkillMeta
from config.enums import AssetType

class TestMarketDataService:

    def test_get_daily_data_cache_miss(self, mock_ifind_provider, mocker):
        """
        场景：缓存文件不存在 (Cache Miss)
        预期：
        1. 调用 provider.fetch_history
        2. 保存数据到缓存 (调用 to_csv)
        3. 返回数据
        """
        # 0. 准备数据
        target_date_str = "20231001"  # 格式必须匹配 service 中的期望 (YYYYMMDD)
        symbol = "600519.SH"

        # 假设 SkillContext 是一个 dataclass 或简单类，至少有 target_date 属性
        mock_context = MagicMock(spec=SkillContext)
        mock_context.target_date = target_date_str

        # 构造 API 返回的假数据 (DataFrame)
        mock_api_data = pd.DataFrame({
            'trade_date': [target_date_str],
            'close': [100.5],
            'pre_close': [100.0],
            'open': [100.1],
            'high': [101.0],
            'low': [99.5]
        })

        # 1. 设置mock行为
        mock_ifind_provider.fetch_history.return_value = mock_api_data
        mock_ifind_provider.connect.return_value = True  # 确保连接成功

        # 2. 初始化 Service (注入 Mock Provider)
        # 假设您的 Service 只需要 provider 参数，缓存逻辑内部处理
        service = MarketDataService()
        # 将 service 内部的 provider 替换为我们的 mock 对象
        service.provider = mock_ifind_provider

        mock_repo = MagicMock()
        # 设定行为：查询缓存时返回 None (模拟 Cache Miss)
        mock_repo.get_daily_data.return_value = None
        service.repo = mock_repo

        # 调用新方法
        result: SkillResult = service.get_daily_data(
            context=mock_context,
            symbol=symbol,
            asset_type=AssetType.STOCK
        )

        # 4. 断言
        # A. 验证返回类型和基本状态
        assert isinstance(result, SkillResult)
        assert result.meta.status == "success"
        assert result.meta.source == "api"  # 应该来自 API
        assert "iFinD" in result.meta.message  # 消息中应包含来源提示

        # B. 验证 Provider 被正确调用
        mock_ifind_provider.fetch_history.assert_called_once_with(
            symbol=symbol,
            start_date=target_date_str,
            end_date=target_date_str,
            asset_type=AssetType.STOCK
        )

        # C. 验证 Repository 被调用 (查缓存 + 存数据)
        # 1. 查缓存
        mock_repo.get_daily_data.assert_called_once_with(symbol, target_date_str, target_date_str)

        # 2. 存数据 (save_daily_data 应该被调用了一次，传入了那个 DataFrame)
        assert mock_repo.save_daily_data.call_count == 1
        # 检查保存的数据是不是我们 Mock 的那个 df
        saved_df = mock_repo.save_daily_data.call_args[0][0]
        assert isinstance(saved_df, pd.DataFrame)
        assert len(saved_df) == 1

        # D. 验证返回的数据内容
        assert result.data is not None
        assert result.data.get('close') == 100.5
        assert result.data.get('pre_close') == 100.0

        # E. 验证生成的 Hint (可选)
        assert result.summary_hint is not None
        assert "涨跌幅" in result.summary_hint or "收盘价" in result.summary_hint

    def test_get_daily_data_cache_hit(self, mock_ifind_provider, mocker):
        """
        场景：缓存命中 (Cache Hit)
        预期：
        1. Repository 返回数据
        2. 不调用 provider.fetch_history
        3. 不调用 repo.save_daily_data
        4. 返回 source='cache' 的结果
        """
        # 0. 准备数据
        target_date_str = "20231002"
        symbol = "600519.SH"

        mock_context = MagicMock(spec=SkillContext)
        mock_context.target_date = target_date_str

        # 构造缓存中已有的数据 (DataFrame)
        mock_cached_data = pd.DataFrame({
            'trade_date': [target_date_str],
            'close': [102.5],
            'pre_close': [100.5],
            'open': [101.0],
            'high': [103.0],
            'low': [100.0]
        })

        # 1. 设置 Mock 行为
        # Provider 即使被调用也不应该，但为了安全还是 Mock 一下防止意外
        mock_ifind_provider.fetch_history.return_value = None

        # 2. 初始化 Service 并注入 Mock
        service = MarketDataService()
        service.provider = mock_ifind_provider

        mock_repo = MagicMock()
        # 🔥 关键：设定行为 -> 查询缓存时直接返回有效 DataFrame (模拟 Cache Hit)
        mock_repo.get_daily_data.return_value = mock_cached_data
        service.repo = mock_repo

        # 3. 执行
        result: SkillResult = service.get_daily_data(
            context=mock_context,
            symbol=symbol,
            asset_type=AssetType.STOCK
        )

        # 4. 断言
        # A. 验证返回状态
        assert isinstance(result, SkillResult)
        assert result.meta.status == "success"
        assert result.meta.source == "cache"  # 必须来自缓存
        assert "本地缓存" in result.meta.message or "DB" in result.meta.mess

    def test_get_daily_data_api_error_handling(self, mock_ifind_provider, mocker):
        """
        场景：API 错误或连接失败 (Error Handling)
        预期：
        1. Repository 返回空 (Cache Miss)
        2. Provider 连接失败 或 请求抛错
        3. Service 捕获异常，不崩溃
        4. 返回 status='failed' 的 SkillResult
        """
        # 0. 准备数据
        target_date_str = "20231003"
        symbol = "600519.SH"

        mock_context = MagicMock(spec=SkillContext)
        mock_context.target_date = target_date_str

        # 1. 设置 Mock 行为 -> 模拟连接失败
        mock_ifind_provider.connect.return_value = False  # 模拟连接被拒绝
        # 或者模拟 fetch_history 抛出异常:
        # mock_ifind_provider.fetch_history.side_effect = Exception("Network Timeout")

        # 2. 初始化 Service 并注入 Mock
        service = MarketDataService()
        service.provider = mock_ifind_provider

        mock_repo = MagicMock()
        # 设定行为：查询缓存返回 None (强制走 API 逻辑)
        mock_repo.get_daily_data.return_value = None
        service.repo = mock_repo

        # 3. 执行
        # 注意：这里不应该抛出异常，而是返回一个 failed 的 Result
        result: SkillResult = service.get_daily_data(
            context=mock_context,
            symbol=symbol,
            asset_type=AssetType.STOCK
        )

        # 4. 断言
        # A. 验证返回状态为失败
        assert isinstance(result, SkillResult)
        assert result.meta.status == "failed"
        assert result.meta.source == "none"  # 或者根据代码逻辑可能是 "api" 但状态是 failed

        # B. 验证错误消息包含关键信息
        assert result.meta.message is not None
        assert "无法连接" in result.meta.message or "失败" in result.meta.message or "Error" in result.meta.message

        # C. 验证 Provider 被尝试调用 (connect 被调用)
        mock_ifind_provider.connect.assert_called_once()

        # 如果是因为 connect 返回 False，fetch_history 不应该被调用
        mock_ifind_provider.fetch_history.assert_not_called()

        # D. 验证 Repository 没有尝试保存数据 (因为获取失败了)
        mock_repo.save_daily_data.assert_not_called()

        # E. 验证返回的数据为空
        assert result.data == {} or result.data is None

    def test_get_daily_data_api_empty_response(self, mock_ifind_provider, mocker):
        """
        补充场景：API 成功连接但返回空数据 (例如非交易日)
        预期：返回 status='failed' 或 'partial'，提示无数据
        """
        target_date_str = "20231004"  # 假设是个节假日
        symbol = "600519.SH"

        mock_context = MagicMock(spec=SkillContext)
        mock_context.target_date = target_date_str

        # 1. 设置 Mock 行为 -> 连接成功，但返回空 DataFrame
        mock_ifind_provider.connect.return_value = True
        mock_ifind_provider.fetch_history.return_value = pd.DataFrame()  # 空表

        # 2. 初始化 Service
        service = MarketDataService()
        service.provider = mock_ifind_provider

        mock_repo = MagicMock()
        mock_repo.get_daily_data.return_value = None
        service.repo = mock_repo

        # 3. 执行
        result: SkillResult = service.get_daily_data(
            context=mock_context,
            symbol=symbol,
            asset_type=AssetType.STOCK
        )

        # 4. 断言
        assert result.meta.status == "failed"  # 根据您的代码逻辑，空数据返回 failed
        assert "空数据" in result.meta.message or "iFinD" in result.meta.message

        # 验证尝试了保存吗？您的代码逻辑里，如果 df_new.empty 会直接 return，不会 save
        mock_repo.save_daily_data.assert_not_called()