#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
import pandas as pd
from data_external.db.engine import engine

print('=== 2020年3月关键因子（疫情爆发）===')
df = pd.read_sql("""
SELECT indicator_code, factor_type, factor_value, cycle_value
FROM macro_factor_value
WHERE publish_date = '20200331'
ORDER BY indicator_code, factor_type
""", engine)
print(df.to_string(index=False))

print('\n=== 2021年10月关键因子（通胀高点）===')
df2 = pd.read_sql("""
SELECT indicator_code, factor_type, factor_value
FROM macro_factor_value
WHERE publish_date = '20211031'
  AND indicator_code IN ('CN_CPI_YOY_M', 'CN_PPI_YOY_M', 'CN_M2_YOY_M', 'CN_DR007_D')
ORDER BY indicator_code, factor_type
""", engine)
print(df2.to_string(index=False))

print('\n=== 因子数据统计 ===')
df3 = pd.read_sql("""
SELECT 
    indicator_code,
    COUNT(*) as total,
    SUM(CASE WHEN factor_type = 'level' THEN 1 ELSE 0 END) as level_cnt,
    SUM(CASE WHEN factor_type = 'change' THEN 1 ELSE 0 END) as change_cnt,
    MIN(publish_date) as start,
    MAX(publish_date) as end
FROM macro_factor_value
GROUP BY indicator_code
ORDER BY indicator_code
""", engine)
print(df3.to_string(index=False))
