# skills/market_data/service.py

import atexit
import pandas as pd
from typing import Optional
from utils.logger import logger

from data_external.db.repositories import MarketDataRepository
from .provider.ifind_provider import ifind_provider
from config.enums import AssetType


class MarketDataService:
    def __init__(self):
        logger.info("🚀 正在初始化 MarketDataService...")

        self.repo = MarketDataRepository()
        self.provider = ifind_provider  # 获取单例

        # [关键修改] 初始化时立即尝试连接，而不是等到第一次取数据
        # 这样如果账号密码错误或终端未开，能立刻报错，方便排查
        try:
            if not self.provider.connect():
                raise ConnectionError("iFinD 初始化连接失败。请检查：1. 账号密码是否正确; 2. 同花顺终端是否已打开并登录。")
            logger.info("✅ MarketDataService 初始化完成 (iFinD 已连接)。")
        except Exception as e:
            logger.error(f"❌ MarketDataService 启动失败：{e}")
            # 可以选择重新抛出异常，阻止程序继续运行，避免后续空转
            raise e

    def get_daily_data(
            self,
            symbol: str,
            start_date: str,
            end_date: str,
            asset_type: AssetType = AssetType.STOCK
    ) -> Optional[pd.DataFrame]:
        """
        获取日线数据 (带缓存逻辑)
        此时 provider 已经是连接状态，_ensure_connected 会直接返回 True
        """
        logger.info(f"请求数据：{symbol} ({asset_type.value})")

        # 1. 尝试从数据库获取
        # 注意：确保 repo.get_daily_data 实现正确，这里假设它存在
        try:
            df_cached = self.repo.get_daily_data(symbol, start_date, end_date)
            if df_cached is not None and not df_cached.empty:
                logger.info(f"✅ [Cache Hit] 从本地数据库获取 {symbol} 数据成功。")
                return df_cached
        except Exception as db_err:
            logger.warning(f"⚠️ 读取缓存失败，将重新获取：{db_err}")

        # 2. 缓存未命中，调用 Provider 获取
        logger.info(f"🌐 [Cache Miss] 本地无数据，调用 iFinD 获取 {symbol}...")
        try:
            # 此时 _ensure_connected 内部检查 _is_logged_in 为 True，直接跳过登录逻辑
            df_new = self.provider.fetch_history(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                asset_type=asset_type
            )

            if df_new.empty:
                logger.warning(f"⚠️ iFinD 返回空数据：{symbol}")
                return None

            # 3. 保存到数据库
            self.repo.save_daily_data(df_new, symbol)

            logger.info(f"💾 数据已保存至本地缓存。")
            return df_new

        except Exception as e:
            logger.error(f"❌ 获取外部数据失败：{e}")
            # 如果是因为会话过期导致的错误，可以在这里尝试重连一次（高级容错）
            # self.provider._is_logged_in = False
            # if self.provider.connect(): ... retry ...
            raise e


# 实例化服务 (这里会触发 __init__ 中的 connect)
try:
    market_data_service = MarketDataService()
except Exception as e:
    # 如果初始化失败，记录日志并创建一个空对象或退出，防止后续引用报错
    logger.critical("无法创建 market_data_service 实例，程序将无法获取数据。")
    market_data_service = None
    # 如果是测试环境，可以选择 sys.exit(1) 强制停止
    # import sys; sys.exit(1)


# --- 生命周期管理 ---
def _shutdown_cleanup():
    """程序退出时的清理钩子"""
    logger.info("🛑 检测到程序退出，正在清理 iFinD 资源...")
    if 'ifind_provider' in globals():
        ifind_provider.disconnect()
    elif market_data_service and hasattr(market_data_service, 'provider'):
        market_data_service.provider.disconnect()


atexit.register(_shutdown_cleanup)