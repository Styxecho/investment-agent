# skills/market_data/service.py

import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from utils.logger import logger
from data_external.db.repositories import MarketDataRepository, FundRepository
from .provider.ifind_provider import ifind_provider
from config.enums import AssetType
from utils.trade_calendar import TradeCalendarService

# 引入基类定义的契约
from skills.base import SkillContext, SkillResult, SkillMeta


class MarketDataService:
    """
    市场数据服务层。
    负责协调 缓存(DB) 和 数据源(iFinD)，并遵循标准输入输出契约。
    """

    def __init__(self):
        self.repo = MarketDataRepository()
        self.fund_repo = FundRepository()  # 基金数据仓储
        self.trade_calendar = TradeCalendarService()  # 交易日历服务
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
        1. 根据 asset_type 判断资产类型
        2. 股票/ETF: 查询 StockDaily 表
        3. 基金：查询 FundDaily 表，并使用交易日历获取 T-1 日数据
        4. 若命中：返回 SkillResult(status='success', source='cache')。
        5. 若未命中：调用 iFinD API，存入 DB，返回结果。
        6. 异常处理：捕获所有异常，返回 status='failed' 的 SkillResult。

        :param context: 包含 target_date 的上下文。
        :param symbol: 资产代码（如 '600519.SH', '003956.OF'）。
        :param asset_type: 资产类型。
        :return: SkillResult 对象。
        """
        target_date = context.target_date  # 格式：YYYYMMDD
        
        # 根据资产类型分发到不同的处理方法
        if asset_type == AssetType.FUND:
            return self._get_fund_daily_data(context, symbol, target_date)
        else:
            # 股票/ETF 使用现有逻辑
            return self._get_stock_daily_data(context, symbol, target_date)
    
    def _get_stock_daily_data(
            self,
            context: SkillContext,
            symbol: str,
            target_date: str
    ) -> SkillResult:
        """
        获取股票/ETF 的日终行情数据（原有逻辑）
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
            
            # 使用交易日历获取 T-1 日，以便查询范围包含 pre_close 所需数据
            prev_trading_date = self.trade_calendar.get_previous_trading_date(target_date, days_back=1)
            if prev_trading_date:
                query_start = prev_trading_date
            else:
                # 降级：往前推 3 天
                target_dt = datetime.strptime(target_date, "%Y%m%d")
                query_start = (target_dt - timedelta(days=3)).strftime("%Y%m%d")
            
            df_cached = self.repo.get_daily_data(symbol, query_start, target_date)

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
                logger.info(f"[Service] 缓存未命中，请求数据：{symbol} @ {target_date}")

                # 尝试 iFinD，失败则降级到 AkShare
                df_new = None
                use_akshare = False
                
                try:
                    if self._ensure_connected():
                        df_new = self.provider.fetch_history(
                            symbol=symbol,
                            start_date=target_date,
                            end_date=target_date,
                            asset_type=asset_type
                        )
                    else:
                        logger.warning("[Service] iFinD 连接失败，降级使用 AkShare")
                        use_akshare = True
                except Exception as e:
                    logger.warning(f"[Service] iFinD 调用失败：{e}，降级使用 AkShare")
                    use_akshare = True
                
                # 降级到 AkShare
                if use_akshare:
                    from .provider.akshare_provider import AkShareProvider
                    akshare = AkShareProvider()
                    logger.info(f"[Service] 使用 AkShare 获取数据：{symbol}")
                    df_new = akshare.fetch_history(symbol, target_date, target_date)

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
    
    def _get_fund_daily_data(
            self,
            context: SkillContext,
            fund_code: str,
            target_date: str
    ) -> SkillResult:
        """
        获取基金日终净值（支持单日或日期范围查询）
        
        逻辑流程：
        1. 检查是否指定了日期范围（start_date, end_date）
        2. 如果是范围查询，直接查询该范围
        3. 如果是单日查询，查询 [T-1, T] 范围以获取昨收净值
        4. 查询缓存或调用 iFinD API
        5. 返回结果
        """
        # 检查是否指定了日期范围
        start_date = context.extra_params.get('start_date') if context.extra_params else None
        end_date = context.extra_params.get('end_date') if context.extra_params else None
        
        # 1. 验证日期格式
        try:
            if start_date:
                datetime.strptime(start_date, "%Y%m%d")
            if end_date:
                datetime.strptime(end_date, "%Y%m%d")
            target_dt = datetime.strptime(target_date, "%Y%m%d")
        except ValueError:
            logger.error(f"无效日期格式")
            return SkillResult(
                data={},
                meta=SkillMeta(
                    source="validation",
                    status="failed",
                    target_date=target_date,
                    message="无效日期格式 (应为 YYYYMMDD)"
                )
            )
        
        # 2. 确定查询范围
        if start_date and end_date:
            # 用户指定了日期范围
            query_start = start_date
            query_end = end_date
            logger.info(f"[Service] 基金日期范围查询：[{query_start}, {query_end}]")
        else:
            # 单日查询，需要获取 T-1 日以计算涨跌
            prev_trading_date = self.trade_calendar.get_previous_trading_date(target_date, days_back=1)
            if not prev_trading_date:
                prev_trading_date = (target_dt - timedelta(days=3)).strftime("%Y%m%d")
            query_start = prev_trading_date
            query_end = target_date
            logger.info(f"[Service] 基金单日查询：[{query_start}, {query_end}]")
        
        meta_source = "unknown"
        meta_status = "failed"
        meta_message = ""
        df_result: Optional[pd.DataFrame] = None
        
        try:
            # 3. 尝试从数据库获取
            df_cached = self.fund_repo.get_fund_nav(fund_code, query_start, query_end)
            
            if df_cached is not None and not df_cached.empty:
                # 缓存命中
                df_result = df_cached
                meta_source = "cache"
                meta_status = "success"
                meta_message = f"数据来自本地缓存 ({query_start} ~ {query_end})"
                logger.info(f"[Service] ✅ 缓存命中 (Source: DB)")
            
            # 4. 缓存未命中，调用 iFinD
            if df_result is None:
                logger.info(f"[Service] 缓存未命中，请求 iFinD: {fund_code} @ [{query_start}, {query_end}]")
                
                # 调用 Provider 获取基金净值
                df_new = self.provider.fetch_fund_nav(
                    fund_code=fund_code,
                    start_date=query_start,
                    end_date=query_end
                )
                
                if df_new is None or df_new.empty:
                    meta_message = f"iFinD 返回空数据 ({query_start} ~ {query_end})"
                    logger.warning(f"[Service] {meta_message}")
                    return SkillResult(
                        data={},
                        meta=SkillMeta(
                            source="api",
                            status="failed",
                            target_date=target_date,
                            message=meta_message
                        )
                    )
                
                # 5. 保存到数据库
                logger.info(f"[Service] 💾 正在保存新数据到本地...")
                self.fund_repo.save_fund_nav(df_new, fund_code)
                
                df_result = df_new
                meta_source = "api"
                meta_status = "success"
                meta_message = f"数据来自 iFinD API ({query_start} ~ {query_end})"
            
            # 6. 构建最终结果
            # 如果是日期范围查询，返回所有数据
            if start_date and end_date:
                # 返回净值序列
                data_list = df_result.to_dict('records')
                hint = f"{fund_code} 在 {start_date} 至 {end_date} 期间共 {len(data_list)} 个交易日："
                for i, row in enumerate(data_list):
                    unit_nav = row.get('unit_nav', 0)
                    hint += f" {row.get('trade_date')}={unit_nav:.4f}"
                    if i < len(data_list) - 1:
                        hint += ","
            else:
                # 单日查询
                row = df_result.iloc[0] if len(df_result) > 0 else None
                if row is None:
                    return SkillResult(
                        data={},
                        meta=SkillMeta(
                            source=meta_source,
                            status="failed",
                            target_date=target_date,
                            message="未找到目标日期数据"
                        )
                    )
                
                data_dict = row.to_dict()
                unit_nav = data_dict.get('unit_nav')
                prev_nav = data_dict.get('prev_unit_nav')
                
                if unit_nav and prev_nav:
                    pct = (float(unit_nav) - float(prev_nav)) / float(prev_nav) * 100
                    hint = f"{fund_code} 在 {target_date} 单位净值为 {unit_nav:.4f}, 较前一交易日上涨 {pct:.2f}%"
                else:
                    hint = f"{fund_code} 在 {target_date} 单位净值为 {unit_nav:.4f}"
                
                return SkillResult(
                    data=data_dict,
                    meta=SkillMeta(
                        source=meta_source,
                        status=meta_status,
                        target_date=target_date,
                        message=meta_message
                    ),
                    summary_hint=hint
                )
            
            # 日期范围查询返回
            return SkillResult(
                data={'nav_series': data_list},
                meta=SkillMeta(
                    source=meta_source,
                    status=meta_status,
                    target_date=target_date,
                    message=meta_message
                ),
                summary_hint=hint
            )
            
        except Exception as e:
            error_msg = f"获取基金数据失败：{str(e)}"
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