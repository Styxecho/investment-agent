#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
import pandas as pd
from data_external.db.engine import engine

print('=== PMI因子验证（减50处理）===')

# 检查2016年2月（PMI低于50）
df = pd.read_sql("""
    SELECT indicator_code, publish_date, factor_type, factor_value, cycle_value
    FROM macro_factor_value
    WHERE indicator_code IN ('CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M')
      AND publish_date = '20160229'
    ORDER BY indicator_code, factor_type
""", engine)
print("\n2016年2月（PMI低于50，应显示收缩）:")
print(df.to_string(index=False))

# 检查2017年12月（PMI高于50）
df2 = pd.read_sql("""
    SELECT indicator_code, publish_date, factor_type, factor_value, cycle_value
    FROM macro_factor_value
    WHERE indicator_code IN ('CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M')
      AND publish_date = '20171231'
    ORDER BY indicator_code, factor_type
""", engine)
print("\n2017年12月（PMI高于50，应显示扩张）:")
print(df2.to_string(index=False))

# 检查原始PMI值
print("\n=== 原始PMI值对比 ===")
df3 = pd.read_sql("""
    SELECT indicator_code, publish_date, value
    FROM macro_indicator_value
    WHERE indicator_code IN ('CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M')
      AND publish_date IN ('20160229', '20171231')
    ORDER BY indicator_code, publish_date
""", engine)
print(df3.to_string(index=False))

print("\n=== 总因子数量统计 ===")
df4 = pd.read_sql("""
    SELECT indicator_code, COUNT(*) as cnt
    FROM macro_factor_value
    GROUP BY indicator_code
    ORDER BY indicator_code
""", engine)
print(df4.to_string(index=False))
