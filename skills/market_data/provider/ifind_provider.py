# skills/market_data/providers/ifind_provider.py

# 延迟导入 iFinDPy，避免模块加载时报错
try:
    import iFinDPy as ifd
    IFIND_AVAILABLE = True
except ImportError:
    IFIND_AVAILABLE = False
    ifd = None

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

        if not IFIND_AVAILABLE:
            logger.error("❌ iFinDPy 模块未安装，无法使用 iFinD 数据源")
            return False

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

        # 2. 构造请求指标 (关键修改：确保包含 pre_close 和 adjust_factor)
        close_indicator = asset_type.ifind_close_price_indicator
        pre_close_indicator = asset_type.ifind_pre_close_indicator
        adjust_factor_indicator = asset_type.ifind_adjust_factor_indicator

        indicators = [close_indicator]
        if pre_close_indicator:
            indicators.append(pre_close_indicator)
        if adjust_factor_indicator:
            indicators.append(adjust_factor_indicator)

        request_indicator = ";".join(indicators)
        
        # 【关键修复】根据指标数量生成 jsonparam
        indicator_count = len(indicators)
        jsonparam = ';' * (indicator_count - 1)

        logger.info(f"[iFinD] 请求指标：{request_indicator} ({indicator_count}个指标)")
        logger.info(f"[iFinD] 参数：jsonparam='{jsonparam}'")
        global_param = asset_type.ifind_global_param or ''

        # 3. 执行带重试的请求
        df = None
        last_error = None

        for attempt in range(retry_times):
            try:
                logger.debug(f"[iFinD] 尝试请求 (第 {attempt + 1}/{retry_times} 次)...")

                res = ifd.THS_DS(
                    thscode=ths_code,
                    jsonIndicator=request_indicator,
                    jsonparam=jsonparam,
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
        
        # 映射复权因子
        if adjust_factor_indicator:
            if adjust_factor_indicator in raw_cols:
                column_mapping[adjust_factor_indicator] = 'adjust_factor'
            else:
                logger.warning(f"[iFinD] 请求了复权因子但未找到列：{adjust_factor_indicator}. 当前列：{raw_cols}")

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
        if adjust_factor_indicator:
            required_cols.append('adjust_factor')
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.error(f"[iFinD] 标准化后缺失关键列：{missing}")
            # 视情况决定是否抛错

        return df
    
    def fetch_fund_nav(
        self,
        fund_code: str,
        start_date: str,
        end_date: str,
        retry_times: int = 3
    ) -> pd.DataFrame:
        """
        获取公募基金净值序列
        
        :param fund_code: 基金代码（如 '003956.OF'）
        :param start_date: 开始日期（YYYYMMDD）
        :param end_date: 结束日期（YYYYMMDD）
        :param retry_times: 重试次数
        :return: DataFrame 包含 unit_nav, accumulated_nav, adjusted_nav 列
        
        API 调用示例：
        THS_DS('003956.OF','ths_unit_nv_fund;ths_accum_unit_nv_fund;ths_adjustment_nv_fund','','block:latest','2026-04-03','2026-04-05')
        """
        # 1. 确保连接
        self._ensure_connected()
        
        # 2. 日期格式转换
        try:
            start_dt = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError as e:
            logger.error(f"日期格式错误，必须为 YYYYMMDD: {e}")
            raise e
        
        logger.info(f"[iFinD] 准备获取基金净值：{fund_code} ({start_dt} ~ {end_dt})")
        
        # 3. 构造请求指标（基金需要三个净值）
        request_indicator = AssetType.FUND.ifind_fund_nav_indicators
        global_param = AssetType.FUND.ifind_global_param
        
        # 【关键修复】根据 jsonIndicator 中的分号数量生成 jsonparam
        # 如果有 3 个指标（2 个分号），则 jsonparam=';;'
        indicator_count = request_indicator.count(';') + 1
        jsonparam = ';' * (indicator_count - 1)
        
        logger.info(f"[iFinD] 请求指标：{request_indicator} ({indicator_count}个指标)")
        logger.info(f"[iFinD] 参数：jsonparam='{jsonparam}'")
        
        # 4. 执行带重试的请求
        df = None
        last_error = None
        
        for attempt in range(retry_times):
            try:
                logger.debug(f"[iFinD] 尝试请求 (第 {attempt + 1}/{retry_times} 次)...")
                
                res = ifd.THS_DS(
                    thscode=fund_code,
                    jsonIndicator=request_indicator,
                    jsonparam=jsonparam,
                    globalparam=global_param,
                    begintime=start_dt,
                    endtime=end_dt
                )
                
                if res and hasattr(res, 'data'):
                    df = res.data
                    if df is not None and not df.empty:
                        logger.info(f"[iFinD] 第 {attempt + 1} 次请求成功，获取 {len(df)} 条记录。")
                        break
                    else:
                        logger.warning(f"[iFinD] 返回数据为空。")
                        break
                
                last_error = Exception("API 返回结果为空或格式异常")
                
            except Exception as e:
                last_error = e
                logger.warning(f"[iFinD] 第 {attempt + 1} 次请求失败：{e}")
                if attempt < retry_times - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"[iFinD] 等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"[iFinD] 达到最大重试次数 {retry_times}，最终失败。")
                    raise e
        
        if df is None or df.empty:
            if last_error:
                raise last_error
            return pd.DataFrame()
        
        # 5. 数据标准化与清洗
        raw_cols = df.columns.tolist()
        column_mapping = {}
        
        # 映射时间
        if 'time' in raw_cols:
            column_mapping['time'] = 'trade_date'
        
        # 映射代码
        if 'thscode' in raw_cols:
            column_mapping['thscode'] = 'fund_code'
        
        # 映射三种净值
        if 'ths_unit_nv_fund' in raw_cols:
            column_mapping['ths_unit_nv_fund'] = 'unit_nav'
        if 'ths_accum_unit_nv_fund' in raw_cols:
            column_mapping['ths_accum_unit_nv_fund'] = 'accumulated_nav'
        if 'ths_adjustment_nv_fund' in raw_cols:
            column_mapping['ths_adjustment_nv_fund'] = 'adjusted_nav'
        
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        # 统一日期列格式
        if 'trade_date' in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
        
        return df
    
    def fetch_fund_nav_with_prev(
        self,
        fund_code: str,
        target_date: str,
        trade_calendar_service
    ) -> pd.DataFrame:
        """
        获取基金 T 日和 T-1 日净值，并转换为 close/pre_close 格式
        
        :param fund_code: 基金代码
        :param target_date: 目标日期（YYYYMMDD）
        :param trade_calendar_service: 交易日历服务实例
        :return: DataFrame 包含 close (T 日净值) 和 pre_close (T-1 日净值)
        
        核心逻辑：
        1. 查询交易日历，找到 T-1 交易日
        2. 调用 fetch_fund_nav 查询 [T-1, T] 范围
        3. 将返回的 2 条记录转换为 1 行（close + pre_close）
        """
        # 1. 获取 T-1 交易日
        prev_trading_date = trade_calendar_service.get_previous_trading_date(target_date, days_back=1)
        
        if not prev_trading_date:
            logger.warning(f"无法找到 {target_date} 的前一个交易日，使用默认逻辑")
            # 降级策略：简单减 3 天
            from datetime import timedelta
            target_dt = datetime.strptime(target_date, "%Y%m%d")
            prev_dt = target_dt - timedelta(days=3)
            prev_trading_date = prev_dt.strftime("%Y%m%d")
        
        logger.info(f"[iFinD] 基金查询日期范围：[{prev_trading_date}, {target_date}]")
        
        # 2. 查询净值序列
        df = self.fetch_fund_nav(fund_code, prev_trading_date, target_date)
        
        if df is None or df.empty:
            return pd.DataFrame()
        
        # 3. 转换为 close/pre_close 格式
        df_converted = self._convert_fund_nav_to_price(df, target_date)
        
        return df_converted
    
    def _convert_fund_nav_to_price(self, df: pd.DataFrame, target_date: str) -> pd.DataFrame:
        """
        将基金净值序列转换为 close/pre_close 格式
        
        输入：
        | trade_date | fund_code | unit_nav | accumulated_nav | adjusted_nav |
        | 2026-04-03 | 003956.OF | 1.2345   | 1.3000          | 1.2800       |
        | 2026-04-04 | 003956.OF | 1.2500   | 1.3100          | 1.2900       |
        
        输出：
        | trade_date | fund_code | close  | pre_close | unit_nav | accumulated_nav | adjusted_nav |
        | 20260404   | 003956.OF | 1.2500 | 1.2345    | 1.2500   | 1.3100          | 1.2900       |
        """
        # 1. 按日期排序
        df = df.sort_values('trade_date')
        
        # 2. 筛选目标日期
        df_target = df[df['trade_date'].dt.strftime('%Y%m%d') == target_date]
        df_prev = df[df['trade_date'].dt.strftime('%Y%m%d') < target_date]
        
        if df_target.empty:
            logger.warning(f"目标日期 {target_date} 无数据")
            return pd.DataFrame()
        
        # 3. 构建结果（只保留 T 日数据，但包含 T-1 日的 pre_close）
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


    def fetch_index_history(
            self,
            symbol: Union[str, List[str]],
            start_date: str,
            end_date: str,
            retry_times: int = 3
    ) -> pd.DataFrame:
        """
        获取指数历史行情数据 (包含收盘价和前收盘价)
        
        封装 iFinD 指数接口：
        THS_DS('921128.SZ,931587.CSI','ths_pre_close_index;ths_close_price_index',';','block:history','2026-04-20','2026-04-23')
        
        :param symbol: 指数代码 (如 '000001.SH', '399001.SZ', '931587.CSI')，支持列表
        :param start_date: 开始日期 (YYYYMMDD)
        :param end_date: 结束日期 (YYYYMMDD)
        :param retry_times: 失败重试次数
        :return: 标准化后的 Pandas DataFrame (包含 'close', 'pre_close' 列)
        """
        return self.fetch_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            asset_type=AssetType.INDEX,
            retry_times=retry_times
        )


# 导出全局单例
ifind_provider = iFinDProvider()