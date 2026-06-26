#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导出所有宏观指标的完整数据用于审核
"""
import pandas as pd
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine

# 读取所有数据
raw_sql = """
SELECT indicator_code, publish_date, value as raw_value, frequency
FROM macro_indicator_value 
WHERE frequency = 'monthly'
ORDER BY indicator_code, publish_date
"""
raw_df = pd.read_sql(raw_sql, engine)
raw_df['publish_date'] = pd.to_datetime(raw_df['publish_date'].astype(str))

factor_sql = """
SELECT indicator_code, publish_date, factor_type, factor_value, cycle_value, trend_value
FROM macro_factor_value
ORDER BY indicator_code, publish_date, factor_type
"""
factor_df = pd.read_sql(factor_sql, engine)
factor_df['publish_date'] = pd.to_datetime(factor_df['publish_date'].astype(str))

# 分离level和change
level_df = factor_df[factor_df['factor_type'] == 'level'][['indicator_code', 'publish_date', 'factor_value', 'cycle_value']].copy()
level_df.columns = ['indicator_code', 'publish_date', 'level_zscore', 'level_cycle']

change_df = factor_df[factor_df['factor_type'] == 'change'][['indicator_code', 'publish_date', 'factor_value', 'cycle_value']].copy()
change_df.columns = ['indicator_code', 'publish_date', 'change_zscore', 'change_cycle']

# 合并
merged = pd.merge(raw_df, level_df, on=['indicator_code', 'publish_date'], how='left')
merged = pd.merge(merged, change_df, on=['indicator_code', 'publish_date'], how='left')

output = merged[['indicator_code', 'publish_date', 'raw_value', 'level_cycle', 'level_zscore', 'change_zscore']].copy()
output.columns = ['Indicator', 'Date', 'Raw_Value', 'HP_Cycle', 'Level_ZScore', 'Change_ZScore']
output = output.sort_values(['Indicator', 'Date'])

# 保存完整CSV
output_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_factors_complete.csv'
output.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f"Complete data saved to: {output_file}")
print(f"Total: {len(output)} records, {output['Indicator'].nunique()} indicators\n")

# 按指标打印2016-2017数据
slice_data = output[(output['Date'] >= '2016-01-01') & (output['Date'] <= '2017-12-31')]

indicators = sorted(slice_data['Indicator'].unique())
for ind in indicators:
    data = slice_data[slice_data['Indicator'] == ind]
    print("="*100)
    print(f"{ind} - 2016-2017")
    print("="*100)
    print(data.to_string(index=False))
    print()
