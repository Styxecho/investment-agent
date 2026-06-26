#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证月度收益率计算
选取沪深300指数(000300.SH)进行计算并输出结果
"""
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')

import pandas as pd
from sqlalchemy import create_engine
from utils.trade_calendar import TradeCalendarService
from utils.returns_calculator import calculate_period_return

# 数据库连接
engine = create_engine('sqlite:///D:/Study/Project/investment-agent/data_external/db/external_data.db')

print("="*80)
print("沪深300(000300.SH) 月度收益率计算验证")
print("="*80)

# 1. 读取数据
sql = """
SELECT trade_date, close_price
FROM index_daily
WHERE index_code = '000300.SH'
ORDER BY trade_date
"""
df = pd.read_sql(sql, engine)
df['trade_date'] = df['trade_date'].astype(str).str.replace('-', '')
print(f"\n原始数据：{len(df)} 条")
print(f"日期范围：{df['trade_date'].min()} 至 {df['trade_date'].max()}")

# 2. 获取月度日期对（2016年1月至2017年12月）
calendar = TradeCalendarService()
date_pairs = calendar.get_month_end_dates('20160101', '20171231')
print(f"\n月度区间数量：{len(date_pairs)} 个")
print(f"首个区间：{date_pairs[0]}")
print(f"末个区间：{date_pairs[-1]}")

# 3. 构建价格序列
price_series = df.set_index('trade_date')['close_price']

# 4. 逐月计算
results = []
for prev_end, curr_end in date_pairs:
    # 提取子序列
    mask = (price_series.index >= prev_end) & (price_series.index <= curr_end)
    subset = price_series[mask]
    
    if len(subset) < 2:
        continue
    
    start_price = subset.iloc[0]
    end_price = subset.iloc[-1]
    
    # 计算收益率
    monthly_return = calculate_period_return(
        price_series,
        start_date=prev_end,
        end_date=curr_end,
        method='compound'
    )
    
    if monthly_return is None:
        continue
    
    trade_month = curr_end[:6]
    
    results.append({
        'trade_month': trade_month,
        'period_start': prev_end,
        'period_end': curr_end,
        'start_price': round(start_price, 2),
        'end_price': round(end_price, 2),
        'monthly_return_pct': round(monthly_return * 100, 2)
    })

results_df = pd.DataFrame(results)

# 5. 输出结果
print("\n" + "="*80)
print("月度收益率明细（2016-2017）")
print("="*80)
print(results_df.to_string(index=False))

# 6. 统计摘要
print("\n" + "="*80)
print("统计摘要")
print("="*80)
print(f"计算月份数：{len(results_df)}")
print(f"月度收益率均值：{results_df['monthly_return_pct'].mean():.2f}%")
print(f"月度收益率中位数：{results_df['monthly_return_pct'].median():.2f}%")
print(f"月度收益率标准差：{results_df['monthly_return_pct'].std():.2f}%")
print(f"最大月度收益：{results_df['monthly_return_pct'].max():.2f}%")
print(f"最小月度收益：{results_df['monthly_return_pct'].min():.2f}%")
print(f"正收益月份数：{(results_df['monthly_return_pct'] > 0).sum()}")
print(f"负收益月份数：{(results_df['monthly_return_pct'] < 0).sum()}")

# 7. 累计收益率
initial_price = results_df.iloc[0]['start_price']
final_price = results_df.iloc[-1]['end_price']
total_return = (final_price / initial_price - 1) * 100
print(f"\n累计收益率（2016-01至2017-12）：{total_return:.2f}%")
print(f"期初价格：{initial_price}")
print(f"期末价格：{final_price}")

# 8. 保存到CSV
output_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\csi300_monthly_returns_2016_2017.csv'
results_df.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"\n结果已保存到：{output_path}")
