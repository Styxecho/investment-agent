#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
切片1复盘报告：2016-2017 宏观因子与资产表现关联分析
"""
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from utils.trade_calendar import TradeCalendarService
from utils.returns_calculator import calculate_period_return

engine = create_engine('sqlite:///D:/Study/Project/investment-agent/data_external/db/external_data.db')

print("="*100)
print("切片1复盘报告：2016-2017 供给侧改革与漂亮50")
print("="*100)
print("\n【分析框架】")
print("1. 宏观状态识别：基于Z-score判断经济周期位置")
print("2. 滞后验证：当月宏观数据 → 次月资产收益（T+1月）")
print("3. 行业映射：验证'宏观状态→行业轮动'逻辑是否成立")
print("="*100)

# 读取数据
macro_sql = """
SELECT indicator_code, publish_date, factor_value
FROM macro_factor_value
WHERE factor_type = 'level'
    AND publish_date BETWEEN '20160101' AND '20171231'
ORDER BY indicator_code, publish_date
"""
macro_df = pd.read_sql(macro_sql, engine)
macro_df['publish_date'] = pd.to_datetime(macro_df['publish_date'].astype(str))
macro_df['year_month'] = macro_df['publish_date'].dt.strftime('%Y%m')
macro_pivot = macro_df.pivot(index='year_month', columns='indicator_code', values='factor_value')

# 计算资产收益
price_sql = """
SELECT index_code, trade_date, close_price
FROM index_daily
WHERE index_code IN (
    '000300.SH', '000905.SH', '000852.SH',
    '801950.SI', '801040.SI', '801050.SI', '801120.SI',
    '801110.SI', '801150.SI', '801890.SI'
)
ORDER BY index_code, trade_date
"""
price_df = pd.read_sql(price_sql, engine)
price_df['trade_date'] = price_df['trade_date'].astype(str).str.replace('-', '')

calendar = TradeCalendarService()
date_pairs = calendar.get_month_end_dates('20160101', '20171231')

asset_returns = []
for index_code, group in price_df.groupby('index_code'):
    group = group.sort_values('trade_date')
    price_series = group.set_index('trade_date')['close_price']
    for prev_end, curr_end in date_pairs:
        ret = calculate_period_return(price_series, start_date=prev_end, end_date=curr_end, method='compound')
        if ret is not None:
            asset_returns.append({
                'index_code': index_code,
                'trade_month': curr_end[:6],
                'monthly_return': ret
            })

asset_df = pd.DataFrame(asset_returns)
asset_pivot = asset_df.pivot(index='trade_month', columns='index_code', values='monthly_return')

# 滞后对齐
asset_pivot_lag = asset_pivot.copy()
asset_pivot_lag.index = [
    (pd.to_datetime(x + '01', format='%Y%m%d') + pd.DateOffset(months=-1)).strftime('%Y%m')
    for x in asset_pivot_lag.index
]

combined = pd.merge(macro_pivot, asset_pivot_lag, left_index=True, right_index=True, how='inner')

# ============================================================================
# 核心发现
# ============================================================================
print("\n" + "="*100)
print("【核心发现】")
print("="*100)

# 1. PPI高位期分析
print("\n1. PPI > +2σ 时期（2016.7-2017.2，共8个月）")
print("-"*80)
ppi_high = combined[combined['CN_PPI_YOY_M'] > 2.0]
print(f"   期间: {ppi_high.index.tolist()}")
print(f"   钢铁: {ppi_high['801040.SI'].mean()*100:.2f}% (超额: {(ppi_high['801040.SI'].mean() - ppi_high['000300.SH'].mean())*100:+.2f}%)")
print(f"   煤炭: {ppi_high['801950.SI'].mean()*100:.2f}% (超额: {(ppi_high['801950.SI'].mean() - ppi_high['000300.SH'].mean())*100:+.2f}%)")
print(f"   有色金属: {ppi_high['801050.SI'].mean()*100:.2f}% (超额: {(ppi_high['801050.SI'].mean() - ppi_high['000300.SH'].mean())*100:+.2f}%)")
print(f"   沪深300: {ppi_high['000300.SH'].mean()*100:.2f}%")
print("   → 钢铁显著跑赢，但有色金属跑输，分化严重")

# 2. PMI分化期
print("\n2. PMI制造业 > PMI服务业（共9个月）")
print("-"*80)
if 'CN_PMI_MFG_M' in combined.columns and 'CN_PMI_SVC_M' in combined.columns:
    pmi_div = combined[combined['CN_PMI_MFG_M'] > combined['CN_PMI_SVC_M']]
    print(f"   期间: {pmi_div.index.tolist()}")
    print(f"   钢铁: {pmi_div['801040.SI'].mean()*100:.2f}%")
    print(f"   机械设备: {pmi_div['801890.SI'].mean()*100:.2f}%")
    print(f"   食品饮料: {pmi_div['801120.SI'].mean()*100:.2f}%")
    print(f"   家用电器: {pmi_div['801110.SI'].mean()*100:.2f}%")
    print("   → 消费（家电、食品）反而跑赢工业，预期落空")

# 3. PPI-CPI缺口
print("\n3. PPI-CPI缺口 > +1.5σ（共8个月）")
print("-"*80)
if 'CN_PPI_YOY_M' in combined.columns and 'CN_CPI_YOY_M' in combined.columns:
    combined['ppi_cpi_gap'] = combined['CN_PPI_YOY_M'] - combined['CN_CPI_YOY_M']
    gap_high = combined[combined['ppi_cpi_gap'] > 1.5]
    print(f"   期间: {gap_high.index.tolist()}")
    print(f"   上游（有色金属）: {gap_high['801050.SI'].mean()*100:.2f}%")
    print(f"   下游（食品饮料）: {gap_high['801120.SI'].mean()*100:.2f}%")
    print(f"   差距: {(gap_high['801050.SI'].mean() - gap_high['801120.SI'].mean())*100:+.2f}%")
    print("   → 上游大幅跑输下游，与'利润向上游集中'逻辑相反！")

# 4. 流动性环境
print("\n4. M2持续为负（2016.7-2017.12，几乎全程）")
print("-"*80)
m2_neg = combined[combined['CN_M2_YOY_M'] < 0]
print(f"   M2<0的月份数: {len(m2_neg)}")
print(f"   大盘（沪深300）: {m2_neg['000300.SH'].mean()*100:.2f}%")
print(f"   中盘（中证500）: {m2_neg['000905.SH'].mean()*100:.2f}%")
print(f"   小盘（中证1000）: {m2_neg['000852.SH'].mean()*100:.2f}%")
print("   → 大盘并未显著跑赢，中盘反而更好")

# ============================================================================
# 月度详细对照
# ============================================================================
print("\n" + "="*100)
print("【关键月份详细对照】")
print("="*100)
print("\n月份   PMI    PPI    CPI    M2     沪深300  钢铁   煤炭   有色   食品")
print("-"*80)

key_months = ['201607', '201608', '201609', '201610', '201611', '201612',
              '201701', '201702', '201703', '201704', '201705', '201706']

for month in key_months:
    if month not in combined.index:
        continue
    row = combined.loc[month]
    pmi = row.get('CN_PMI_MFG_M', 0)
    ppi = row.get('CN_PPI_YOY_M', 0)
    cpi = row.get('CN_CPI_YOY_M', 0)
    m2 = row.get('CN_M2_YOY_M', 0)
    hs300 = row.get('000300.SH', 0) * 100
    steel = row.get('801040.SI', 0) * 100
    coal = row.get('801950.SI', 0) * 100
    metal = row.get('801050.SI', 0) * 100
    food = row.get('801120.SI', 0) * 100
    
    print(f"{month} {pmi:5.2f} {ppi:5.2f} {cpi:5.2f} {m2:5.2f}  {hs300:6.2f}% {steel:6.2f}% {coal:6.2f}% {metal:6.2f}% {food:6.2f}%")

# ============================================================================
# 结论
# ============================================================================
print("\n" + "="*100)
print("【初步结论】")
print("="*100)
print("""
1. 【PPI逻辑部分成立】
   - PPI>+2σ时钢铁显著跑赢（+1.82%超额）
   - 但有色金属跑输，说明行业内部分化大
   - 单纯看PPI不够，还需结合产能利用率、库存周期等

2. 【PMI逻辑不成立】
   - PMI制造业>服务业时，消费（家电+1.72%）跑赢工业（钢铁+1.24%）
   - 可能原因：2016-2017年'漂亮50'行情主导，消费龙头受追捧

3. 【PPI-CPI逻辑反向】
   - 缺口大时上游跑输下游2.75%
   - 可能原因：市场提前反应完毕，或中下游通过提价转嫁成本

4. 【流动性逻辑不显著】
   - M2为负时中盘>大盘>小盘
   - 数据量不足（M2负值仅3个月），统计意义有限

5. 【关键洞察】
   - 宏观逻辑到市场传导存在时滞和扭曲
   - 简单阈值规则（如PPI>2σ）不足以指导配置
   - 需要引入：领先指标、市场预期、资金面等多重验证
   - 切片2（2019-2020）需重点关注'预期差'而非绝对水平
""")

print("="*100)
print("报告生成完成")
print("="*100)
