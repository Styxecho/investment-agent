# skills/portfolio/loader.py
import pandas as pd
import os
from typing import List, Dict
from config.enums import AssetType
from utils.logger import logger


class HoldingsLoader:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"持仓文件未找到: {csv_path}")

    def load(self) -> List[Dict]:
        """
        读取 CSV 文件，返回标准化的持仓列表。
        返回结构: [{'code': '600519.SH', 'name': '贵州茅台', 'volume': 100, 'cost_price': 1500.0, 'asset_type': AssetType.STOCK}, ...]
        """
        logger.info(f"正在加载持仓文件: {self.csv_path}")

        try:
            df = pd.read_csv(self.csv_path)

            # 基础数据清洗
            # 1. 去除空行
            df = df.dropna(how='all')

            # 2. 确保关键列存在
            required_cols = ['code', 'volume', 'cost_price']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"CSV 文件缺少必要列: {missing_cols}")

            # 3. 类型转换
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype(int)
            df['cost_price'] = pd.to_numeric(df['cost_price'], errors='coerce').fillna(0.0)

            # 4. 处理 asset_type (映射到枚举)
            def map_to_enum(val):
                if pd.isna(val):
                    return AssetType.STOCK
                val_str = str(val).strip().upper()
                if val_str in AssetType.__members__:
                    return AssetType[val_str]
                return AssetType.STOCK

            # 如果列存在则映射，不存在则直接创建默认列
            if 'asset_type' in df.columns:
                df['asset_type'] = df['asset_type'].apply(map_to_enum)
            else:
                df['asset_type'] = AssetType.STOCK

            # 5. 填充默认名称
            # 【修正点】这里必须是 'code'，因为您的 CSV 表头是 code
            if 'name' not in df.columns:
                df['name'] = df['code']

                # 转换为字典列表
            holdings = df.to_dict(orient='records')

            logger.info(f"成功加载 {len(holdings)} 只持仓标的。")
            return holdings

        except Exception as e:
            logger.error(f"加载持仓文件失败: {e}")
            raise e