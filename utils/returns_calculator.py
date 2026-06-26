# utils/returns_calculator.py
"""
通用收益率计算模块

设计原则：
1. 与数据源解耦：输入任意价格/净值序列即可计算
2. 与时间周期解耦：不感知"月/季/年"概念，仅计算给定区间的收益率
3. 提供多种计算方式：复权累乘、简单除法、对数收益率

使用示例：
    # 1. 获取月度日期对
    from utils.trade_calendar import trade_calendar
    date_pairs = trade_calendar.get_month_end_dates('20160101', '20161231')
    
    # 2. 计算月度收益率
    from utils.returns_calculator import calculate_period_return
    for prev_end, curr_end in date_pairs:
        monthly_return = calculate_period_return(
            price_series, 
            start_date=prev_end, 
            end_date=curr_end,
            method='compound'
        )
"""
import pandas as pd
import numpy as np
from typing import Optional, List, Tuple


def calculate_period_return(
    price_series: pd.Series,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    method: str = 'compound'
) -> Optional[float]:
    """
    计算给定价格序列在指定区间内的收益率
    
    :param price_series: pd.Series, index为日期(YYYYMMDD), values为价格/净值
    :param start_date: 开始日期(包含, YYYYMMDD), None则取序列第一个值
    :param end_date: 结束日期(包含, YYYYMMDD), None则取序列最后一个值
    :param method: 计算方法
        - 'compound': 单日收益率累乘 (1+r1)*(1+r2)*...-1, 适用于价格序列
        - 'simple': 首尾价格相除 end/start - 1, 快速计算
        - 'log': 对数收益率 ln(end/start), 用于统计建模
    :return: 收益率(float), 如果找不到数据则返回 None
    
    示例:
        >>> s = pd.Series([100, 102, 101, 105], index=['20260101', '20260102', '20260103', '20260106'])
        >>> calculate_period_return(s, '20260101', '20260106')
        0.05  # 5%
    """
    if price_series.empty:
        return None
    
    # 确定起始和结束值
    if start_date is not None and end_date is not None:
        # 筛选区间内的数据
        mask = (price_series.index >= start_date) & (price_series.index <= end_date)
        subset = price_series[mask]
        
        if subset.empty:
            return None
        
        # 找到区间内第一个和最后一个值
        start_price = subset.iloc[0]
        end_price = subset.iloc[-1]
    elif start_date is not None:
        # 只有开始日期
        mask = price_series.index >= start_date
        subset = price_series[mask]
        if subset.empty:
            return None
        start_price = subset.iloc[0]
        end_price = price_series.iloc[-1]
    elif end_date is not None:
        # 只有结束日期
        mask = price_series.index <= end_date
        subset = price_series[mask]
        if subset.empty:
            return None
        start_price = price_series.iloc[0]
        end_price = subset.iloc[-1]
    else:
        # 无日期限制，使用全部数据
        start_price = price_series.iloc[0]
        end_price = price_series.iloc[-1]
    
    # 检查有效性
    if pd.isna(start_price) or pd.isna(end_price) or start_price == 0:
        return None
    
    # 计算收益率
    if method == 'simple':
        return end_price / start_price - 1.0
    
    elif method == 'log':
        return np.log(end_price / start_price)
    
    elif method == 'compound':
        # 单日收益率累乘
        # 如果只有首尾两个点，等价于 simple
        if len(subset) <= 2:
            return end_price / start_price - 1.0
        
        # 计算每日收益率并累乘
        daily_returns = subset.pct_change().dropna()
        if daily_returns.empty:
            return 0.0
        
        cumulative = (1 + daily_returns).prod() - 1.0
        return cumulative
    
    else:
        raise ValueError(f"不支持的计算方法：{method}，请使用 'compound'|'simple'|'log'")


def calculate_monthly_returns(
    price_df: pd.DataFrame,
    date_col: str = 'trade_date',
    price_col: str = 'close_price',
    group_col: str = 'index_code',
    start_date: str = '20150101',
    end_date: str = '20261231',
    calendar_service = None
) -> pd.DataFrame:
    """
    批量计算多指数的月度收益率
    
    :param price_df: 价格数据DataFrame，必须包含 date_col, price_col, group_col 列
    :param date_col: 日期列名
    :param price_col: 价格列名
    :param group_col: 分组列名（如指数代码）
    :param start_date: 计算起始日期（YYYYMMDD）
    :param end_date: 计算结束日期（YYYYMMDD）
    :param calendar_service: 交易日历服务实例，None则自动创建
    :return: DataFrame，包含以下列：
        - index_code: 指数代码
        - trade_month: 交易月份（YYYYMM）
        - period_start_date: 上月尾日期
        - period_end_date: 本月尾日期
        - start_price: 上月尾收盘价
        - end_price: 本月尾收盘价
        - monthly_return: 月度收益率
        - cumulative_return: 累计收益率（从该指数第一个有效月起）
    """
    from utils.trade_calendar import TradeCalendarService
    
    if calendar_service is None:
        calendar_service = TradeCalendarService()
    
    # 获取月度日期对
    date_pairs = calendar_service.get_month_end_dates(start_date, end_date)
    if not date_pairs:
        return pd.DataFrame()
    
    # 确保日期列格式正确
    price_df = price_df.copy()
    price_df[date_col] = price_df[date_col].astype(str).str.replace('-', '')
    
    # 按指数分组计算
    results = []
    
    for index_code, group in price_df.groupby(group_col):
        # 构建价格序列（日期→价格）
        group = group.sort_values(date_col)
        price_series = group.set_index(date_col)[price_col]
        
        # 计算每个月的收益率
        cumulative = 1.0
        first_valid = False
        
        for prev_end, curr_end in date_pairs:
            # 提取子序列
            mask = (price_series.index >= prev_end) & (price_series.index <= curr_end)
            subset = price_series[mask]
            
            if len(subset) < 2:
                # 区间内数据不足，跳过
                continue
            
            # 获取首尾价格
            start_price = subset.iloc[0]
            end_price = subset.iloc[-1]
            
            # 计算收益率（使用 compound 方法）
            monthly_return = calculate_period_return(
                price_series, 
                start_date=prev_end, 
                end_date=curr_end,
                method='compound'
            )
            
            if monthly_return is None:
                continue
            
            # 累计收益率
            if not first_valid:
                cumulative = 1.0 + monthly_return
                first_valid = True
            else:
                cumulative = cumulative * (1.0 + monthly_return)
            
            # 提取交易月份（从本月尾日期）
            trade_month = curr_end[:6]
            
            results.append({
                'index_code': index_code,
                'trade_month': trade_month,
                'period_start_date': prev_end,
                'period_end_date': curr_end,
                'start_price': round(start_price, 4),
                'end_price': round(end_price, 4),
                'monthly_return': round(monthly_return, 6),
                'cumulative_return': round(cumulative - 1.0, 6)
            })
    
    return pd.DataFrame(results)


def calculate_rolling_return(
    price_series: pd.Series,
    window: int = 20,
    method: str = 'compound'
) -> pd.Series:
    """
    计算滚动窗口收益率
    
    :param price_series: 价格序列
    :param window: 窗口大小（交易日数）
    :param method: 计算方法
    :return: 滚动收益率序列
    
    示例：
        计算20日滚动收益率
        >>> rolling_ret = calculate_rolling_return(price_series, window=20)
    """
    if method == 'simple':
        return price_series / price_series.shift(window) - 1.0
    elif method == 'log':
        return np.log(price_series / price_series.shift(window))
    elif method == 'compound':
        # 使用每日收益率累乘
        daily_returns = price_series.pct_change()
        return (1 + daily_returns).rolling(window=window).apply(lambda x: x.prod() - 1.0, raw=True)
    else:
        raise ValueError(f"不支持的计算方法：{method}")


if __name__ == '__main__':
    # 简单测试
    print("收益率计算模块测试")
    
    # 测试数据
    test_series = pd.Series(
        [100, 102, 101, 105, 103, 108],
        index=['20260101', '20260102', '20260103', '20260106', '20260107', '20260108']
    )
    
    # 测试 simple 方法
    ret_simple = calculate_period_return(test_series, '20260101', '20260108', method='simple')
    print(f"Simple 收益率: {ret_simple:.4f} (预期: 0.0800)")
    
    # 测试 compound 方法
    ret_compound = calculate_period_return(test_series, '20260101', '20260108', method='compound')
    print(f"Compound 收益率: {ret_compound:.4f} (预期: ~0.0800)")
    
    # 测试 log 方法
    ret_log = calculate_period_return(test_series, '20260101', '20260108', method='log')
    print(f"Log 收益率: {ret_log:.4f} (预期: ~0.0770)")
    
    print("测试完成！")
