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
        1. 从 context.extra_params 提取 symbol/asset_codes 和 asset_type/asset_types。
        2. 使用 context.target_date 作为查询日期。
        3. 调用 service.get_daily_data（支持单只或批量查询）。
        4. 返回标准化的 SkillResult。
        """
        params = context.extra_params or {}
        
        # 支持批量查询（用于 PortfolioSkill 等上游批量调用）
        asset_codes = params.get("asset_codes")
        asset_types = params.get("asset_types")
        
        if asset_codes and isinstance(asset_codes, list):
            return self._execute_batch(context, asset_codes, asset_types or [])
        
        # 单只查询（用于 LLM 工具调用）
        symbol = params.get("symbol")
        asset_type_str = params.get("asset_type", "stock")

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

        try:
            asset_type = AssetType(asset_type_str.lower())
        except ValueError:
            logger.warning(f"未知的资产类型 {asset_type_str}，默认使用 STOCK")
            asset_type = AssetType.STOCK

        result = self.service.get_daily_data(
            context=context,
            symbol=symbol,
            asset_type=asset_type
        )

        if result.meta.status == "success" and result.data:
            if 'pre_close' not in result.data or result.data.get('pre_close') is None:
                current_hint = result.summary_hint or ""
                result.summary_hint = f"{current_hint} (注：该日可能为上市首日，无昨收数据)"

        return result
    
    def _execute_batch(
        self,
        context: SkillContext,
        asset_codes: list,
        asset_types: list
    ) -> SkillResult:
        """
        批量获取行情数据，供 PortfolioSkill 等上游调用。
        
        :param asset_codes: 资产代码列表
        :param asset_types: 资产类型列表（与 asset_codes 一一对应，或只有一个默认值）
        :return: SkillResult，data 字段为 List[dict]
        """
        results = []
        failed_codes = []
        
        # 如果 asset_types 长度与 asset_codes 不一致，用最后一个或默认值填充
        if len(asset_types) < len(asset_codes):
            default_type = asset_types[-1] if asset_types else "stock"
            asset_types = asset_types + [default_type] * (len(asset_codes) - len(asset_types))
        
        for code, atype in zip(asset_codes, asset_types):
            try:
                asset_type = AssetType(atype.lower())
            except ValueError:
                asset_type = AssetType.STOCK
            
            sub_context = SkillContext(
                target_date=context.target_date,
                extra_params={
                    "symbol": code,
                    "asset_type": atype
                }
            )
            
            result = self.service.get_daily_data(
                context=sub_context,
                symbol=code,
                asset_type=asset_type
            )
            
            if result.meta.status == "success" and result.data:
                results.append(result.data)
            else:
                failed_codes.append(code)
                logger.warning(f"[GetMarketDataSkill] 批量查询失败：{code} - {result.meta.message}")
        
        if not results:
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="api",
                    status="failed",
                    target_date=context.target_date,
                    message=f"所有资产行情获取失败。失败列表：{failed_codes}"
                ),
                summary_hint="无法获取任何资产的行情数据。"
            )
        
        status = "partial" if failed_codes else "success"
        message = f"批量查询完成：成功 {len(results)} 只"
        if failed_codes:
            message += f"，失败 {len(failed_codes)} 只：{failed_codes}"
        
        return SkillResult(
            data={"items": results},
            meta=SkillMeta(
                source="api",
                status=status,
                target_date=context.target_date,
                message=message
            ),
            summary_hint=message
        )


# --- 导出单例实例 ---
# 这样其他模块可以直接 from skills.market_data.skill import get_market_data_skill
get_market_data_skill = GetMarketDataSkill()