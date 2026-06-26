# tests/test_trade_calendar.py
"""
交易日历服务测试
"""
import pytest
from datetime import datetime
from utils.trade_calendar import TradeCalendarService


class TestTradeCalendarService:
    """交易日历服务测试类"""
    
    @pytest.fixture
    def calendar_service(self):
        """创建交易日历服务实例"""
        return TradeCalendarService(calendar_year=2026)
    
    def test_is_trading_day_weekday(self, calendar_service):
        """测试普通工作日"""
        # 2026-04-07 是周二，应该是交易日
        assert calendar_service.is_trading_day("20260407") == True
    
    def test_is_trading_day_weekend(self, calendar_service):
        """测试周末"""
        # 2026-04-04 是周六
        assert calendar_service.is_trading_day("20260404") == False
        # 2026-04-05 是周日
        assert calendar_service.is_trading_day("20260405") == False
    
    def test_is_trading_day_holiday(self, calendar_service):
        """测试节假日"""
        # 2026-01-01 是元旦（节假日）
        # 注意：需要确保 trade_calendar.csv 中包含此日期
        result = calendar_service.is_trading_day("20260101")
        # 如果 CSV 中定义了该节假日，应返回 False
        # 如果 CSV 未加载或无此节假日，仅通过周末判断
        assert result == False, "2026-01-01 应该是节假日（非交易日）"
    
    def test_get_previous_trading_day(self, calendar_service):
        """测试获取前一个交易日"""
        # 周一的前一个交易日应该是周五
        # 2026-04-06 是周一（清明节后）
        prev_date = calendar_service.get_previous_trading_date("20260406", days_back=1)
        
        # 应该返回 2026-04-03（周五）
        assert prev_date is not None
        assert prev_date == "20260403"
    
    def test_get_previous_trading_day_after_holiday(self, calendar_service):
        """测试节假日后的第一个交易日"""
        # 2026-01-04 是周日，2026-01-05 是周一（节假日后的第一个交易日）
        # 前一个交易日应该是 2025-12-31 或更早
        prev_date = calendar_service.get_previous_trading_date("20260105", days_back=1)
        
        # 应该返回节假日前的最后一个交易日
        assert prev_date is not None
        assert prev_date < "20260105"
    
    def test_parse_date_yyyymmdd(self, calendar_service):
        """测试日期解析（YYYYMMDD 格式）"""
        date_obj = calendar_service._parse_date("20260404")
        assert date_obj.year == 2026
        assert date_obj.month == 4
        assert date_obj.day == 4
    
    def test_parse_date_yyyy_mm_dd(self, calendar_service):
        """测试日期解析（YYYY-MM-DD 格式）"""
        date_obj = calendar_service._parse_date("2026-04-04")
        assert date_obj.year == 2026
        assert date_obj.month == 4
        assert date_obj.day == 4
    
    def test_get_trading_date_range(self, calendar_service):
        """测试获取交易日范围"""
        # 获取 2026-04-01 到 2026-04-10 的交易日
        trading_days = calendar_service.get_trading_date_range("20260401", "20260410")
        
        assert len(trading_days) > 0
        # 应该不包含周末
        for day in trading_days:
            date_obj = datetime.strptime(day, "%Y%m%d")
            assert date_obj.weekday() < 5  # 不是周六或周日
    
    def test_reload_calendar(self, calendar_service):
        """测试重新加载日历"""
        calendar_service.reload(2026)
        # 应该不抛出异常


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
