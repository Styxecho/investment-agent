#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
import pandas as pd
from data_external.db.engine import engine
from sqlalchemy import text

print('=== Import missing monthly data ===')

monthly_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\marco_indicators_history_series_monthly.csv'
df = pd.read_csv(monthly_file, encoding='gbk')

data_df = df.iloc[5:].copy()
# 转换日期列
date_col = data_df.columns[0]
data_df[date_col] = pd.to_datetime(data_df[date_col], errors='coerce')
data_df = data_df.dropna(subset=[date_col])
data_df['date'] = data_df[date_col].dt.strftime('%Y%m%d')

indicators = ['CN_IAV_YOY_M', 'CN_CPI_YOY_M', 'CN_PPI_YOY_M', 'CN_SFS_YOY_M', 'CN_IIV_YOY_M']
total = 0

for code in indicators:
    if code not in df.columns:
        print(f'  X {code}: not found')
        continue
    
    records = []
    for _, row in data_df.iterrows():
        val = row[code]
        if pd.notna(val) and str(val).strip() != '':
            try:
                records.append({
                    'indicator_code': code,
                    'publish_date': row['date'],
                    'value': float(val),
                    'frequency': 'monthly',
                    'period_type': 'yoy',
                    'data_source': 'wind'
                })
            except:
                pass
    
    if records:
        with engine.connect() as conn:
            conn.execute(text('DELETE FROM macro_indicator_value WHERE indicator_code = :code'), {'code': code})
            conn.commit()
        pd.DataFrame(records).to_sql('macro_indicator_value', engine, if_exists='append', index=False)
        print(f'  OK {code}: {len(records)}')
        total += len(records)

print(f'\nTotal monthly: {total}')

print('\n=== Import DXY daily ===')
daily_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_indicators_history_series_daily.csv'
df2 = pd.read_csv(daily_file, encoding='utf-8-sig', header=None)

data_df2 = df2.iloc[5:, [0, 5]].copy()
data_df2.columns = ['date', 'dxy']
data_df2['date'] = pd.to_datetime(data_df2['date'], errors='coerce')
data_df2 = data_df2.dropna(subset=['date'])
data_df2['date'] = data_df2['date'].dt.strftime('%Y%m%d')

records = []
for _, row in data_df2.iterrows():
    val = row['dxy']
    if pd.notna(val) and str(val).strip() != '':
        try:
            records.append({
                'indicator_code': 'CN_DXY_D',
                'publish_date': row['date'],
                'value': float(val),
                'frequency': 'daily',
                'period_type': 'absolute',
                'data_source': 'wind'
            })
        except:
            pass

if records:
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM macro_indicator_value WHERE indicator_code = 'CN_DXY_D'"))
        conn.commit()
    pd.DataFrame(records).to_sql('macro_indicator_value', engine, if_exists='append', index=False)
    print(f'  OK CN_DXY_D: {len(records)}')

print('\n=== Verify ===')
df_check = pd.read_sql('SELECT indicator_code, frequency, COUNT(*) as cnt FROM macro_indicator_value GROUP BY indicator_code, frequency ORDER BY indicator_code', engine)
print(df_check.to_string(index=False))

catalog = pd.read_sql('SELECT indicator_code FROM macro_indicator_catalog', engine)
has_data = set(df_check['indicator_code'])
missing = set(catalog['indicator_code']) - has_data
if missing:
    print(f'\nMissing: {missing}')
else:
    print('\nAll indicators have data!')
