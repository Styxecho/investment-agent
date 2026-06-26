#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
from sqlalchemy import text
import pandas as pd

# 1. 添加M1M2剪刀差到catalog
with engine.connect() as conn:
    conn.execute(text("""
        INSERT OR REPLACE INTO macro_indicator_catalog 
        (indicator_code, indicator_name, category, country, frequency, unit, description, data_source)
        VALUES ('CN_M1M2_DIFF_M', 'M1-M2剪刀差', 'liquidity', 'CN', 'monthly', 'PCT', 'M1同比减M2同比，反映资金活化程度', 'computed')
    """))
    conn.commit()
    print('Added CN_M1M2_DIFF_M to catalog')

# 2. 添加M1M2剪刀差到factor_config
with engine.connect() as conn:
    conn.execute(text("""
        INSERT OR REPLACE INTO macro_factor_config 
        (indicator_code, filter_type, filter_params, level_window, change_window, winsorize_threshold, min_periods_for_zscore, hp_warmup_months, is_active)
        VALUES ('CN_M1M2_DIFF_M', 'one_sided_hp', '{\"lamb\": 14400}', 36, 48, 3.0, 12, 18, 1)
    """))
    conn.commit()
    print('Added CN_M1M2_DIFF_M to factor_config')

# 3. 更新PMI配置
with engine.connect() as conn:
    for code in ['CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M']:
        conn.execute(text("""
            UPDATE macro_factor_config 
            SET filter_params = '{\"lamb\": 14400, \"subtract_baseline\": 50}'
            WHERE indicator_code = :code
        """), {'code': code})
    conn.commit()
    print('Updated PMI config')

# 验证
df = pd.read_sql("SELECT indicator_code, filter_params FROM macro_factor_config WHERE indicator_code IN ('CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M', 'CN_M1M2_DIFF_M')", engine)
print('\nUpdated config:')
print(df.to_string(index=False))
