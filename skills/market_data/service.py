# skills/market_data/service.py

import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from utils.logger import logger
from data_external.db.repositories import MarketDataRepository
from .provider.ifind_provider import ifind_provider
from config.enums import AssetType

# 引入基类定义的契约
from skills.base import SkillContext, SkillResult, SkillMeta


class MarketDataService:
    """
    市场数据服务层。
    负责协调 缓存(DB) 和 数据源(iFinD)，并遵循标准输入输出契约。
    """

    def __init__(self):
        self.repo = MarketDataRepository()
        self.provider = ifind_provider  # 引用全局单例 Provider
        # 注意：这里不再主动 connect()，改为懒加载

    def _ensure_connected(self) -> bool:
        """确保 iFinD 已连接"""
        return self.provider.connect()

    def get_daily_data(
            self,
            context: SkillContext,
            symbol: str,
            asset_type: AssetType = AssetType.STOCK
    ) -> SkillResult:
        """
        获取单日行情数据 (包含 close 和 pre_close)。

        逻辑流程：
        1. 解析日期：从 context.target_date 获取目标日期。
        2. 查缓存：查询 DB 中该日期的数据。
        3. 若命中：返回 SkillResult(status='success', source='cache')。
        4. 若未命中：
           a. 检查 iFinD 连接。
           b. 调用 provider.fetch_history (请求单日)。
           c. 存入 DB。
           d. 返回 SkillResult(status='success', source='api')。
        5. 异常处理：捕获所有异常，返回 status='failed' 的 SkillResult，不抛出异常。

        :param context: 包含 target_date 的上下文。
        :param symbol: 股票代码。
        :param asset_type: 资产类型。
        :return: SkillResult 对象。
        """
        target_date = context.target_date  # 格式：YYYYMMDD

        # 用于构建元数据
        meta_source = "unknown"
        meta_status = "failed"
        meta_message = ""
        result_data: Dict[str, Any] = {}
        df_result: Optional[pd.DataFrame] = None

        try:
            # 1. 尝试从数据库获取
            # 注意：repo.get_daily_data 需要支持查询单日或日期范围
            # 假设 repo 接口是 get_daily_data(symbol, start, end)
            logger.info(f"[Service] 正在查询缓存：{symbol} @ {target_date}")

            # 为了获取 pre_close 的校验，或者防止边界问题，我们可以查当天
            # 如果 repo 实现是精确匹配日期，则 start=end
            df_cached = self.repo.get_daily_data(symbol, target_date, target_date)

            if df_cached is not None and not df_cached.empty:
                # 检查关键字段是否存在 (close, pre_close)
                if 'close' in df_cached.columns and 'pre_close' in df_cached.columns:
                    logger.info(f"[Service] ✅ 缓存命中 (Source: DB)")
                    df_result = df_cached
                    meta_source = "cache"
                    meta_status = "success"
                    meta_message = f"数据来自本地缓存 ({target_date})"
                else:
                    logger.warning(f"[Service] ⚠️ 缓存数据不完整 (缺失 close/pre_close)，重新获取。")
                    df_cached = None  # 强制走刷新逻辑

            # 2. 缓存未命中或数据不完整，调用 Provider
            if df_result is None:
                logger.info(f"[Service] 🌐 缓存未命中，请求 iFinD: {symbol} @ {target_date}")

                if not self._ensure_connected():
                    raise ConnectionError("无法连接 iFinD 终端")

                # 调用 Provider (已包含重试逻辑)
                # 请求范围：只请求当天即可，因为 API 返回的 pre_close 字段已经包含了昨收信息
                df_new = self.provider.fetch_history(
                    symbol=symbol,
                    start_date=target_date,
                    end_date=target_date,
                    asset_type=asset_type
                )

                if df_new is None or df_new.empty:
                    meta_message = f"iFinD 返回空数据 ({target_date})"
                    logger.warning(f"[Service] {meta_message}")
                    # 返回空结果的失败状态
                    return SkillResult(
                        data={},
                        meta=SkillMeta(
                            source="api",
                            status="failed",
                            target_date=target_date,
                            message=meta_message
                        )
                    )

                # 3. 保存到数据库
                logger.info(f"[Service] 💾 正在保存新数据到本地...")
                # 假设 repo.save_daily_data 能处理 DataFrame
                self.repo.save_daily_data(df_new, symbol)

                df_result = df_new
                meta_source = "api"
                meta_status = "success"
                meta_message = f"数据来自 iFinD API ({target_date})"

            # 4. 构建最终结果
            # 提取目标日期的那一行数据转为字典，方便 LLM 阅读
            # 假设 df_result 中 trade_date 列存在且匹配
            row = df_result[df_result['trade_date'] == target_date]

            if row.empty:
                # 极端情况：API 返回了数据但没有目标日期这一行（比如节假日）
                meta_message = f"数据中不包含目标日期 {target_date} (可能是非交易日)"
                return SkillResult(
                    data={},
                    meta=SkillMeta(
                        source=meta_source,
                        status="partial",  # 部分成功或无数据
                        target_date=target_date,
                        message=meta_message
                    )
                )

            # 将 Series 转为 Dict
            data_dict = row.iloc[0].to_dict()

            # 生成给 LLM 的自然语言提示
            close_val = data_dict.get('close')
            pre_close_val = data_dict.get('pre_close')
            hint = ""
            if close_val and pre_close_val:
                try:
                    pct = (float(close_val) - float(pre_close_val)) / float(pre_close_val) * 100
                    hint = f"{symbol} 在 {target_date} 收盘价为 {close_val}, 昨收 {pre_close_val}, 涨跌幅 {pct:.2f}%"
                except:
                    hint = f"{symbol} 在 {target_date} 收盘价 {close_val}, 昨收 {pre_close_val}"

            return SkillResult(
                data=data_dict,  # 或者可以放整个 df_result.to_dict()，视下游需求
                meta=SkillMeta(
                    source=meta_source,
                    status=meta_status,
                    target_date=target_date,
                    message=meta_message
                ),
                summary_hint=hint
            )

        except Exception as e:
            error_msg = f"获取数据失败：{str(e)}"
            logger.error(f"[Service] ❌ {error_msg}")
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="none",
                    status="failed",
                    target_date=target_date,
                    message=error_msg
                )
            )

# 注意：移除了模块级别的全局实例化 market_data_service
# 推荐在 Skill 类的 __init__ 中实例化此类，或通过依赖注入传入