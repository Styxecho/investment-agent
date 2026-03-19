# skills/market_data/utils.py
# 用于调用外源数据之后存储到本地，避免循环反复调用
import pandas as pd
from datetime import datetime
from config.settings import settings

def save_df_to_market_storage(df: pd.DataFrame, symbol: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{symbol}_history_{timestamp}.csv"
    file_path = settings.MARKET_DATA_DIR / filename
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return str(file_path)