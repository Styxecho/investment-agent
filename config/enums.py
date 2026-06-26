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
    INDEX = "index"

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
            # 通过代码前缀判断是股票、ETF 还是指数
            # 指数代码通常以 000/399/930/950/980 等开头（6位数字）
            # ETF 代码通常以 51/52/15/16 开头
            prefix = code_upper[:3]
            if prefix in ['000', '399', '930', '950', '980']:
                return cls.INDEX
            prefix2 = code_upper[:2]
            if prefix2 in ['51', '52', '15', '16']:
                return cls.ETF
            return cls.STOCK
        elif code_upper.endswith('.CSI'):
            return cls.INDEX
        elif code_upper.endswith('.IB'):
            return cls.BOND
        else:
            # 默认返回 STOCK
            return cls.STOCK

    @property
    def tushare_daily_api(self) -> str:
        """返回 Tushare 日线数据接口名称"""
        mapping = {
            self.STOCK: 'daily',
            self.ETF: 'fund_daily',  # ETF 使用场内基金日线接口
            self.INDEX: 'index_daily',
            self.FUND: 'fund_nav',
        }
        return mapping.get(self, 'daily')

    @property
    def tushare_code_field(self) -> str:
        """返回 Tushare 接口所需的代码字段名"""
        mapping = {
            self.STOCK: 'ts_code',
            self.ETF: 'ts_code',
            self.INDEX: 'ts_code',
            self.FUND: 'ts_code',
        }
        return mapping.get(self, 'ts_code')

    @property
    def tushare_column_mapping(self) -> dict:
        """返回 Tushare 原始列到标准列的映射"""
        # 股票/指数日线共有字段
        stock_like_mapping = {
            'trade_date': 'trade_date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'pre_close': 'pre_close',
            'vol': 'volume',
            'amount': 'amount',
            'pct_chg': 'pct_change',
        }
        # ETF/场内基金日线字段（fund_daily 接口）
        etf_mapping = {
            'trade_date': 'trade_date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'pre_close': 'pre_close',
            'vol': 'volume',
            'amount': 'amount',
            'pct_chg': 'pct_change',
        }
        # 基金净值特有字段
        fund_mapping = {
            'ann_date': 'announce_date',
            'nav_date': 'trade_date',
            'unit_nav': 'unit_nav',
            'accum_nav': 'accumulated_nav',
            'adj_nav': 'adjusted_nav',
        }
        mapping = {
            self.STOCK: stock_like_mapping,
            self.ETF: etf_mapping,
            self.INDEX: stock_like_mapping,
            self.FUND: fund_mapping,
        }
        return mapping.get(self, stock_like_mapping)

    @property
    def tushare_close_column(self) -> str:
        """返回标准化后的收盘价/净值列名"""
        mapping = {
            self.STOCK: 'close',
            self.ETF: 'close',
            self.INDEX: 'close',
            self.FUND: 'unit_nav',
        }
        return mapping.get(self, 'close')

    @property
    def tushare_pre_close_column(self) -> str:
        """返回标准化后的昨收列名"""
        mapping = {
            self.STOCK: 'pre_close',
            self.ETF: 'pre_close',
            self.INDEX: 'pre_close',
            self.FUND: '',  # 基金需要查询 T-1 日净值
        }
        return mapping.get(self, 'pre_close')

    @property
    def tushare_requires_trade_calendar(self) -> bool:
        """Tushare 基金净值需要交易日历来获取 T-1 日数据"""
        return self == self.FUND

    # --- iFinD 特定映射配置 ---
    # 将数据源特定的配置隔离在枚举内部，避免污染业务逻辑

    @property
    def ifind_close_price_indicator(self) -> str:
        """返回 iFinD 接口所需的 jsonIndicator 参数 (收盘价/净值/指数收盘价)"""
        mapping = {
            self.STOCK: 'ths_close_price_stock',
            self.ETF: 'ths_close_price_stock',  # ETF 使用股票指标
            self.FUND: 'ths_unit_nv_fund',  # 单位净值
            self.INDEX: 'ths_close_price_index'  # 指数收盘价
        }
        return mapping.get(self, '')

    @property
    def ifind_pre_close_indicator(self) -> str:
        """返回 iFinD 接口所需的 jsonIndicator 参数（前收盘价/昨收净值/指数前收盘价）"""
        mapping = {
            self.STOCK: 'ths_pre_close_stock',
            self.ETF: 'ths_pre_close_stock',  # ETF 使用股票指标
            self.FUND: '',  # 基金无昨收，需要查询 T-1 日净值
            self.INDEX: 'ths_pre_close_index'  # 指数前收盘价
        }
        return mapping.get(self, '')

    @property
    def ifind_close_price_column(self) -> str:
        """返回 iFinD 原始数据中收盘价列的列名，用于后续重命名"""
        mapping = {
            self.STOCK: 'close',
            self.ETF: 'close',
            self.FUND: 'unit_nav',  # 单位净值映射为 close
            self.INDEX: 'close'  # 指数收盘价
        }
        return mapping.get(self, '')

    @property
    def ifind_pre_close_column(self) -> str:
        """返回 iFinD 原始数据中昨收价列的列名，用于后续重命名"""
        mapping = {
            self.STOCK: 'pre_close',
            self.ETF: 'pre_close',
            self.FUND: '',  # 基金无昨收列
            self.INDEX: 'pre_close'  # 指数前收盘价
        }
        return mapping.get(self, '')

    @property
    def ifind_adjust_factor_indicator(self) -> str:
        """返回 iFinD 接口所需的复权因子指标"""
        mapping = {
            self.STOCK: 'ths_af2_stock',
            self.ETF: 'ths_af2_stock',  # ETF 和股票共用同一个复权因子字段
            self.FUND: '',  # 基金无复权因子字段，使用 adjusted_nav
            self.INDEX: ''  # 指数无需复权因子
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
        # 基金通常需要 block:latest，股票和 ETF 通常不需要
        # 指数需要 block:history 获取历史数据
        if self == self.FUND:
            return 'block:latest'
        elif self == self.INDEX:
            return 'block:history'
        return ''
    
    @property
    def requires_trade_calendar(self) -> bool:
        """是否需要查询交易日历（所有资产类型都需要）"""
        return True