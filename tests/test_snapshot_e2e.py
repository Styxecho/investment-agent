# tests/test_snapshot_e2e.py
"""
端到端测试：验证 PortfolioSkill 计算结果 -> SnapshotSkill 保存 -> 数据库读取的完整链路
使用纯 Mock 数据，不依赖外部 API。
"""
import pytest
from datetime import date
from skills.base import SkillContext
from skills.portfolio.snapshot.snapshot_skill import SnapshotSkill
from data_external.db.repositories import PortfolioSnapshotRepository
from data_external.db.engine import SessionLocal
from data_external.db.models import PortfolioSnapshot


class TestSnapshotE2E:
    """SnapshotSkill 端到端测试"""

    @pytest.fixture(autouse=True)
    def cleanup_db(self):
        """每次测试前清理测试数据"""
        db = SessionLocal()
        try:
            db.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.portfolio_id == "test_portfolio"
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
        yield

    def test_save_and_read_snapshot(self):
        """测试保存快照后能从数据库正确读取"""
        snapshot_skill = SnapshotSkill()

        # 构造模拟的 PortfolioTimeSeries 数据
        mock_time_series = {
            "snapshots": [
                {
                    "trade_date": "20260414",
                    "total_market_value": 150000.00,
                    "total_cost_value": 140000.00,
                    "total_pnl_cumulated": 10000.00,
                    "daily_pnl": 2500.00,
                    "daily_return": 1.69,
                    "net_value": 1.0714,
                    "position_count": 2,
                    "positions": [
                        {
                            "trade_date": "20260414",
                            "asset_code": "600519.SH",
                            "asset_name": "贵州茅台",
                            "asset_type": "STOCK",
                            "volume": 100.0,
                            "current_price": 1800.00,
                            "cost_price": 1700.00,
                            "market_value": 180000.00,
                            "cost_value": 170000.00,
                            "pnl_cumulated": 10000.00,
                            "pnl_daily": 2000.00,
                            "weight": 0.80,
                            "contribution_to_daily_pnl": 2000.00,
                            "contribution_to_daily_return": 1.35
                        },
                        {
                            "trade_date": "20260414",
                            "asset_code": "003956.OF",
                            "asset_name": "易方达蓝筹精选",
                            "asset_type": "FUND",
                            "volume": 1000.0,
                            "current_price": 2.15,
                            "cost_price": 2.00,
                            "market_value": 2150.00,
                            "cost_value": 2000.00,
                            "pnl_cumulated": 150.00,
                            "pnl_daily": 50.00,
                            "weight": 0.20,
                            "contribution_to_daily_pnl": 50.00,
                            "contribution_to_daily_return": 0.34
                        }
                    ]
                }
            ],
            "start_date": "20260414",
            "end_date": "20260414",
            "total_days": 1
        }

        context = SkillContext(
            target_date="20260414",
            extra_params={
                "portfolio_time_series": mock_time_series,
                "portfolio_id": "test_portfolio"
            }
        )

        # 1. 执行保存
        result = snapshot_skill.execute(context)

        assert result.meta.status == "success"
        assert result.data["saved_count"] == 1
        assert result.data["portfolio_id"] == "test_portfolio"

        # 2. 从数据库读取验证
        repo = PortfolioSnapshotRepository()
        saved = repo.get_snapshot(date(2026, 4, 14), portfolio_id="test_portfolio")

        assert saved is not None
        assert saved["trade_date"] == "20260414"
        assert saved["total_market_value"] == 150000.00
        assert saved["daily_pnl"] == 2500.00
        assert saved["daily_return"] == 1.69
        assert saved["net_value"] == 1.0714
        assert saved["position_count"] == 2
        assert len(saved["positions"]) == 2

        # 验证个股明细
        first_pos = saved["positions"][0]
        assert first_pos["asset_code"] == "600519.SH"
        assert first_pos["asset_name"] == "贵州茅台"
        assert first_pos["contribution_to_daily_pnl"] == 2000.00

    def test_multi_day_snapshot_sequence(self):
        """测试多日快照按顺序保存和读取"""
        snapshot_skill = SnapshotSkill()

        mock_time_series = {
            "snapshots": [
                {
                    "trade_date": "20260410",
                    "total_market_value": 100000.00,
                    "total_cost_value": 100000.00,
                    "total_pnl_cumulated": 0.00,
                    "daily_pnl": 0.00,
                    "daily_return": 0.00,
                    "net_value": 1.00,
                    "position_count": 1,
                    "positions": []
                },
                {
                    "trade_date": "20260411",
                    "total_market_value": 102000.00,
                    "total_cost_value": 100000.00,
                    "total_pnl_cumulated": 2000.00,
                    "daily_pnl": 2000.00,
                    "daily_return": 2.00,
                    "net_value": 1.02,
                    "position_count": 1,
                    "positions": []
                }
            ],
            "start_date": "20260410",
            "end_date": "20260411",
            "total_days": 2
        }

        context = SkillContext(
            target_date="20260411",
            extra_params={
                "portfolio_time_series": mock_time_series,
                "portfolio_id": "test_portfolio"
            }
        )

        result = snapshot_skill.execute(context)
        assert result.data["saved_count"] == 2

        # 读取区间序列
        repo = PortfolioSnapshotRepository()
        sequence = repo.get_snapshots(
            date(2026, 4, 10),
            date(2026, 4, 11),
            portfolio_id="test_portfolio"
        )

        assert len(sequence) == 2
        assert sequence[0]["trade_date"] == "20260410"
        assert sequence[0]["net_value"] == 1.00
        assert sequence[1]["trade_date"] == "20260411"
        assert sequence[1]["net_value"] == 1.02

    def test_missing_data_validation(self):
        """测试缺少 portfolio_time_series 时的错误处理"""
        snapshot_skill = SnapshotSkill()

        context = SkillContext(
            target_date="20260414",
            extra_params={}
        )

        result = snapshot_skill.execute(context)
        assert result.meta.status == "failed"
        assert "缺少 portfolio_time_series" in result.meta.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
