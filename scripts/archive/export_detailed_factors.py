#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导出所有宏观指标的原始值和因子值，用于审核
"""
import pandas as pd
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine

# 1. 读取原始数据
raw_sql = """
SELECT 
    indicator_code,
    publish_date,
    value as raw_value,
    frequency
FROM macro_indicator_value 
WHERE frequency = 'monthly'
ORDER BY indicator_code, publish_date
"""
raw_df = pd.read_sql(raw_sql, engine)
raw_df['publish_date'] = pd.to_datetime(raw_df['publish_date'].astype(str))
print(f"Raw data: {len(raw_df)} rows")

# 2. 读取因子数据
factor_sql = """
SELECT 
    indicator_code,
    publish_date,
    factor_type,
    factor_value,
    cycle_value,
    trend_value
FROM macro_factor_value
ORDER BY indicator_code, publish_date, factor_type
"""
factor_df = pd.read_sql(factor_sql, engine)
factor_df['publish_date'] = pd.to_datetime(factor_df['publish_date'].astype(str))
print(f"Factor data: {len(factor_df)} rows")

# 3. 分离level和change
level_df = factor_df[factor_df['factor_type'] == 'level'][['indicator_code', 'publish_date', 'factor_value', 'cycle_value', 'trend_value']].copy()
level_df.columns = ['indicator_code', 'publish_date', 'level_zscore', 'level_cycle', 'level_trend']

change_df = factor_df[factor_df['factor_type'] == 'change'][['indicator_code', 'publish_date', 'factor_value', 'cycle_value', 'trend_value']].copy()
change_df.columns = ['indicator_code', 'publish_date', 'change_zscore', 'change_cycle', 'change_trend']

# 4. 合并
merged = pd.merge(raw_df, level_df, on=['indicator_code', 'publish_date'], how='left')
merged = pd.merge(merged, change_df, on=['indicator_code', 'publish_date'], how='left')

# 5. 重命名和排序
output = merged[['indicator_code', 'publish_date', 'raw_value', 'level_cycle', 'level_zscore', 'change_zscore']].copy()
output.columns = ['Indicator', 'Date', 'Raw_Value', 'HP_Cycle', 'Level_ZScore', 'Change_ZScore']
output = output.sort_values(['Indicator', 'Date'])

# 6. 保存到CSV
output_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_factors_detailed.csv'
output.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f"\nSaved to: {output_file}")
print(f"Total records: {len(output)}")

# 7. 按指标统计
print("\nRecords per indicator:")
print(output.groupby('Indicator').size().to_string())

# 8. 显示所有指标的关键数据（2016-2017切片）
slice_data = output[(output['Date'] >= '2016-01-01') & (output['Date'] <= '2017-12-31')]

print("\n" + "="*100)
print("PMI Manufacturing (CN_PMI_MFG_M) - 2016-2017")
print("="*100)
pmi = slice_data[slice_data['Indicator'] == 'CN_PMI_MFG_M']
print(pmi.to_string(index=False))

print("\n" + "="*100)
print("PPI YoY (CN_PPI_YOY_M) - 2016-2017")
print("="*100)
ppi = slice_data[slice_data['Indicator'] == 'CN_PPI_YOY_M']
print(ppi.to_string(index=False))

print("\n" + "="*100)
print("CPI YoY (CN_CPI_YOY_M) - 2016-2017")
print("="*100)
cpi = slice_data[slice_data['Indicator'] == 'CN_CPI_YOY_M']
print(cpi.to_string(index=False))

print("\n" + "="*100)
print("M2 YoY (CN_M2_YOY_M) - 2016-2017")
print("="*100)
m2 = slice_data[slice_data['Indicator'] == 'CN_M2_YOY_M']
print(m2.to_string(index=False))

print("\n" + "="*100)
print("M1 YoY (CN_M1_YOY_M) - 2016-2017")
print("="*100)
m1 = slice_data[slice_data['Indicator'] == 'CN_M1_YOY_M']
print(m1.to_string(index=False))

print("\n" + "="*100)
print("IAV YoY (CN_IAV_YOY_M) - 2016-2017")
print("="*100)
iav = slice_data[slice_data['Indicator'] == 'CN_IAV_YOY_M']
print(iav.to_string(index=False))
