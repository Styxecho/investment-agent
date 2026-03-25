# skills/market_data/providers/ifind_provider.py

import iFinDPy as ifd
import pandas as pd
from datetime import datetime
from typing import Optional, List, Union
import time
from config.settings import settings
from config.enums import AssetType
from utils.logger import logger


class iFinDProvider:
    """
    iFinD 数据提供者 (单例模式)

    更新特性：
    1. 支持获取多字段 (Close + Pre_Close)。
    2. 内置指数退避重试机制 (Retry with Exponential Backoff)。
    3. 保持原有的单例、懒加载特性。
    """

    _instance: Optional['iFinDProvider'] = None
    _is_logged_in: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(iFinDProvider, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.username = getattr(settings, 'IFIND_USERNAME', None)
        self.pin = getattr(settings, 'IFIND_PIN', None)

        if not self.username or not self.pin:
            logger.warning("⚠️ 配置缺失：未在 settings 中找到 IFIND_USERNAME 或 IFIND_PIN")

        self._initialized = True

    def connect(self) -> bool:
        if self._is_logged_in:
            return True

        if not self.username or not self.pin:
            raise ValueError("iFinD 登录失败：缺少用户名或 PIN 码配置。")

        try:
            logger.info("🔑 正在连接 iFinD 数据终端...")
            login_res = ifd.THS_iFinDLogin(self.username, self.pin)

            if login_res == 0:
                self._is_logged_in = True
                logger.info("✅ iFinD 连接成功 (会话保持中)。")
                return True
            elif login_res == 2:
                logger.error("❌ iFinD 登录失败，用户名或密码错误。")
            else:
                logger.error("❌ iFinD 登录失败，未知原因。")
            return False
        except Exception as e:
            logger.error(f"❌ iFinD 连接异常：{e}")
            self._is_logged_in = False
            return False

    def disconnect(self):
        if self._is_logged_in:
            try:
                logger.info("👋 正在断开 iFinD 连接...")
                ifd.THS_iFinDLogout()
                self._is_logged_in = False
                logger.info("✅ iFinD 已安全断开。")
            except Exception as e:
                logger.error(f"⚠️ 登出时发生错误：{e}")

    def _ensure_connected(self):
        if not self._is_logged_in:
            if not self.connect():
                raise ConnectionError("无法连接到 iFinD。请检查网络、账号配置或同花顺终端状态。")

    def fetch_history(
            self,
            symbol: Union[str, List[str]],
            start_date: str,
            end_date: str,
            asset_type: AssetType = AssetType.STOCK,
            retry_times: int = 3
    ) -> pd.DataFrame:
        """
        获取历史行情数据 (包含收盘价和前收盘价)

        :param symbol: 股票代码 (如 '000001.SZ')，支持列表
        :param start_date: 开始日期 (YYYYMMDD)
        :param end_date: 结束日期 (YYYYMMDD)
        :param asset_type: 资产类型
        :param retry_times: 失败重试次数
        :return: 标准化后的 Pandas DataFrame (包含 'close', 'pre_close' 列)
        """
        # 1. 确保连接
        self._ensure_connected()

        # 处理 symbol 输入
        if isinstance(symbol, list):
            ths_code = ",".join(symbol)
            logger.debug(f"批量查询代码：{ths_code}")
        else:
            ths_code = str(symbol)

        # 日期格式转换
        try:
            start_dt = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError as e:
            logger.error(f"日期格式错误，必须为 YYYYMMDD: {e}")
            raise e

        logger.info(f"[iFinD] 准备获取数据：{ths_code} ({start_dt} ~ {end_dt})")

        # 2. 构造请求指标 (关键修改：确保包含 pre_close)
        close_indicator = asset_type.ifind_close_price_indicator
        pre_close_indicator = asset_type.ifind_pre_close_indicator

        if pre_close_indicator:
            request_indicator = f"{close_indicator},{pre_close_indicator}"
        else:
            request_indicator = close_indicator

        logger.info(f"[iFinD] 请求指标：{request_indicator}")
        global_param = asset_type.ifind_global_param or '100'

        # 3. 执行带重试的请求
        df = None
        last_error = None

        for attempt in range(retry_times):
            try:
                logger.debug(f"[iFinD] 尝试请求 (第 {attempt + 1}/{retry_times} 次)...")

                res = ifd.THS_DS(
                    thscode=ths_code,
                    jsonIndicator=request_indicator,
                    jsonparam='100',
                    globalparam=global_param,
                    begintime=start_dt,
                    endtime=end_dt
                )

                if res and hasattr(res, 'data'):
                    df = res.data
                    if df is not None and not df.empty:
                        logger.info(f"[iFinD] 第 {attempt + 1} 次请求成功，获取 {len(df)} 条记录。")
                        break  # 成功则跳出重试循环
                    else:
                        logger.warning(f"[iFinD] 返回数据为空。")
                        break  # 空数据通常不需要重试

                # 如果 res 为 None 或没有 data 属性，视为本次请求无效，进入重试
                last_error = Exception("API 返回结果为空或格式异常")

            except Exception as e:
                last_error = e
                logger.warning(f"[iFinD] 第 {attempt + 1} 次请求失败：{e}")
                if attempt < retry_times - 1:
                    wait_time = 2 ** attempt  # 指数退避：1s, 2s, 4s
                    logger.info(f"[iFinD] 等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"[iFinD] 达到最大重试次数 {retry_times}，最终失败。")
                    raise e  # 抛出最后一次错误

        if df is None or df.empty:
            if last_error:
                raise last_error
            return pd.DataFrame()

        # 4. 数据标准化与清洗 (关键修改：映射 pre_close)
        raw_cols = df.columns.tolist()
        column_mapping = {}

        # 映射时间
        if 'time' in raw_cols:
            column_mapping['time'] = 'date'
        # 映射代码
        if 'thscode' in raw_cols:
            column_mapping['thscode'] = 'scrt_code'

        # 映射收盘价
        if close_indicator in raw_cols:
            column_mapping[close_indicator] = asset_type.ifind_close_price_column
        else:
            logger.warning(f"[iFinD] 未找到预期的收盘价列：{close_indicator}. 当前列：{raw_cols}")
        # 映射昨收价 (利用枚举定义的原始列名)
        # 只有当请求了昨收指标，且返回中存在该列时才映射
        if pre_close_indicator:
            if pre_close_indicator in raw_cols:
                column_mapping[pre_close_indicator] = asset_type.ifind_pre_close_column
            else:
                logger.warning(f"[iFinD] 请求了昨收但未找到列：{pre_close_indicator}. 当前列：{raw_cols}")

        if column_mapping:
            df = df.rename(columns=column_mapping)

        # 统一日期列格式
        if 'date' in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df['trade_date'] = df['date'].dt.strftime('%Y%m%d')

        # 确保需要的列存在 (可选检查)
        required_cols = ['scrt_code', 'trade_date', 'close']
        if pre_close_indicator:
            required_cols.append('pre_close')
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.error(f"[iFinD] 标准化后缺失关键列：{missing}")
            # 视情况决定是否抛错

        return df


# 导出全局单例
ifind_provider = iFinDProvider()