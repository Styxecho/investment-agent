# skills/market_data/providers/akshare_provider.py
import akshare as ak
import pandas as pd
from datetime import datetime
from utils.logger import logger


class AkShareProvider:
    """AkShare 数据源的具体实现"""

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        logger.info(f"[AkShare] 正在获取 {symbol} 历史数据...")
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )

            if df.empty:
                return pd.DataFrame()

            # 标准化列名
            column_mapping = {
                "日期": "trade_date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "vol",
                "成交额": "amount", "涨跌幅": "pct_change",
                "昨收": "pre_close"
            }
            df = df.rename(columns=column_mapping)
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y%m%d")
            
            # 确保 pre_close 列存在
            if "pre_close" not in df.columns:
                # 如果 AkShare 没有返回 pre_close，用 close 近似（首日情况）
                df["pre_close"] = df["close"].shift(1)

            logger.info(f"[AkShare] 成功获取 {len(df)} 条记录。")
            return df

        except Exception as e:
            logger.error(f"[AkShare] 获取失败：{e}")
            raise

    def get_current_price(self, symbol: str) -> float:
        # 简化版实现，实际可优化
        try:
            df = ak.stock_zh_a_spot_em()
            spot = df[df["代码"] == symbol]
            if spot.empty:
                return 0.0
            return float(spot.iloc[0]["最新价"])
        except Exception as e:
            logger.error(f"[AkShare] 实时获取失败：{e}")
            return 0.0