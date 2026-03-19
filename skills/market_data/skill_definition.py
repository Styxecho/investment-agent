# skills/market_data/skill_definition.py
from skills.base import BaseSkill
from typing import Dict, Any, List
import pandas as pd
from config.settings import settings
from utils.logger import logger
from .service import market_data_service


class GetMarketDataSkill(BaseSkill):
    """
    获取股票市场数据的技能。
    当前默认使用 AkShare 作为后端提供者。
    未来可以通过配置切换为 Tushare 或其他 API。
    """

    def __init__(self):
        # 由service内部管理，不再直接调用provider
        pass

    @property
    def name(self) -> str:
        return "get_market_data"

    @property
    def description(self) -> str:
        return (
            "获取 A 股股票或场内ETF的历史行情或实时价格。"
            "当用户询问某只股票或场内ETF的价格、走势、历史数据时使用此技能。"
            "需要提供股票或场内ETF代码 (6位数字)、开始日期和结束日期 (格式 YYYYMMDD)。"
            "如果用户只问当前价格，只需提供股票或场内ETF代码。"
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "6 位数字的股票代码，例如 '000001' (平安银行), '600519' (贵州茅台)"
                },
                "start_date": {
                    "type": "string",
                    "description": "开始日期，格式 YYYYMMDD。如果是查询实时价格，此字段可选。"
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期，格式 YYYYMMDD。如果是查询实时价格，此字段可选。"
                },
                "data_type": {
                    "type": "string",
                    "enum": ["history", "realtime"],
                    "description": "数据类型：'history' 获取历史 K 线，'realtime' 获取最新价。默认为 'history'。"
                }
            },
            "required": ["symbol"]
        }

    def execute(self, **kwargs) -> Any:
        symbol = kwargs.get("symbol")
        data_type = kwargs.get("data_type", "history")

        if not symbol:
            raise ValueError("缺少必要参数：symbol (股票代码)")

        try:
            if data_type == "realtime":
                data = market_data_service.get_realtime_data(symbol)

                if not data:
                    return {"error": "Failed to fetch realtime data", "symbol":symbol}

                return {
                    'symbol': symbol,
                    'current_price': data.get('current_price'),
                    'change_percent': data.get('change_percent', 0.0),
                    'update_time': data.get('update_time'),
                    'currency': 'CNY',
                    'source': 'cache_or_api'
                }

            elif data_type == "history":
                start_date = kwargs.get("start_date")
                end_date = kwargs.get("end_date")

                if not start_date or not end_date:
                    # 如果没有提供日期，默认获取最近 30 天
                    from datetime import datetime, timedelta
                    end_obj = datetime.now()
                    start_obj = end_obj - timedelta(days=30)
                    start_date = start_obj.strftime("%Y%m%d")
                    end_date = end_obj.strftime("%Y%m%d")
                    logger.info(f"未提供日期，默认获取最近 30 天：{start_date} 至 {end_date}")

                df = market_data_service.get_daily_data(symbol, start_date, end_date)

                if df is None or df.empty:
                    return {"error": "No data found", "symbol": symbol}

                return {
                    "symbol": symbol,
                    "count": len(df),
                    "start_date": start_date,
                    "end_date": end_date,
                    "preview": df.head(5).to_dict(orient="records"),
                    "columns": list(df.columns),
                    "source": "cache_or_api"
                }

            else:
                raise ValueError(f"未知的数据类型：{data_type}")

        except Exception as e:
            logger.error(f"执行技能get_market_data失败： {e}")


# 实例化，方便其他地方导入
get_market_data_skill = GetMarketDataSkill()