import pandas as pd
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
from sqlalchemy import text

# 1. Check if CN_R007_D exists in catalog and value table
print('=== Current CN_R007_D Status ===')
df = pd.read_sql("SELECT COUNT(*) as cnt FROM macro_indicator_value WHERE indicator_code='CN_R007_D'", engine)
print(f'Value records: {df.iloc[0]["cnt"]}')

df2 = pd.read_sql("SELECT * FROM macro_indicator_catalog WHERE indicator_code='CN_R007_D'", engine)
print(f'Catalog entry: {len(df2)} rows')
if len(df2) > 0:
    print(df2.to_string(index=False))

# 2. Check old CSV
old_csv = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\raw_data\macro_indicators_history_series_daily.csv'
df_old = pd.read_csv(old_csv, encoding='utf-8-sig', header=None)
print(f'\n=== Old CSV Structure ===')
print(f'Shape: {df_old.shape}')
print(f'Row 0 (indicator_code): {df_old.iloc[0].tolist()}')
print(f'Row 1 (Chinese names): {df_old.iloc[1].tolist()}')
print(f'Row 2 (codes): {df_old.iloc[2].tolist()}')
print(f'\nFirst data row:')
print(df_old.iloc[3].tolist())
print(f'\nLast data row:')
print(df_old.iloc[-1].tolist())
