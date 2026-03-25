import pytest
from unittest.mock import patch
from datetime import date
from typing import List

# 导入被测试模块
from skills.portfolio.calculator import calculate_portfolio_timeseries, calculate_portfolio_snapshot
from skills.portfolio.skill import PortfolioSkill
from skills.portfolio.schema import Position, MarketData, AssetType, PortfolioTimeSeries
from skills.base import SkillResult, SkillContext, SkillMeta
from skills.market_data.skill import GetMarketDataSkill


# -------------------------------------------------------------------------
# 1. 计算器核心逻辑测试 (Unit Tests for Calculator)
# 对应路线图 Step 3: 纯函数 + 多维计算 + 精度控制
# -------------------------------------------------------------------------

class TestPortfolioCalculator:
    """测试纯计算引擎的数学正确性和鲁棒性"""

    def test_basic_multi_day_calculation(self):
        """
        场景：2天，2只股票。
        手动计算预期值，验证 PnL, Weight, Contribution 是否匹配。
        """
        positions = [
            # Day 1
            Position(trade_date=date(2026,3,20), asset_code="A.SH", asset_type=AssetType.STOCK, volume=100, cost_price=10.0),
            Position(trade_date=date(2026,3,20), asset_code="B.SZ", asset_type=AssetType.STOCK, volume=200, cost_price=20.0),
            # Day 2
            Position(trade_date=date(2026,3,21), asset_code="A.SH", asset_type=AssetType.STOCK, volume=100, cost_price=10.0),
            Position(trade_date=date(2026,3,21), asset_code="B.SZ", asset_type=AssetType.STOCK, volume=200, cost_price=20.0),
        ]

        market_data = [
            # Day 1: A(+5%), B(-5%)
            MarketData(asset_code="A.SH", trade_date=date(2026,3,20), asset_type=AssetType.STOCK, close_price=10.5,
                       pre_close_price=10.0),
            MarketData(asset_code="B.SZ", trade_date=date(2026,3,20), asset_type=AssetType.STOCK, close_price=19.0,
                       pre_close_price=20.0),
            # Day 2: A(+4.76%), B(0%)
            MarketData(asset_code="A.SH", trade_date=date(2026,3,21), asset_type=AssetType.STOCK, close_price=11.0,
                       pre_close_price=10.5),
            MarketData(asset_code="B.SZ", trade_date=date(2026,3,21), asset_type=AssetType.STOCK, close_price=19.0,
                       pre_close_price=19.0),
        ]

        result: PortfolioTimeSeries = calculate_portfolio_timeseries(positions, market_data)

        # --- 断言基础结构 ---
        assert result.total_days == 2
        assert result.start_date == date(2026,3,20)
        assert result.end_date == date(2026,3,21)

        # --- 断言 Day 1 ---
        snap1 = result.snapshots[0]
        assert snap1.trade_date == date(2026,3,20)
        # MV = 100*10.5 + 200*19.0 = 1050 + 3800 = 4850
        assert abs(snap1.total_market_value - 4850.0) < 0.01
        # PnL = 100*(10.5-10) + 200*(19-20) = 50 - 200 = -150
        assert abs(snap1.daily_pnl - (-150.0)) < 0.01

        # 验证权重 (A: 1050/4850)
        pos_a = next(p for p in snap1.positions if p.asset_code == "A.SH")
        expected_weight_a = 1050.0 / 4850.0
        assert abs(pos_a.weight - expected_weight_a) < 0.0001

        # --- 断言 Day 2 ---
        snap2 = result.snapshots[1]
        assert snap2.trade_date == date(2026,3,21)
        # MV = 100*11 + 200*19 = 1100 + 3800 = 4900
        assert abs(snap2.total_market_value - 4900.0) < 0.01
        # PnL = 100*(11-10.5) + 0 = 50
        assert abs(snap2.daily_pnl - 50.0) < 0.01

    def test_missing_market_data_handling(self):
        """
        测试部分行情缺失的填充逻辑：
        1. Close 缺，Pre 有 -> 填 Close (PnL=0)
        2. Pre 缺，Close 有 -> 填 Pre (PnL=0)
        """
        positions = [
            Position(trade_date=date(2026,3,20), asset_code="A.SH", asset_type=AssetType.STOCK, volume=100, cost_price=10.0),
            Position(trade_date=date(2026,3,20), asset_code="B.SZ", asset_type=AssetType.STOCK, volume=100, cost_price=10.0),
            Position(trade_date=date(2026,3,20), asset_code="C.SZ", asset_type=AssetType.STOCK, volume=100, cost_price=10.0),
        ]

        market_data = [
            # A: 正常
            MarketData(asset_code="A.SH", trade_date=date(2026,3,20), asset_type=AssetType.STOCK, close_price=11.0,
                       pre_close_price=10.0),
            # B: Close 缺失
            MarketData(asset_code="B.SZ", trade_date=date(2026,3,20), asset_type=AssetType.STOCK, close_price=None,
                       pre_close_price=10.0),
            # C: Pre 缺失
            MarketData(asset_code="C.SZ", trade_date=date(2026,3,20), asset_type=AssetType.STOCK, close_price=12.0,
                       pre_close_price=None),
        ]

        result = calculate_portfolio_timeseries(positions, market_data)
        snap = result.snapshots[0]

        # A: PnL = 100
        pos_a = next(p for p in snap.positions if p.asset_code == "A.SH")
        assert abs(pos_a.pnl_daily - 100.0) < 0.01

        # B: Close 被填为 10.0, PnL = 0
        pos_b = next(p for p in snap.positions if p.asset_code == "B.SZ")
        assert abs(pos_b.current_price - 10.0) < 0.01
        assert abs(pos_b.pnl_daily - 0.0) < 0.01

        # C: Pre 被填为 12.0, PnL = 0
        pos_c = next(p for p in snap.positions if p.asset_code == "C.SZ")
        assert abs(pos_c.current_price - 12.0) < 0.01
        assert abs(pos_c.pnl_daily - 0.0) < 0.01

    def test_critical_data_missing_raises_error(self):
        """测试双缺数据是否抛出 ValueError"""
        positions = [
            Position(trade_date=date(2026,3,20), asset_code="BAD.STOCK", asset_type=AssetType.STOCK, volume=100,
                     cost_price=10.0),
        ]
        market_data = [
            MarketData(asset_code="BAD.STOCK", trade_date=date(2026,3,20), asset_type=AssetType.STOCK, close_price=None,
                       pre_close_price=None),
        ]

        with pytest.raises(ValueError, match="数据完整性校验失败"):
            calculate_portfolio_timeseries(positions, market_data)

    def test_float_precision_and_rounding(self):
        """测试浮点数精度"""
        positions = [
            Position(trade_date=date(2026,3,20), asset_code="A.SH", asset_type=AssetType.STOCK, volume=1000,
                     cost_price=10.0),
            Position(trade_date=date(2026,3,20), asset_code="B.SH", asset_type=AssetType.STOCK, volume=1000,
                     cost_price=10.0),
            Position(trade_date=date(2026,3,20), asset_code="C.SH", asset_type=AssetType.STOCK, volume=1000,
                     cost_price=10.0),
        ]
        market_data = [
            MarketData(asset_code="A.SH", trade_date=date(2026,3,20), asset_type=AssetType.STOCK, close_price=10.001,
                       pre_close_price=10.0),
            MarketData(asset_code="B.SH", trade_date=date(2026,3,20), asset_type=AssetType.STOCK, close_price=10.002,
                       pre_close_price=10.0),
            MarketData(asset_code="C.SH", trade_date=date(2026,3,20), asset_type=AssetType.STOCK, close_price=10.003,
                       pre_close_price=10.0),
        ]

        result = calculate_portfolio_timeseries(positions, market_data)
        snap = result.snapshots[0]

        # 总市值: 30006.0
        assert abs(snap.total_market_value - 30006.0) < 0.01

        # 权重和应为 1.0
        total_weight = sum(p.weight for p in snap.positions)
        assert abs(total_weight - 1.0) < 1e-6


# -------------------------------------------------------------------------
# 2. 技能封装层测试 (Integration Tests for Skill)
# 对应路线图 Step 3: 异常处理与消息生成
# -------------------------------------------------------------------------

class TestPortfolioSkill:
    """测试 PortfolioSkill 的端到端流程，Mock 外部依赖"""

    @pytest.fixture
    def skill(self):
        """初始化技能实例"""
        return PortfolioSkill()

    def test_successful_execution_with_message(self, skill):
        """测试成功场景：验证数据流转和自然语言消息生成"""

        # 1. 准备 Context (使用 SkillContext 对象)
        context = SkillContext(
            target_date="20260320",
            extra_params={
                "holdings": [
                    {"asset_code": "A.SH", "volume": 100, "cost_price": 10.0, "asset_name": "Stock A"},
                    {"asset_code": "B.SZ", "volume": 100, "cost_price": 20.0, "asset_name": "Stock B"}
                ],
                "trade_date": "20260320"
            }
        )

        # 2. Mock MarketDataSkill 的返回结果
        mock_market_result = SkillResult(
            data={
                "items": [
                    {"asset_code": "A.SH", "trade_date": "20260320", "asset_type": "STOCK", "close_price": 11.0,
                     "pre_close_price": 10.0},
                    {"asset_code": "B.SZ", "trade_date": "20260320", "asset_type": "STOCK", "close_price": 19.0,
                     "pre_close_price": 20.0}
                ]
            },
            meta=SkillMeta(status="success", source="cache", target_date="20260320", message="已从本地加载数据"),
            summary_hint="已从本地加载数据"
        )

        # 3. 打桩 (Mocking)
        with patch.object(GetMarketDataSkill, 'execute', return_value=mock_market_result) as mock_execute:
            # 4. 执行 (同步调用)
            result: SkillResult = skill.execute(context)

            # 5. 断言
            assert result.meta.status == "success"

            # 检查生成的自然语言消息 (现在在 summary_hint 中)
            assert result.summary_hint is not None
            assert "总市值" in result.summary_hint
            assert "盈利" in result.summary_hint or "亏损" in result.summary_hint

            # 验证数据结构 (calculate_portfolio_timeseries 返回的 model_dump 包含 snapshots)
            assert "snapshots" in result.data
            assert len(result.data["snapshots"]) >= 1

    def test_empty_holdings_input(self, skill):
        """测试输入为空时的友好提示"""
        # 使用 SkillContext
        context = SkillContext(
            target_date="20260320",
            extra_params={"holdings": None}
        )

        result: SkillResult = skill.execute(context)

        assert result.meta.status == "failed"
        # 消息可能在 meta.message 或 summary_hint，根据 skill.py 的实现，失败时通常在 meta.message
        # 但为了兼容，我们检查一下 summary_hint 或者 meta.message
        error_msg = result.meta.message or result.summary_hint or ""
        assert "未检测到持仓数据" in error_msg

    def test_market_data_failure(self, skill):
        """测试依赖的行情服务失败时的降级处理"""
        context = SkillContext(
            target_date="20260320",
            extra_params={
                "holdings": [{"asset_code": "A.SH", "volume": 100, "cost_price": 10.0}],
                "trade_date": "20260320"
            }
        )

        # Mock 行情返回失败状态
        mock_market_result = SkillResult(
            data={},  # 失败时 data 通常为空
            meta=SkillMeta(status="failed", source="api", target_date="20260320", message="API 连接超时"),
            summary_hint="API 连接超时"
        )

        with patch.object(GetMarketDataSkill, 'execute', return_value=mock_market_result) as mock_execute:
            result: SkillResult = skill.execute(context)

            # 根据 skill.py 逻辑，如果 market_data_list 为空，会返回 failed
            assert result.meta.status == "failed"
            error_msg = result.meta.message or ""
            assert "无法获取任何资产的行情数据" in error_msg

    def test_calculator_value_error_handling(self, skill):
        """测试计算器抛出 ValueError 时的捕获与转译"""
        context = SkillContext(
            target_date="20260320",
            extra_params={
                "holdings": [{"asset_code": "BAD.STOCK", "volume": 100, "cost_price": 10.0}],
                "trade_date": "20260320"
            }
        )

        # Mock 行情返回了数据，但数据是坏的（双缺），导致 calculator 抛错
        # 注意：这里 data 依然要包装成 Dict
        mock_market_result = SkillResult(
            data={
                "items": [
                    {"asset_code": "BAD.STOCK", "trade_date": "20260320", "asset_type": "STOCK", "close_price": 10,
                     "pre_close_price": 0}
                ]
            },
            meta=SkillMeta(status="success", source="api", target_date="20260320", message=""),
            summary_hint=""
        )

        with patch.object(GetMarketDataSkill, 'execute', return_value=mock_market_result) as mock_execute:
            result: SkillResult = skill.execute(context)

            assert result.meta.status == "failed"
            error_msg = result.meta.message or ""
            assert "计算" in error_msg or "数据" in error_msg or "除数" in error_msg

            # 确保 NOT 是“无法获取行情”这个错误（那是解析失败或空列表的错误）
            assert "无法获取任何资产的行情数据" not in error_msg

