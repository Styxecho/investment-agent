# skills/portfolio/backtest/skill.py
"""
BacktestSkill: 投资组合回测技能
职责：接收回测请求，调用回测引擎，返回标准化结果
"""
from pathlib import Path
from typing import Any, Dict

from skills.base import BaseSkill, SkillContext, SkillResult, SkillMeta
from utils.logger import logger

from .schema import BacktestRequest, BacktestAsset
from .engine import BacktestEngine


class BacktestSkill(BaseSkill):
    """
    通用组合回测技能。
    支持等权重、风险平价、用户自定义权重等多种组合构建方法。
    """

    def __init__(self):
        super().__init__(skill_dir=str(Path(__file__).parent))
        self.engine = BacktestEngine()

    @property
    def name(self) -> str:
        return "portfolio_backtest"

    @property
    def description(self) -> str:
        return (
            "对投资组合进行历史回测。输入资产列表、回测区间和组合构建方法，"
            "输出净值序列、绩效指标（年化收益、波动率、最大回撤、夏普比率等）以及再平衡记录。"
            "支持 risk_parity（风险平价）、equal_weight（等权重）和 user_defined（指定权重）。"
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "assets": {
                    "type": "array",
                    "description": "资产列表，每项包含 code 和可选的 weight",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "weight": {"type": "number"}
                        },
                        "required": ["code"]
                    }
                },
                "start_date": {
                    "type": "string",
                    "pattern": "^\\d{8}$",
                    "description": "开始日期 YYYYMMDD"
                },
                "end_date": {
                    "type": "string",
                    "pattern": "^\\d{8}$",
                    "description": "结束日期 YYYYMMDD"
                },
                "method": {
                    "type": "string",
                    "enum": ["risk_parity", "equal_weight", "user_defined"],
                    "default": "risk_parity",
                    "description": "组合构建方法"
                },
                "rebalance_freq": {
                    "type": "string",
                    "enum": ["none", "monthly", "quarterly"],
                    "default": "monthly",
                    "description": "再平衡频率"
                },
                "lookback_days": {
                    "type": "integer",
                    "default": 252,
                    "description": "协方差估计窗口（交易日）"
                }
            },
            "required": ["assets", "start_date", "end_date"]
        }

    def execute(self, context: SkillContext) -> SkillResult:
        """
        执行回测
        """
        try:
            extra = context.extra_params or {}
            assets_raw = extra.get("assets", [])
            start_date = extra.get("start_date", context.target_date)
            end_date = extra.get("end_date", context.target_date)
            method = extra.get("method", "risk_parity")
            rebalance_freq = extra.get("rebalance_freq", "monthly")
            lookback_days = extra.get("lookback_days", 252)

            if not assets_raw:
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source="validation",
                        status="failed",
                        target_date=context.target_date,
                        message="缺少 assets 参数，请提供回测资产列表。"
                    ),
                )

            assets = []
            for item in assets_raw:
                code = item.get("code")
                if not code:
                    continue
                weight = item.get("weight")
                assets.append(BacktestAsset(code=code, weight=weight))

            request = BacktestRequest(
                assets=assets,
                start_date=start_date,
                end_date=end_date,
                method=method,
                rebalance_freq=rebalance_freq,
                lookback_days=lookback_days,
            )

            logger.info(f"[BacktestSkill] 开始回测: {len(assets)} 只资产, {start_date} ~ {end_date}, method={method}")
            result = self.engine.run(request)

            if result.error_message:
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source="backtest_engine",
                        status="failed",
                        target_date=context.target_date,
                        message=f"回测执行失败: {result.error_message}"
                    ),
                )

            summary = (
                f"回测完成 ({start_date} ~ {end_date})。"
                f"年化收益 {result.metrics.annualized_return:.2%}，"
                f"年化波动 {result.metrics.annualized_volatility:.2%}，"
                f"最大回撤 {result.metrics.max_drawdown:.2%}，"
                f"夏普比率 {result.metrics.sharpe_ratio:.2f}。"
            )

            return SkillResult(
                data=result.model_dump(),
                meta=SkillMeta(
                    source="backtest_engine",
                    status="success",
                    target_date=context.target_date,
                    message="回测成功"
                ),
                summary_hint=summary,
            )

        except Exception as e:
            logger.exception(f"[BacktestSkill] 执行异常: {e}")
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="system_error",
                    status="failed",
                    target_date=context.target_date,
                    message=f"回测服务异常: {str(e)}"
                ),
            )
