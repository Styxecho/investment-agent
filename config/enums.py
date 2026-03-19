# config/enums.py

from enum import Enum


class AssetType(Enum):
    """
    【全局】资产类别枚举
    用于统一整个项目中对资产类型的标识。
    """
    STOCK = "stock"
    ETF = "etf"
    FUND = "fund"
    BOND = "bond"
    FUTURES = "futures"

    def __str__(self):
        return self.value

    # --- iFinD 特定映射配置 ---
    # 将数据源特定的配置隔离在枚举内部，避免污染业务逻辑

    @property
    def ifind_indicator(self) -> str:
        """返回 iFinD 接口所需的 jsonIndicator 参数"""
        mapping = {
            self.STOCK: 'ths_close_price_stock',
            self.ETF: 'ths_close_price_fund',
            self.FUND: 'ths_adjustment_nv_fund'
        }
        return mapping.get(self, '')

    @property
    def ifind_price_column(self) -> str:
        """返回 iFinD 原始数据中价格列的列名，用于后续重命名"""
        mapping = {
            self.STOCK: 'close',
            self.ETF: 'close',
            self.FUND: 'adjusted_nav'
        }
        return mapping.get(self, '')

    @property
    def ifind_global_param(self) -> str:
        """返回 iFinD 接口所需的 globalparam 参数"""
        # 基金和 ETF 通常需要 block:latest，股票通常不需要
        if self in [self.ETF, self.FUND]:
            return 'block:latest'
        return ''