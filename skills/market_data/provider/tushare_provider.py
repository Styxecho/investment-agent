# skills/market_data/providers/tushare_provider.py

import time
from datetime import datetime
from typing import Optional, Union, List

import pandas as pd

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None

from config.settings import settings
from config.enums import AssetType
from utils.logger import logger


class TushareProvider:
    """
    Tushare 数据提供者（单例模式）

    支持：
    - A 股日线（含前复权）
    - ETF 日线
    - 指数日线
    - 公募基金净值

    接口文档：
    - daily: https://tushare.pro/document/2?doc_id=27
    - index_daily: https://tushare.pro/document/2?doc_id=78
    - fund_nav: https://tushare.pro/document/2?doc_id=182
    """

    _instance: Optional['TushareProvider'] = None
    _pro = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(TushareProvider, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.token = getattr(settings, 'TUSHARE_TOKEN', None)
        if not self.token:
            logger.warning("⚠️  配置缺失：未在 settings 中找到 TUSHARE_TOKEN")

        self._initialized = True

    def _get_pro(self):
        """懒加载 Tushare pro 接口"""
        if self._pro is not None:
            return self._pro

        if not TUSHARE_AVAILABLE:
            raise ImportError("tushare 模块未安装，请运行：pip install tushare")

        if not self.token:
            raise ValueError("Tushare token 未配置")

        ts.set_token(self.token)
        self._pro = ts.pro_api()
        logger.info("✅ Tushare pro_api 初始化完成")
        return self._pro

    def _call_api_with_retry(self, api_name: str, max_retries: int = 3, **kwargs):
        """带指数退避的 Tushare API 调用"""
        pro = self._get_pro()
        api = getattr(pro, api_name)

        last_error = None
        for attempt in range(max_retries):
            try:
                df = api(**kwargs)
                return df
            except Exception as e:
                last_error = e
                logger.warning(f"[Tushare] {api_name} 第 {attempt + 1}/{max_retries} 次请求失败：{e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"[Tushare] 等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"[Tushare] {api_name} 达到最大重试次数，最终失败。")
                    raise last_error

    def _normalize_code(self, symbol: str, asset_type: AssetType) -> str:
        """
        将项目内部代码格式转换为 Tushare 格式。

        项目内部：000001.SZ, 000001.SH, 000985.CSI, 003956.OF
        Tushare：  000001.SZ, 000001.SH, 000985.CSI, 003956.OF

        大部分情况下后缀一致，只需统一大小写。
        """
        return symbol.upper()

    def fetch_history(
        self,
        symbol: Union[str, List[str]],
        start_date: str,
        end_date: str,
        asset_type: AssetType = AssetType.STOCK,
        retry_times: int = 3
    ) -> pd.DataFrame:
        """
        获取历史日线数据（股票 / ETF / 指数）。

        :param symbol: 资产代码或代码列表
        :param start_date: 开始日期 (YYYYMMDD)
        :param end_date: 结束日期 (YYYYMMDD)
        :param asset_type: 资产类型
        :param retry_times: 失败重试次数
        :return: 标准化后的 DataFrame
        """
        if isinstance(symbol, list):
            # Tushare 接口一次只能查一个代码，需要分批
            records = []
            for s in symbol:
                df = self.fetch_history(s, start_date, end_date, asset_type, retry_times)
                if df is not None and not df.empty:
                    records.append(df)
            if not records:
                return pd.DataFrame()
            return pd.concat(records, ignore_index=True)

        ts_code = self._normalize_code(symbol, asset_type)
        api_name = asset_type.tushare_daily_api

        logger.info(f"[Tushare] 准备获取数据：{ts_code} ({start_date} ~ {end_date}) [{api_name}]")

        df = self._call_api_with_retry(
            api_name,
            max_retries=retry_times,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

        if df is None or df.empty:
            logger.warning(f"[Tushare] {ts_code} 返回数据为空")
            return pd.DataFrame()

        # 标准化列名
        column_mapping = asset_type.tushare_column_mapping
        df = df.rename(columns=column_mapping)

        # 统一日期格式
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')

        # 确保数值类型正确
        numeric_cols = ['open', 'high', 'low', 'close', 'pre_close', 'volume', 'amount', 'pct_change']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 添加代码列（Tushare 返回的 ts_code 字段）
        if 'ts_code' in df.columns:
            df = df.rename(columns={'ts_code': 'scrt_code'})
        else:
            df['scrt_code'] = ts_code

        logger.info(f"[Tushare] {ts_code} 成功获取 {len(df)} 条记录")
        return df

    def fetch_index_history(
        self,
        symbol: Union[str, List[str]],
        start_date: str,
        end_date: str,
        retry_times: int = 3
    ) -> pd.DataFrame:
        """获取指数历史日线数据"""
        return self.fetch_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            asset_type=AssetType.INDEX,
            retry_times=retry_times
        )

    def fetch_fund_nav(
        self,
        fund_code: str,
        start_date: str,
        end_date: str,
        retry_times: int = 3
    ) -> pd.DataFrame:
        """
        获取公募基金净值序列。

        :param fund_code: 基金代码（如 '003956.OF'）
        :param start_date: 开始日期 (YYYYMMDD)
        :param end_date: 结束日期 (YYYYMMDD)
        :param retry_times: 失败重试次数
        :return: DataFrame 包含 unit_nav, accumulated_nav, adjusted_nav
        """
        ts_code = self._normalize_code(fund_code, AssetType.FUND)
        logger.info(f"[Tushare] 准备获取基金净值：{ts_code} ({start_date} ~ {end_date})")

        df = self._call_api_with_retry(
            'fund_nav',
            max_retries=retry_times,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

        if df is None or df.empty:
            logger.warning(f"[Tushare] {ts_code} 返回基金净值数据为空")
            return pd.DataFrame()

        # 标准化列名
        column_mapping = AssetType.FUND.tushare_column_mapping
        df = df.rename(columns=column_mapping)

        # 基金接口返回的是 nav_date，映射为 trade_date
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')

        numeric_cols = ['unit_nav', 'accumulated_nav', 'adjusted_nav']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if 'ts_code' in df.columns:
            df = df.rename(columns={'ts_code': 'fund_code'})
        else:
            df['fund_code'] = ts_code

        logger.info(f"[Tushare] {ts_code} 成功获取 {len(df)} 条基金净值记录")
        return df

    def fetch_fund_nav_with_prev(
        self,
        fund_code: str,
        target_date: str,
        trade_calendar_service
    ) -> pd.DataFrame:
        """
        获取基金 T 日和 T-1 日净值，并转换为 close/pre_close 格式。
        """
        prev_trading_date = trade_calendar_service.get_previous_trading_date(target_date, days_back=1)
        if not prev_trading_date:
            from datetime import timedelta
            target_dt = datetime.strptime(target_date, "%Y%m%d")
            prev_dt = target_dt - timedelta(days=3)
            prev_trading_date = prev_dt.strftime("%Y%m%d")

        logger.info(f"[Tushare] 基金查询日期范围：[{prev_trading_date}, {target_date}]")
        df = self.fetch_fund_nav(fund_code, prev_trading_date, target_date)

        if df is None or df.empty:
            return pd.DataFrame()

        return self._convert_fund_nav_to_price(df, target_date)

    def _convert_fund_nav_to_price(self, df: pd.DataFrame, target_date: str) -> pd.DataFrame:
        """将基金净值序列转换为 close/pre_close 格式"""
        df = df.sort_values('trade_date')

        df_target = df[df['trade_date'].dt.strftime('%Y%m%d') == target_date]
        df_prev = df[df['trade_date'].dt.strftime('%Y%m%d') < target_date]

        if df_target.empty:
            logger.warning(f"目标日期 {target_date} 无基金净值数据")
            return pd.DataFrame()

        t_day_nav = df_target.iloc[0]['unit_nav']
        t_minus_1_nav = df_prev.iloc[-1]['unit_nav'] if not df_prev.empty else t_day_nav

        result = pd.DataFrame([{
            'trade_date': target_date,
            'fund_code': df_target.iloc[0]['fund_code'],
            'close': t_day_nav,
            'pre_close': t_minus_1_nav,
            'unit_nav': t_day_nav,
            'accumulated_nav': df_target.iloc[0]['accumulated_nav'],
            'adjusted_nav': df_target.iloc[0]['adjusted_nav'],
            'prev_unit_nav': t_minus_1_nav
        }])

        return result


# 导出全局单例
tushare_provider = TushareProvider()
