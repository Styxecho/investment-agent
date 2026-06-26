#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重新计算IAV因子并扩展所有因子到20260331
"""

import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from skills.macro_factor.pipeline import MacroFactorPipeline
from data_external.db.engine import engine
import pandas as pd
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pipeline = MacroFactorPipeline()

# 1. Recompute IAV factors
print('=== 重新计算IAV因子 ===')
count = pipeline.run('CN_IAV_YOY_M', '20150101', '20260331')
print(f'IAV: {count} records')

# 2. Extend all other factors to 20260331
print('\n=== 扩展所有因子到20260331 ===')
indicators = pd.read_sql("SELECT indicator_code FROM macro_factor_config WHERE is_active = 1", engine)['indicator_code'].tolist()

total = 0
for code in indicators:
    if code == 'CN_IAV_YOY_M':
        continue
    
    # Check if needs extension
    df = pd.read_sql(text("SELECT MAX(publish_date) as latest FROM macro_factor_value WHERE indicator_code = :code"), 
                     engine, params={"code": code})
    latest = df.iloc[0]['latest']
    
    if latest and str(latest) < '20260331':
        try:
            count = pipeline.run(code, '20150101', '20260331')
            total += count
            print(f'  {code}: +{count} records')
        except Exception as e:
            print(f'  {code}: error - {e}')

print(f'\nTotal extended records: {total}')

# Verify
print('\n=== 验证最新日期 ===')
df = pd.read_sql("""
    SELECT indicator_code, MAX(publish_date) as latest, COUNT(*) as cnt
    FROM macro_factor_value
    GROUP BY indicator_code
    ORDER BY indicator_code
""", engine)
print(df.to_string(index=False))
