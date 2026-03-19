# skills/market_data/providers/ifind_provider.py

import iFinDPy as ifd
import pandas as pd
from datetime import datetime
from typing import Optional, List, Union
from config.settings import settings
from config.enums import AssetType  # 【关键】导入全局枚举
from utils.logger import logger


class iFinDProvider:
    """
    iFinD 数据提供者 (单例模式)

    特性：
    1. 单例：整个应用只登录一次。
    2. 懒加载：第一次调用数据接口时自动检查并登录。
    3. 自动清理：配合 atexit 或手动调用 disconnect 安全登出。
    """

    _instance: Optional['iFinDProvider'] = None
    _is_logged_in: bool = False

    def __new__(cls, *args, **kwargs):
        """单例模式核心：确保只创建一个实例"""
        if cls._instance is None:
            cls._instance = super(iFinDProvider, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """
        初始化配置信息。
        注意：__init__ 在单例模式下可能会被多次调用（如果多处 new），
        所以需要用标志位防止重复初始化配置。
        """
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.username = getattr(settings, 'IFIND_USERNAME', None)
        self.pin = getattr(settings, 'IFIND_PIN', None)

        if not self.username or not self.pin:
            logger.warning("⚠️ 配置缺失：未在 settings 中找到 IFIND_USERNAME 或 IFIND_PIN")

        self._initialized = True

    def connect(self) -> bool:
        """
        显式登录。如果已登录则直接返回。
        """
        if self._is_logged_in:
            return True

        if not self.username or not self.pin:
            raise ValueError("iFinD 登录失败：缺少用户名或 PIN 码配置。")

        try:
            logger.info("🔑 正在连接 iFinD 数据终端...")
            # 调用 iFinD 官方登录接口
            login_res = ifd.THS_iFinDLogin(self.username, self.pin)

            if login_res == 0:
                self._is_logged_in = True
                logger.info("✅ iFinD 连接成功 (会话保持中)。")
                return True
            elif login_res == 2:
                logger.error("❌ iFinD 登录失败，用户名或密码错误。")
            else:
                logger.error("❌ iFinD 登录失败，请检查账号密码或终端是否开启。")
                return False
        except Exception as e:
            logger.error(f"❌ iFinD 连接异常：{e}")
            self._is_logged_in = False
            return False

    def disconnect(self):
        """
        显式登出。建议在程序退出前调用。
        """
        if self._is_logged_in:
            try:
                logger.info("👋 正在断开 iFinD 连接...")
                ifd.THS_iFinDLogout()
                self._is_logged_in = False
                logger.info("✅ iFinD 已安全断开。")
            except Exception as e:
                logger.error(f"⚠️ 登出时发生错误：{e}")
        else:
            logger.debug("ℹ️ iFinD 当前未连接，跳过登出操作。")

    def _ensure_connected(self):
        """内部辅助：确保在执行数据请求前已连接"""
        if not self._is_logged_in:
            if not self.connect():
                raise ConnectionError("无法连接到 iFinD。请检查网络、账号配置或同花顺终端状态。")

    def fetch_history(
            self,
            symbol: Union[str, List[str]],
            start_date: str,
            end_date: str,
            asset_type: AssetType = AssetType.STOCK
    ) -> pd.DataFrame:
        """
        获取历史行情数据

        :param symbol: 股票代码 (如 '000001.SZ')，支持列表
        :param start_date: 开始日期 (YYYYMMDD)
        :param end_date: 结束日期 (YYYYMMDD)
        :param asset_type: 资产类型 (使用全局枚举 AssetType)
        :return: 标准化后的 Pandas DataFrame
        """
        # 1. 确保连接
        self._ensure_connected()

        # 处理 symbol 输入
        if isinstance(symbol, list):
            ths_code = ",".join(symbol)
            logger.debug(f"批量查询代码：{ths_code}")
        else:
            ths_code = str(symbol)

        # 日期格式转换 (YYYYMMDD -> YYYY-MM-DD)
        try:
            start_dt = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError as e:
            logger.error(f"日期格式错误，必须为 YYYYMMDD: {e}")
            raise e

        logger.info(f"[iFinD] 获取 {asset_type.value} 数据：{ths_code} ({start_dt} ~ {end_dt})")

        try:
            # 2. 从枚举中获取 iFinD 特定参数 (消除硬编码)
            indicator = asset_type.ifind_indicator
            global_param = asset_type.ifind_global_param

            if not indicator:
                raise ValueError(f"不支持的资产类型配置：{asset_type}")

            # 3. 调用 iFinD 接口
            df = ifd.THS_DS(
                thscode=ths_code,
                jsonIndicator=indicator,
                jsonparam='100',  # 假设固定参数，如有需要也可放入枚举
                globalparam=global_param,
                begintime=start_dt,
                endtime=end_dt
            ).data

            if df is None or df.empty:
                logger.warning(f"[iFinD] 未返回数据：{ths_code}")
                return pd.DataFrame()

            # 4. 数据标准化与清洗
            target_price_col = asset_type.ifind_price_column

            # 定义映射关系 (只映射存在的列，防止报错)
            raw_cols = df.columns.tolist()
            column_mapping = {}

            if 'time' in raw_cols:
                column_mapping['time'] = 'date'
            if 'thscode' in raw_cols:
                column_mapping['thscode'] = 'scrt_code'
            if indicator in raw_cols:
                column_mapping[indicator] = target_price_col

            if column_mapping:
                df = df.rename(columns=column_mapping)

            # 统一日期列格式
            if 'date' in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                # 额外生成系统标准的 trade_date (YYYYMMDD 字符串)
                df['trade_date'] = df['date'].dt.strftime('%Y%m%d')

            logger.info(f"[iFinD] 成功获取 {len(df)} 条记录。")
            return df

        except Exception as e:
            logger.error(f"[iFinD] 数据获取失败：{e}")
            # 遇到严重网络错误时，可以选择标记为未登录，以便下次重试时重新登录
            # self._is_logged_in = False
            raise e


# 导出一个全局单例实例，方便其他模块直接 import 使用
ifind_provider = iFinDProvider()