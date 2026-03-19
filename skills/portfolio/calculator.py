# skills/portfolio/calculator.py
from typing import List, Dict, Optional
from datetime import datetime, date
import pandas as pd

# 引入之前的服务
from skills.market_data.service import market_data_service
from config.enums import AssetType
from skills.portfolio.loader import HoldingsLoader
from utils.logger import logger


class PortfolioService:
    def __init__(self, holdings_loader: HoldingsLoader):
        self.loader = holdings_loader
        self.market_service = market_data_service

    def calculate_pnl(self, target_date: Optional[str] = None) -> pd.DataFrame:
        """
        计算组合在指定日期的损益情况。

        参数:
            target_date: 日期字符串 'YYYYMMDD'。如果为 None，默认为最近一个交易日（今天）。

        返回:
            包含详细计算结果的 DataFrame。
        """
        if target_date is None:
            target_date = datetime.now().strftime('%Y%m%d')

        logger.info(f"开始计算组合损益，基准日期: {target_date}")

        holdings = self.loader.load()
        results = []

        for holding in holdings:
            # holding['code'] 来自 loader，值是字符串如 '600519.SH'
            code = holding['code']
            volume = holding['volume']
            cost_price = holding['cost_price']
            name = holding.get('name', code)

            # holding['asset_type'] 来自 loader，值已经是 AssetType 枚举对象 (如 AssetType.STOCK)
            asset_type_obj = holding.get('asset_type', AssetType.STOCK)

            # 【修正点 1】安全处理 asset_type
            # 如果 loader 已经返回了枚举对象，直接使用；如果是字符串（以防万一），则转换
            if isinstance(asset_type_obj, AssetType):
                asset_type = asset_type_obj
            else:
                # 兼容处理：如果是字符串，尝试转枚举
                try:
                    asset_type = AssetType[str(asset_type_obj).upper()]
                except (KeyError, ValueError):
                    asset_type = AssetType.STOCK

            # 1. 获取最新收盘价
            df = self.market_service.get_daily_data(
                symbol=code,  # 这里的参数名 symbol 是 service 定义的，传入 code 字符串即可
                start_date=target_date,
                end_date=target_date,
                asset_type=asset_type
            )

            current_price = 0.0
            data_status = "OK"

            if df is not None and not df.empty:
                row = df.iloc[0]
                current_price = row['close']
            else:
                logger.warning(f"未找到 {code} 在 {target_date} 的价格数据，跳过计算。")
                data_status = "Missing Data"
                current_price = 0.0

            # 2. 计算指标
            if current_price > 0:
                market_value = current_price * volume
                profit_loss = (current_price - cost_price) * volume
                profit_ratio = (current_price - cost_price) / cost_price * 100
            else:
                market_value = 0.0
                profit_loss = 0.0
                profit_ratio = 0.0

            results.append({
                # 【修正点 2】列名统一为 'code'，与 CSV 表头保持一致
                'code': code,
                'name': name,
                'volume': volume,
                'cost_price': cost_price,
                'current_price': round(current_price, 2),
                'market_value': round(market_value, 2),
                'profit_loss': round(profit_loss, 2),
                'profit_ratio(%)': round(profit_ratio, 2),
                'status': data_status
            })

        result_df = pd.DataFrame(results)

        # 3. 计算组合汇总行
        if not result_df.empty:
            total_mv = result_df['market_value'].sum()
            total_pl = result_df['profit_loss'].sum()
            total_cost = (result_df['cost_price'] * result_df['volume']).sum()
            total_ratio = (total_pl / total_cost * 100) if total_cost > 0 else 0

            logger.info("=" * 30)
            logger.info(f"组合总览 ({target_date}):")
            logger.info(f"总市值: {total_mv:,.2f}")
            logger.info(f"总盈亏: {total_pl:,.2f}")
            logger.info(f"总收益率: {total_ratio:.2f}%")
            logger.info("=" * 30)

        return result_df