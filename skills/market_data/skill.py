# skills/market_data/skill.py

from skills.base import BaseSkill, SkillContext, SkillResult, SkillMeta
from typing import Dict, Any
from config.enums import AssetType
from utils.logger import logger
from .service import MarketDataService


class GetMarketDataSkill(BaseSkill):
    """
    【重构版】获取股票市场数据的技能。

    特性：
    1. 基于全局时间观 (context.target_date)，不再依赖 LLM 猜测日期。
    2. 自动获取收盘价 (close) 和昨收价 (pre_close)。
    3. 返回标准化的 SkillResult，包含自然语言摘要。
    4. 内部处理缓存与 API 调用，对上层透明。
    """

    def __init__(self):
        super().__init__(skill_dir=__file__)
        # 实例化服务层 (懒加载连接)
        self.service = MarketDataService()

    @property
    def name(self) -> str:
        return "get_market_data"

    @property
    def description(self) -> str:
        return (
            "获取 A 股股票或场内 ETF 在特定日期的行情数据（包含收盘价、昨收价、涨跌幅）。"
            "当用户询问某只股票的价格、涨跌情况、历史表现时使用。"
            "只需提供股票代码 (6 位数字或带后缀)，系统会自动使用当前对话视角的日期。"
            "无需用户提供开始/结束日期。"
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码。例如：'000001' (平安银行), '600519' (贵州茅台), '000001.SZ'。"
                },
                "asset_type": {
                    "type": "string",
                    "enum": ["stock", "etf", "fund"],
                    "description": "资产类型。默认为 'stock'。如果是 ETF 请填 'etf'。",
                    "default": "stock"
                }
            },
            "required": ["symbol"]
        }

    def execute(self, context: SkillContext) -> SkillResult:
        """
        执行逻辑：
        1. 从 context.extra_params 提取 symbol 和 asset_type。
        2. 使用 context.target_date 作为查询日期。
        3. 调用 service.get_daily_data。
        4. 返回标准化的 SkillResult。
        """
        # 1. 提取参数
        params = context.extra_params or {}
        symbol = params.get("symbol")
        asset_type_str = params.get("asset_type", "stock")

        # 2. 基础校验
        if not symbol:
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="none",
                    status="failed",
                    target_date=context.target_date,
                    message="缺少必要参数：symbol (股票代码)。请用户提供要查询的股票代码。"
                ),
                summary_hint="请告诉我您想查询哪只股票的代码？"
            )

        # 规范化股票代码 (可选：如果用户只输 6 位数字，这里可以加后缀逻辑，暂略)
        # 假设 provider 能处理 '000001' 或 '000001.SZ'

        # 转换资产类型枚举
        try:
            asset_type = AssetType(asset_type_str.lower())
        except ValueError:
            logger.warning(f"未知的资产类型 {asset_type_str}，默认使用 STOCK")
            asset_type = AssetType.STOCK

        # 3. 调用 Service (核心逻辑)
        # service 内部会处理：查缓存 -> 调 API -> 存缓存 -> 返回结果
        result = self.service.get_daily_data(
            context=context,
            symbol=symbol,
            asset_type=asset_type
        )

        # 4. 后处理 (可选)
        # 如果 service 返回成功，但数据中没有 pre_close (比如新股)，可以在这里补充提示
        if result.meta.status == "success" and result.data:
            if 'pre_close' not in result.data or result.data.get('pre_close') is None:
                # 更新 hint，提示缺少昨收
                current_hint = result.summary_hint or ""
                result.summary_hint = f"{current_hint} (注：该日可能为上市首日，无昨收数据)"

        return result


# --- 导出单例实例 ---
# 这样其他模块可以直接 from skills.market_data.skill import get_market_data_skill
get_market_data_skill = GetMarketDataSkill()