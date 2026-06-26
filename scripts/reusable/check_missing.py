#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
import pandas as pd
from sqlalchemy import text

# Check missing indicators
print('=== Check raw data ===')
missing = ['CN_IAV_YOY_M', 'CN_CPI_YOY_M', 'CN_PPI_YOY_M', 'CN_SFS_YOY_M', 'CN_IIV_YOY_M', 'CN_DXY_D']
for code in missing:
    df = pd.read_sql(text(f"SELECT COUNT(*) as cnt, MIN(publish_date) as start, MAX(publish_date) as end FROM macro_indicator_value WHERE indicator_code = :code"), 
                     engine, params={"code": code})
    row = df.iloc[0]
    print(f'{code}: {row["cnt"]} records, {row["start"]} - {row["end"]}')

print('\n=== All monthly indicators data count ===')
all_codes = pd.read_sql(text("SELECT indicator_code, COUNT(*) as cnt FROM macro_indicator_value WHERE frequency = 'monthly' GROUP BY indicator_code"), engine)
print(all_codes.to_string(index=False))
