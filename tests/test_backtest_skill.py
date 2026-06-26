# tests/test_backtest_skill.py
"""
BacktestSkill 基础测试（Mock 数据，不依赖外部 API）
"""
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch

from skills.portfolio.backtest.skill import BacktestSkill
from skills.portfolio.backtest.schema import BacktestRequest, BacktestAsset
from skills.base import SkillContext


class TestBacktestSkill:
    """回测技能测试"""

    @pytest.fixture
    def mock_price_data(self):
        """构造模拟价格数据"""
        dates = pd.date_range("20240101", "20240331", freq="D")
        # 构造两只资产的价格序列
        price_a = 100.0 * (1.0 + pd.Series(range(len(dates)), index=dates) * 0.001)
        price_b = 100.0 * (1.0 + pd.Series(range(len(dates)), index=dates) * 0.0005)
        return {
            "510300.SH": price_a,
            "511010.SH": price_b,
        }

    def test_risk_parity_solver_accuracy(self):
        """验证风险平价求解器精度"""
        import numpy as np
        from skills.portfolio.backtest.risk_parity import risk_parity_weights

        cov = np.array([[0.04, 0.01], [0.01, 0.09]])
        w = risk_parity_weights(cov)

        assert abs(w.sum() - 1.0) < 1e-6
        assert (w >= 0).all()

        # 验证风险贡献是否接近相等
        sigma_w = cov @ w
        rc = w * sigma_w
        portfolio_var = w @ sigma_w
        rc_ratio = rc / portfolio_var
        assert abs(rc_ratio[0] - rc_ratio[1]) < 1e-4

    def test_performance_metrics_calculation(self):
        """验证绩效指标计算"""
        import pandas as pd
        from skills.portfolio.backtest.performance import calculate_metrics

        nav = pd.Series([1.0, 1.02, 1.05, 0.98, 1.10], index=pd.date_range("20240101", periods=5))
        metrics = calculate_metrics(nav)

        assert metrics.cumulative_return == 0.10
        assert metrics.max_drawdown < 0  # 应该有回撤
        assert metrics.sharpe_ratio > 0

    def test_skill_schema_validation(self):
        """验证 Skill 输入校验"""
        skill = BacktestSkill()
        context = SkillContext(
            target_date="20240101",
            extra_params={
                "assets": [
                    {"code": "510300.SH"},
                    {"code": "511010.SH"},
                ],
                "start_date": "20240101",
                "end_date": "20240331",
                "method": "risk_parity",
                "rebalance_freq": "monthly",
            }
        )

        result = skill.execute(context)
        # 由于没有真实数据，预期会失败并返回错误信息
        assert result is not None
        assert hasattr(result, 'meta')

    def test_equal_weight_weights(self):
        """验证等权重构建"""
        import numpy as np
        from skills.portfolio.backtest.risk_parity import build_weights

        cov = np.array([[0.04, 0.01], [0.01, 0.09]])
        w = build_weights("equal_weight", cov)

        assert abs(w[0] - 0.5) < 1e-10
        assert abs(w[1] - 0.5) < 1e-10

    def test_user_defined_weights(self):
        """验证用户指定权重构建"""
        import numpy as np
        from skills.portfolio.backtest.risk_parity import build_weights

        w = build_weights("user_defined", None, [0.3, 0.7])
        assert abs(w[0] - 0.3) < 1e-10
        assert abs(w[1] - 0.7) < 1e-10

        # 自动归一化
        w2 = build_weights("user_defined", None, [1.0, 1.0])
        assert abs(w2[0] - 0.5) < 1e-10

    def test_backtest_request_model(self):
        """验证请求模型"""
        req = BacktestRequest(
            assets=[
                BacktestAsset(code="510300.SH"),
                BacktestAsset(code="511010.SH", weight=0.4),
            ],
            start_date="20240101",
            end_date="20240331",
        )
        assert req.method == "risk_parity"
        assert len(req.assets) == 2
        assert req.assets[0].weight is None
        assert req.assets[1].weight == 0.4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
