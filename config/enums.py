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
    
    @classmethod
    def from_code_suffix(cls, code: str) -> 'AssetType':
        """
        根据代码后缀识别资产类型
        
        示例：
        - '600519.SH' → STOCK
        - '510300.SH' → ETF
        - '003956.OF' → FUND
        
        :param code: 资产代码（如 '600519.SH', '003956.OF'）
        :return: AssetType 枚举值
        """
        code_upper = code.upper()
        
        if code_upper.endswith('.OF'):
            return cls.FUND
        elif code_upper.endswith('.SH') or code_upper.endswith('.SZ'):
            # 通过代码前缀判断是股票还是 ETF
            # ETF 代码通常以 51/52/15/16 开头
            prefix = code_upper[:2]
            if prefix in ['51', '52', '15', '16']:
                return cls.ETF
            return cls.STOCK
        elif code_upper.endswith('.IB'):
            return cls.BOND
        else:
            # 默认返回 STOCK
            return cls.STOCK

    # --- iFinD 特定映射配置 ---
    # 将数据源特定的配置隔离在枚举内部，避免污染业务逻辑

    @property
    def ifind_close_price_indicator(self) -> str:
        """返回 iFinD 接口所需的 jsonIndicator 参数 (收盘价/净值)"""
        mapping = {
            self.STOCK: 'ths_close_price_stock',
            self.ETF: 'ths_close_price_fund',
            self.FUND: 'ths_unit_nv_fund'  # 单位净值
        }
        return mapping.get(self, '')

    @property
    def ifind_pre_close_indicator(self) -> str:
        """返回 iFinD 接口所需的 jsonIndicator 参数（前收盘价/昨收净值）"""
        mapping = {
            self.STOCK: 'ths_pre_close_stock',
            self.ETF: 'ths_pre_close_fund',
            self.FUND: ''  # 基金无昨收，需要查询 T-1 日净值
        }
        return mapping.get(self, '')

    @property
    def ifind_close_price_column(self) -> str:
        """返回 iFinD 原始数据中收盘价列的列名，用于后续重命名"""
        mapping = {
            self.STOCK: 'close',
            self.ETF: 'close',
            self.FUND: 'unit_nav'  # 单位净值映射为 close
        }
        return mapping.get(self, '')

    @property
    def ifind_pre_close_column(self) -> str:
        """返回 iFinD 原始数据中昨收价列的列名，用于后续重命名"""
        mapping = {
            self.STOCK: 'pre_close',
            self.ETF: 'pre_close',
            self.FUND: ''  # 基金无昨收列
        }
        return mapping.get(self, '')

    @property
    def ifind_fund_nav_indicators(self) -> str:
        """
        返回 iFinD 接口所需的基金净值指标（分号分隔）
        
        公募基金需要同时获取三种净值：
        - ths_unit_nv_fund: 单位净值
        - ths_accum_unit_nv_fund: 累计单位净值
        - ths_adjustment_nv_fund: 复权单位净值
        
        调用示例：
        THS_DS('003956.OF', 'ths_unit_nv_fund;ths_accum_unit_nv_fund;ths_adjustment_nv_fund', ...)
        """
        if self == self.FUND:
            return 'ths_unit_nv_fund;ths_accum_unit_nv_fund;ths_adjustment_nv_fund'
        return ''

    @property
    def ifind_global_param(self) -> str:
        """返回 iFinD 接口所需的 globalparam 参数"""
        # 基金和 ETF 通常需要 block:latest，股票通常不需要
        if self in [self.ETF, self.FUND]:
            return 'block:latest'
        return ''
    
    @property
    def requires_trade_calendar(self) -> bool:
        """是否需要查询交易日历（所有资产类型都需要）"""
        return True