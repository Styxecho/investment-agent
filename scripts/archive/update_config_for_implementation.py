#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
from sqlalchemy import text

# 1. Add zscore_baseline column if not exists
try:
    with engine.connect() as conn:
        conn.execute(text('ALTER TABLE macro_factor_config ADD COLUMN zscore_baseline DECIMAL(10,4)'))
        conn.commit()
        print('Added zscore_baseline column')
except Exception as e:
    print(f'Column may already exist: {e}')

# 2. Update PMI configs: zscore_baseline=0
with engine.connect() as conn:
    for code in ['CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M']:
        conn.execute(text("""
            UPDATE macro_factor_config 
            SET zscore_baseline = 0,
                filter_params = '{"lamb": 14400, "subtract_baseline": 50}'
            WHERE indicator_code = :code
        """), {'code': code})
    conn.commit()
    print('Updated PMI configs')

# 3. Set IAV config for Spring Festival exclusion
with engine.connect() as conn:
    conn.execute(text("""
        UPDATE macro_factor_config 
        SET filter_params = '{"lamb": 14400, "exclude_spring_festival": true}'
        WHERE indicator_code = 'CN_IAV_YOY_M'
    """))
    conn.commit()
    print('Updated IAV config')

# Verify
import pandas as pd
df = pd.read_sql('SELECT indicator_code, zscore_baseline, filter_params FROM macro_factor_config', engine)
print('\nUpdated config:')
print(df.to_string(index=False))
