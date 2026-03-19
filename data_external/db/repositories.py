# data_external/db/repositories.py

from sqlalchemy import and_, desc
from datetime import datetime
from typing import Optional, Dict, Any, List
import pandas as pd

from .engine import get_db_session
from .models import StockDaily, StockRealtime
from utils.logger import logger


class MarketDataRepository:
    """
    市场数据仓储层 (Repository Pattern)
    封装所有对 StockDaily 和 StockRealtime 表的数据库操作。
    """
    @staticmethod
    def get_daily_data(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        从数据库获取历史日线数据。
        返回: Pandas DataFrame，如果无数据则返回 None。
        """

        def parse_date(d_str):
            if not d_str:
                return None
            s = str(d_str)
            fmt = "%Y%m%d" if len(s) == 8 else "%Y-%m-%d"
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                return None

        start_dt = parse_date(start_date)
        end_dt = parse_date(end_date)

        if not start_dt or not end_dt:
            logger.error(f"日期解析失败: start={start_date}, end={end_date}")
            return None

        with next(get_db_session()) as db:
            records = db.query(StockDaily).filter(
                and_(
                    StockDaily.symbol == symbol,
                    StockDaily.trade_date >= start_dt,
                    StockDaily.trade_date <= end_dt
                )
            ).order_by(StockDaily.trade_date.asc()).all()

            if not records:
                return None

            # 转换为 DataFrame
            data_list = []
            for r in records:
                data_list.append({
                    'trade_date': r.trade_date.strftime("%Y%m%d"),
                    'open': r.open_price,
                    'high': r.high_price,
                    'low': r.low_price,
                    'close': r.close_price,
                    'vol': r.volume,
                    'amount': r.amount
                })

            df = pd.DataFrame(data_list)
            logger.debug(f"📖 [DB] 从数据库读取 {len(df)} 条记录 ({symbol})")
            return df

    @staticmethod
    def get_latest_realtime(symbol: str, max_age_minutes: int = 5) -> Optional[Dict[str, Any]]:
        """
        获取最新的实时数据。
        如果数据超过 max_age_minutes 分钟，视为过期，返回 None。
        """
        with next(get_db_session()) as db:
            # 获取该股票最新的一条记录
            record = db.query(StockRealtime).filter(
                StockRealtime.symbol == symbol
            ).order_by(desc(StockRealtime.update_time)).first()

            if not record:
                return None

            # 检查时间戳是否过期
            try:
                last_update = datetime.strptime(record.update_time, "%Y-%m-%d %H:%M:%S")
                age_seconds = (datetime.now() - last_update).total_seconds()

                if age_seconds > max_age_minutes * 60:
                    logger.debug(f"⏰ [DB] 实时数据已过期 ({age_seconds}s > {max_age_minutes * 60}s)")
                    return None

                return {
                    'current_price': record.current_price,
                    'change_percent': record.change_percent,
                    'volume': record.volume,
                    'amount': record.amount,
                    'high': getattr(record, 'high', None),
                    'low': getattr(record, 'low', None),
                    'open': getattr(record, 'open', None),
                    'update_time': record.update_time
                }
            except Exception as e:
                logger.error(f"解析实时数据时间出错: {e}")
                return None

    @staticmethod
    def save_realtime_data(symbol: str, data: Dict[str, Any]):
        """
        保存实时数据快照。
        注意：这里采用追加模式，保留历史记录以便分析盘中波动，也可以改为更新模式。
        """
        with next(get_db_session()) as db:
            record = StockRealtime(
                symbol=symbol,
                update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                current_price=data.get('current_price'),
                change_percent=data.get('change_percent'),
                volume=data.get('volume', 0),
                amount=data.get('amount', 0),
                high=data.get('high'),
                low=data.get('low'),
                open=data.get('open')
            )
            db.add(record)
            db.commit()
            logger.debug(f"💾 [DB] 保存实时数据快照: {symbol} @ {record.update_time}")

    @staticmethod
    def save_daily_data(df: pd.DataFrame, symbol: str):
        """
        将历史日线数据保存到数据库。
        兼容 AkShare 返回的中文列名 (如 '日期', '开盘', '收盘' 等)。
        """
        if df.empty:
            logger.warning("尝试保存空的 DataFrame")
            return

        # [关键修复] 统一列名映射，防止因列名不匹配导致数据丢失
        # AkShare 常见列名: 日期, 开盘, 最高, 最低, 收盘, 成交量, 成交额
        # 我们将其映射到代码内部使用的标准英文名
        column_mapping = {
            '日期': 'trade_date',
            'date': 'trade_date',
            'trade_date': 'trade_date',

            '开盘': 'open',
            'open': 'open',

            '最高': 'high',
            'high': 'high',

            '最低': 'low',
            'low': 'low',

            '收盘': 'close',
            'close': 'close',

            '成交量': 'vol',
            'vol': 'vol',
            'volume': 'vol',

            '成交额': 'amount',
            'amount': 'amount',
        }

        # 创建一个新的 DataFrame 副本并重命名列，方便后续处理
        # copy() 避免 SettingWithCopyWarning
        df_clean = df.rename(columns=column_mapping).copy()

        # 检查必须列是否存在
        required_cols = ['trade_date', 'close']
        missing_cols = [col for col in required_cols if col not in df_clean.columns]
        if missing_cols:
            logger.error(f"iFinD 返回数据缺少关键列: {missing_cols}. 当前列: {list(df.columns)}")
            # 尝试打印前几行以便调试
            logger.error(f"数据样例:\n{df.head()}")
            return

        count_saved = 0
        with next(get_db_session()) as db:
            for _, row in df_clean.iterrows():
                # 1. 处理日期格式
                trade_date_val = row.get('trade_date')

                # 如果还是 None，说明映射失败或原始数据为空
                if trade_date_val is None or (isinstance(trade_date_val, str) and not trade_date_val.strip()):
                    logger.warning(f"跳过一行无效日期数据: {row.to_dict()}")
                    continue

                if isinstance(trade_date_val, (str, int)):
                    s_date = str(trade_date_val).strip()
                    # 兼容 YYYYMMDD, YYYY-MM-DD, YYYY/MM/DD
                    if len(s_date) == 8:
                        fmt = "%Y%m%d"
                    elif '-' in s_date:
                        fmt = "%Y-%m-%d"
                    elif '/' in s_date:
                        fmt = "%Y/%m/%d"
                    else:
                        logger.warning(f"未知日期格式: {s_date}")
                        continue

                    try:
                        trade_date = datetime.strptime(s_date, fmt).date()
                    except ValueError:
                        logger.error(f"日期格式解析失败: {s_date}")
                        continue
                elif isinstance(trade_date_val, datetime):
                    trade_date = trade_date_val.date()
                elif hasattr(trade_date_val, 'strftime'):  # pandas Timestamp
                    trade_date = trade_date_val.date()
                else:
                    logger.warning(f"无法处理的日期类型: {type(trade_date_val)}")
                    continue

                # 2. 检查是否已存在
                existing = db.query(StockDaily).filter(
                    and_(
                        StockDaily.symbol == symbol,
                        StockDaily.trade_date == trade_date
                    )
                ).first()

                if not existing:
                    # 辅助函数：安全获取数值，处理 NaN
                    def safe_float(val, default=0.0):
                        if pd.isna(val): return default
                        try:
                            return float(val)
                        except:
                            return default

                    def safe_int(val, default=0):
                        if pd.isna(val): return default
                        try:
                            return int(float(val))
                        except:
                            return default

                    # 3. 构建新记录
                    record = StockDaily(
                        symbol=symbol,
                        trade_date=trade_date,
                        open_price=safe_float(row.get('open')),
                        high_price=safe_float(row.get('high')),
                        low_price=safe_float(row.get('low')),
                        close_price=safe_float(row.get('close')),
                        volume=safe_int(row.get('vol')),
                        amount=safe_float(row.get('amount'))
                    )
                    db.add(record)
                    count_saved += 1

            db.commit()

        if count_saved > 0:
            logger.info(f"💾 [DB] 成功保存 {count_saved} 条新记录到 stock_daily 表 ({symbol})")
        else:
            logger.info(f"ℹ️ [DB] 数据已存在或无有效数据，未写入新记录 ({symbol})")