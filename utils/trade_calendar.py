# utils/trade_calendar.py
"""
交易日历服务（基于 CSV 文件）

用途：
1. 判断指定日期是否为交易日
2. 获取前一个/后一个交易日
3. 获取日期范围内的所有交易日

维护说明：
- 每年更新一次 data_external/reference/trade_calendar_YYYY.csv
- 仅记录非周末的法定节假日
"""
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Set, Tuple
from utils.logger import logger


class TradeCalendarService:
    """交易日历服务（单例模式）"""
    
    _instance: Optional['TradeCalendarService'] = None
    _holidays: Set[str] = set()
    _initialized: bool = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(TradeCalendarService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, calendar_year: Optional[int] = None):
        if self._initialized:
            return
        
        # 默认使用当前年份，或指定年份
        if calendar_year is None:
            calendar_year = datetime.now().year
        
        self.calendar_year = calendar_year
        self._load_holidays()
        self._initialized = True
    
    def _get_calendar_file_path(self, year: int) -> Path:
        """获取指定年份的交易日历文件路径"""
        # 尝试特定年份的文件
        specific_file = Path(__file__).parent.parent / 'data_external' / 'reference' / f'trade_calendar_{year}.csv'
        if specific_file.exists():
            return specific_file
        
        # 回退到通用文件
        general_file = Path(__file__).parent.parent / 'data_external' / 'reference' / 'trade_calendar.csv'
        if general_file.exists():
            return general_file
        
        # 如果都不存在，返回特定年份路径（用于创建新文件）
        return specific_file
    
    def _load_holidays(self):
        """加载节假日 CSV 文件（加载所有年份数据）"""
        csv_path = self._get_calendar_file_path(self.calendar_year)
        
        if not csv_path.exists():
            logger.warning(f"交易日历文件不存在：{csv_path}")
            logger.warning("将仅使用周末判断，所有非周末日期视为交易日")
            return
        
        self._holidays = set()
        try:
            # 使用 utf-8-sig 编码自动处理 BOM
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                # 跳过注释行（以#开头的行）
                lines = [line for line in f if not line.strip().startswith('#')]
            
            # 重新解析过滤后的行
            import io
            csv_content = '\n'.join(lines)
            reader = csv.DictReader(io.StringIO(csv_content))
            
            for row in reader:
                date = row.get('date', '').strip()
                is_holiday = row.get('is_holiday', '').strip()
                
                if not date or date.startswith('#'):
                    continue
                
                if is_holiday == '1':
                    self._holidays.add(date)
            
            logger.info(f"交易日历已加载：{len(self._holidays)} 个节假日 (全量数据)")
            
        except Exception as e:
            logger.error(f"加载交易日历失败：{e}")
            import traceback
            traceback.print_exc()
    
    def is_trading_day(self, trade_date: str) -> bool:
        """
        判断指定日期是否为交易日
        
        :param trade_date: 日期（YYYYMMDD 或 YYYY-MM-DD）
        :return: True=交易日，False=非交易日
        """
        try:
            # 标准化日期格式
            date_obj = self._parse_date(trade_date)
            date_str = date_obj.strftime("%Y-%m-%d")
            
            # 检查周末
            if date_obj.weekday() >= 5:  # 周六=5, 周日=6
                return False
            
            # 检查节假日
            if date_str in self._holidays:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"判断交易日失败：{e}")
            return False
    
    def get_previous_trading_date(self, trade_date: str, days_back: int = 1) -> Optional[str]:
        """
        获取指定日期前的第 N 个交易日
        
        :param trade_date: 基准日期（YYYYMMDD）
        :param days_back: 往前推多少个交易日（默认 1，即 T-1）
        :return: T-N 交易日日期（YYYYMMDD），如果找不到则返回 None
        
        示例：
        - get_previous_trading_date('20260407', 1) → '20260404'（周一的前一个交易日是周五）
        - get_previous_trading_date('20260407', 3) → '20260402'（往前推 3 个交易日）
        """
        try:
            current = self._parse_date(trade_date)
            days_found = 0
            
            # 往前遍历，直到找到足够的交易日
            while days_found < days_back:
                current -= timedelta(days=1)
                
                # 检查是否为交易日
                if self.is_trading_day(current.strftime("%Y%m%d")):
                    days_found += 1
                
                # 安全限制：最多往前推 365 天
                if (datetime.now() - current).days > 365:
                    logger.warning(f"往前推算超过 365 天，停止搜索")
                    return None
            
            return current.strftime("%Y%m%d")
            
        except Exception as e:
            logger.error(f"获取前一个交易日失败：{e}")
            return None
    
    def get_next_trading_date(self, trade_date: str, days_forward: int = 1) -> Optional[str]:
        """
        获取指定日期后的第 N 个交易日
        
        :param trade_date: 基准日期（YYYYMMDD）
        :param days_forward: 往后推多少个交易日（默认 1，即 T+1）
        :return: T+N 交易日日期（YYYYMMDD）
        """
        try:
            current = self._parse_date(trade_date)
            days_found = 0
            
            while days_found < days_forward:
                current += timedelta(days=1)
                
                if self.is_trading_day(current.strftime("%Y%m%d")):
                    days_found += 1
                
                # 安全限制：最多往后推 365 天
                if (current - datetime.now()).days > 365:
                    logger.warning(f"往后推算超过 365 天，停止搜索")
                    return None
            
            return current.strftime("%Y%m%d")
            
        except Exception as e:
            logger.error(f"获取后一个交易日失败：{e}")
            return None
    
    def get_trading_date_range(self, start_date: str, end_date: str) -> List[str]:
        """
        获取日期范围内的所有交易日
        
        :param start_date: 开始日期（YYYYMMDD）
        :param end_date: 结束日期（YYYYMMDD）
        :return: 交易日列表（YYYYMMDD）
        """
        try:
            start = self._parse_date(start_date)
            end = self._parse_date(end_date)
            
            trading_days = []
            current = start
            
            while current <= end:
                if self.is_trading_day(current.strftime("%Y%m%d")):
                    trading_days.append(current.strftime("%Y%m%d"))
                current += timedelta(days=1)
            
            return trading_days
            
        except Exception as e:
            logger.error(f"获取交易日范围失败：{e}")
            return []
    
    def get_last_trading_date_of_month(self, year: int, month: int) -> Optional[str]:
        """
        获取指定年月的最后一个交易日
        
        规则：从自然月最后一天往前推，找到最近一个交易日
        
        :param year: 年份
        :param month: 月份
        :return: 最后一个交易日（YYYYMMDD），找不到则返回 None
        
        示例：
        - get_last_trading_date_of_month(2016, 10) → '20161031'（10月31日是周一，交易日）
        - get_last_trading_date_of_month(2026, 10) → '20261030'（10月31日是周六，往前推）
        """
        try:
            import calendar
            # 获取该月最后一天
            last_day = calendar.monthrange(year, month)[1]
            current = datetime(year, month, last_day)
            
            # 往前遍历，找到第一个交易日
            max_search_days = 10  # 最多往前推10天（应对长假）
            days_searched = 0
            
            while days_searched < max_search_days:
                date_str = current.strftime("%Y%m%d")
                if self.is_trading_day(date_str):
                    return date_str
                current -= timedelta(days=1)
                days_searched += 1
            
            logger.warning(f"未找到 {year}-{month:02d} 的交易日（往前推了{max_search_days}天）")
            return None
            
        except Exception as e:
            logger.error(f"获取 {year}-{month:02d} 月尾日期失败：{e}")
            return None
    
    def get_month_end_dates(
        self, 
        start_date: str, 
        end_date: str
    ) -> List[Tuple[str, str]]:
        """
        获取指定范围内的月度日期对（上月尾, 本月尾）
        
        :param start_date: 开始日期（YYYYMMDD），结果包含该月
        :param end_date: 结束日期（YYYYMMDD），结果包含该月
        :return: [(上月尾, 本月尾), ...] 列表，按时间顺序排列
        
        示例：
        start='20160101', end='20160331'
        → [('20151231', '20160129'), ('20160129', '20160229'), ('20160229', '20160331')]
        
        注意：
        - 第一个元组的"上月尾"可能是 start_date 前一个月的月尾
        - 如果某月找不到交易日，则跳过该月
        """
        try:
            start = self._parse_date(start_date)
            end = self._parse_date(end_date)
            
            # 从 start_date 所在月开始
            current_year = start.year
            current_month = start.month
            
            # 找到 start_date 所在月的月尾
            first_month_end = self.get_last_trading_date_of_month(current_year, current_month)
            if not first_month_end:
                logger.warning(f"未找到 {current_year}-{current_month:02d} 的月尾日期")
                return []
            
            month_ends = [first_month_end]
            
            # 逐月推进，直到超过 end_date
            max_months = 500  # 安全限制，最多500个月
            months_count = 0
            
            while True:
                # 移到下个月
                if current_month == 12:
                    current_year += 1
                    current_month = 1
                else:
                    current_month += 1
                
                month_end = self.get_last_trading_date_of_month(current_year, current_month)
                
                if not month_end:
                    # 该月没有交易日，继续下一个月
                    months_count += 1
                    if months_count > max_months:
                        logger.warning(f"搜索超过 {max_months} 个月，停止")
                        break
                    continue
                
                # 检查是否超过 end_date
                month_end_dt = self._parse_date(month_end)
                if month_end_dt > end:
                    break
                
                month_ends.append(month_end)
                months_count += 1
                
                if months_count > max_months:
                    logger.warning(f"搜索超过 {max_months} 个月，停止")
                    break
            
            # 构建 (上月尾, 本月尾) 对
            date_pairs = []
            for i in range(1, len(month_ends)):
                date_pairs.append((month_ends[i-1], month_ends[i]))
            
            return date_pairs
            
        except Exception as e:
            logger.error(f"获取月度日期对失败：{e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_date(self, date_str: str) -> datetime:
        """
        解析日期字符串为 datetime 对象
        
        支持的格式：
        - YYYYMMDD (如 20260404)
        - YYYY-MM-DD (如 2026-04-04)
        """
        if len(date_str) == 8:
            return datetime.strptime(date_str, "%Y%m%d")
        elif len(date_str) == 10:
            return datetime.strptime(date_str, "%Y-%m-%d")
        else:
            raise ValueError(f"不支持的日期格式：{date_str}")
    
    def reload(self, year: Optional[int] = None):
        """重新加载交易日历（用于测试或手动刷新）"""
        if year:
            self.calendar_year = year
        self._holidays.clear()
        self._load_holidays()
        logger.info("交易日历已重新加载")


# 导出全局单例（默认使用当前年份）
trade_calendar = TradeCalendarService()
