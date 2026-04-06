import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import date

# 1. 导入基类与标准契约 (严格匹配 base.py)
from skills.base import BaseSkill, SkillContext, SkillResult, SkillMeta
from utils.logger import logger
from config.enums import AssetType

# 2. 导入本地 Schema 和 Calculator
from .schema import Position, MarketData, PortfolioTimeSeries
from .calculator import calculate_portfolio_timeseries


# 3. 延迟导入依赖技能 (避免循环导入)
# 在 execute 内部导入，或者确保架构已处理依赖注入
# 这里为了代码清晰，我们在 execute 中动态导入，或者假设环境允许
# 如果 GetMarketDataSkill 也是 BaseSkill 的子类，通常可以直接实例化


class PortfolioSkill(BaseSkill):
    """
    Portfolio Analysis Skill.
    职责：
    1. 从 SkillContext 解析用户持仓。
    2. 调用 MarketDataSkill 获取最新行情 (模拟或真实)。
    3. 执行组合盈亏计算。
    4. 生成自然语言分析报告。
    """

    def __init__(self):
        """
        初始化技能。
        根据 base.py，只需调用 super().__init__() 即可自动加载 prompt.txt。
        """
        # 自动定位当前文件所在目录 (skills/portfolio)
        super().__init__(skill_dir=Path(__file__).parent)

        # 注意：不要在 __init__ 中直接实例化重型依赖或可能导致循环导入的 Skill
        # 我们可以在 execute 中按需实例化，或者通过 context 注入

    # ---------------------------------------------------------------------
    # 1. 实现抽象属性 (解决 TypeError 的关键)
    # ---------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "portfolio_analyzer"

    @property
    def description(self) -> str:
        return (
            "分析投资组合的当日表现。输入持仓列表（代码、数量、成本），"
            "自动获取行情并计算总市值、当日盈亏(PnL)、收益率及个股贡献。"
            "输出包含详细的数据结构和自然语言总结。"
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        """
        定义 LLM 需要提供的参数结构 (JSON Schema)。
        这些参数将被上游组装进 SkillContext.extra_params。
        """
        return {
            "holdings": {
                "type": "array",
                "description": "持仓列表。每项包含: asset_code (str), volume (number), cost_price (number), asset_name (str, optional).",
                "items": {
                    "type": "object",
                    "properties": {
                        "asset_code": {"type": "string"},
                        "volume": {"type": "number"},
                        "cost_price": {"type": "number"},
                        "asset_name": {"type": "string"}
                    },
                    "required": ["asset_code", "volume", "cost_price"]
                }
            },
            "trade_date": {
                "type": "string",
                "pattern": "^\\d{8}$",
                "description": "交易日期 (YYYYMMDD)。可选，默认为目标日期。"
            }
        }

    # ---------------------------------------------------------------------
    # 2. 实现核心执行方法 (同步，接收 SkillContext)
    # ---------------------------------------------------------------------

    def execute(self, context: SkillContext) -> SkillResult:
        """
        执行组合分析 (同步版本)。

        :param context: 包含 target_date, holdings (在 extra_params 或 holdings 字段中) 的上下文。
        :return: SkillResult 包含计算结果和自然语言消息。
        """
        try:
            # --- 步骤 1: 解析输入数据 ---
            # 优先从 extra_params 获取结构化数据 (由 Orchestrator/LLM 填充)
            # 兼容旧版逻辑：如果 direct holdings 在 context.holdings 中也可以
            raw_holdings = None
            if context.extra_params and "holdings" in context.extra_params:
                raw_holdings = context.extra_params["holdings"]
            elif context.holdings:
                raw_holdings = context.holdings

            # 确定交易日期
            trade_date_str = context.target_date  # 默认使用上下文的目标日期
            if context.extra_params and "trade_date" in context.extra_params:
                trade_date_str = context.extra_params["trade_date"]

            if not raw_holdings:
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source="validation",
                        status="failed",
                        target_date=trade_date_str,
                        message="未检测到持仓数据。请提供持仓列表（例如：[{'asset_code': '600519.SH', 'volume': 100, 'cost_price': 1800}]）。"
                    ),
                    summary_hint = "未检测到持仓数据。"
                )

            # 标准化持仓为 List[Position]
            positions = self._parse_holdings(raw_holdings, trade_date_str)

            if not positions:
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source="validation",
                        status="failed",
                        target_date=trade_date_str,
                        message="解析持仓失败，未识别到有效的资产信息。"
                    ),
                    summary_hint="解析持仓失败。"
                )

            # --- 步骤 2: 获取行情数据 ---
            asset_codes = list(set(p.asset_code for p in positions))
            asset_types = list(set(p.asset_type for p in positions))

            logger.info(f"[PortfolioSkill] 请求 {len(asset_codes)} 个资产的行情: {asset_codes}")

            # 【关键改动】：动态导入以避免循环依赖，并实例化依赖技能
            from skills.market_data.skill import GetMarketDataSkill
            market_skill = GetMarketDataSkill()

            # 构造子上下文 (SkillContext)
            # 注意：这里我们需要将参数放入 extra_params，因为 GetMarketDataSkill 也期望这种结构
            sub_context = SkillContext(
                target_date=trade_date_str,
                extra_params={
                    "asset_codes": asset_codes,
                    "asset_types": [at.value for at in asset_types]  # 传字符串值
                }
            )

            # 调用依赖技能 (同步调用)
            market_result = market_skill.execute(sub_context)

            if market_result.meta.status == "failed":
                logger.warning(f"行情获取部分失败: {market_result.meta.message}")
                # 策略：尝试继续，让计算器处理缺失数据，或者在此拦截
                # 这里选择继续，看是否能获取到部分数据

            # 解析行情结果为 List[MarketData]
            market_data_list = self._parse_market_data(market_result.data)

            if not market_data_list:
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source="data_dependency",
                        status="failed",
                        target_date=trade_date_str,
                        message=f"无法获取任何资产的行情数据。原因：{market_result.meta.message}"
                    ),
                    summary_hint="无法获取行情数据。"
                )

            # --- 步骤 3: 执行核心计算 ---
            logger.info("[PortfolioSkill] 开始执行组合计算引擎...")
            try:
                result_ts: PortfolioTimeSeries = calculate_portfolio_timeseries(
                    positions=positions,
                    market_data=market_data_list
                )
            except ValueError as e:
                logger.error(f"计算失败: {str(e)}")
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source="calculation",
                        status="failed",
                        target_date=trade_date_str,
                        message=f"计算过程中发现数据问题：{str(e)[:100]}..."
                    ),
                    summary_hint="计算失败。"
                )

            if not result_ts.snapshots:
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source="calculation",
                        status="success",  # 算是成功但无数据
                        target_date=trade_date_str,
                        message="计算完成，但未找到匹配的交易日期或持仓为空。"
                    ),
                    summary_hint="无有效数据生成报告。"
                )

            # --- 步骤 4: 构建输出与消息 ---
            latest_snapshot = result_ts.snapshots[-1]

            # 生成自然语言总结
            msg_parts = []
            total_pnl = latest_snapshot.daily_pnl
            pnl_sign = "盈利" if total_pnl >= 0 else "亏损"

            # 格式化日期字符串 (如果 snapshot 里是 date 对象，model_dump 会处理，但这里手动格式化用于消息)
            display_date = latest_snapshot.trade_date
            if isinstance(display_date, date):
                display_date = display_date.strftime("%Y%m%d")

            msg_parts.append(f"📅 {display_date} 组合表现：")
            msg_parts.append(
                f"总市值 **{latest_snapshot.total_market_value:,.2f}** 元，"
                f"当日{pnl_sign} **{abs(total_pnl):,.2f}** 元 "
                f"(收益率 {latest_snapshot.daily_return:.2f}%)."
            )

            if latest_snapshot.positions:
                sorted_pos = sorted(latest_snapshot.positions, key=lambda x: x.contribution_to_daily_pnl, reverse=True)
                best = sorted_pos[0]
                worst = sorted_pos[-1]

                if best.contribution_to_daily_pnl > 0:
                    msg_parts.append(
                        f"🚀 最大贡献：**{best.asset_name or best.asset_code}** (贡献 {best.contribution_to_daily_pnl:.2f} 元)。")
                if worst.contribution_to_daily_pnl < 0:
                    msg_parts.append(
                        f"📉 最大拖累：**{worst.asset_name or worst.asset_code}** (拖累 {abs(worst.contribution_to_daily_pnl):,.2f} 元)。")

            final_message = " ".join(msg_parts)

            # 返回标准结果
            # model_dump() 会自动处理 DateStr 的序列化 (date -> "YYYYMMDD")
            return SkillResult(
                data=result_ts.model_dump(),
                meta=SkillMeta(
                    source="calculation",
                    status="success",
                    target_date=trade_date_str,
                    message="组合分析完成。"
                ),
                summary_hint=final_message
            )

        except Exception as e:
            logger.exception(f"[PortfolioSkill] 执行发生未预期错误: {e}")
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="system_error",
                    status="failed",
                    target_date=context.target_date if context else "unknown",
                    message=f"组合分析服务暂时不可用：{str(e)}"
                ),
                summary_hint="系统错误。"
            )

    # ---------------------------------------------------------------------
    # 3. 辅助解析方法 (保持原有逻辑)
    # ---------------------------------------------------------------------

    def _parse_holdings(self, raw_input: Any, trade_date: str) -> List[Position]:
        """将各种格式的输入解析为 List[Position]。"""
        positions = []
        data_list = []

        if isinstance(raw_input, str):
            try:
                data_list = json.loads(raw_input)
            except json.JSONDecodeError:
                logger.error("持仓输入不是有效的 JSON 字符串")
                return []
        elif isinstance(raw_input, list):
            data_list = raw_input
        else:
            logger.error(f"不支持的持仓输入类型: {type(raw_input)}")
            return []

        for item in data_list:
            try:
                code = item.get("asset_code") or item.get("code")
                vol = item.get("volume") or item.get("amount") or 0
                cost = item.get("cost_price") or item.get("cost") or 0
                name = item.get("asset_name") or item.get("name")
                atype_str = item.get("asset_type") or "STOCK"

                try:
                    atype = AssetType[atype_str.upper()]
                except KeyError:
                    atype = AssetType.STOCK

                # 利用 Pydantic 的验证器处理日期格式
                pos = Position(
                    trade_date=trade_date,
                    asset_code=str(code),
                    asset_name=name,
                    asset_type=atype,
                    volume=float(vol),
                    cost_price=float(cost)
                )
                positions.append(pos)
            except Exception as e:
                logger.warning(f"解析单条持仓失败: {item}, 错误: {e}")
                continue

        return positions

    def _parse_market_data(self, data: Union[Dict, List]) -> List[MarketData]:
        """从 MarketDataSkill 的返回结果中提取 List[MarketData]。"""
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # 兼容多种返回结构
            items = data.get("items") or data.get("data") or data.get("result") or []

        # 如果 data 本身就是 SkillResult.data 且结构嵌套，可能需要更深一层，视 MarketDataSkill 而定
        # 假设 MarketDataSkill 返回的 data 字段直接就是列表或包含列表的字典

        market_data_list = []
        for item in items:
            try:
                # 处理可能的枚举字符串
                atype_raw = item.get("asset_type", "STOCK")
                if isinstance(atype_raw, str):
                    atype = AssetType[atype_raw.upper()]
                else:
                    atype = atype_raw  # 已经是枚举

                pre_close = item.get("pre_close_price")
                # 显式处理 None，防止 float(None) 报错
                pre_close_val = float(pre_close) if pre_close is not None else None

                md = MarketData(
                    trade_date=item.get("trade_date"),
                    asset_code=item.get("asset_code"),
                    asset_type=atype,
                    close_price=float(item.get("close_price")),
                    pre_close_price=pre_close_val
                )
                market_data_list.append(md)
            except Exception as e:
                logger.warning(f"解析行情数据失败: {item}, 错误: {e}")
                continue

        return market_data_list