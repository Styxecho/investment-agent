import pandas as pd
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
from sqlalchemy import text

print('=== Import CN_R007_D from Old CSV ===')
print()

# 1. Clean any existing CN_R007_D data
with engine.connect() as conn:
    result = conn.execute(text("DELETE FROM macro_indicator_value WHERE indicator_code='CN_R007_D'"))
    conn.commit()
    print(f'[OK] Cleaned {result.rowcount} old records')

# 2. Add catalog entry
insert_catalog = """
INSERT OR REPLACE INTO macro_indicator_catalog 
(indicator_code, indicator_name, category, country, frequency, unit, data_source, description, is_active)
VALUES (:code, :name, :category, :country, :frequency, :unit, 'wind', :description, 1)
"""

with engine.connect() as conn:
    conn.execute(text(insert_catalog), {
        'code': 'CN_R007_D',
        'name': '中国-银行间质押式回购加权利率-7天(全市场)',
        'category': 'liquidity',
        'country': 'CN',
        'frequency': 'daily',
        'unit': 'PCT',
        'description': '中国-银行间质押式回购加权利率-7天(全市场R007)',
    })
    conn.commit()
    print('[OK] Updated catalog entry')

# 3. Import data from old CSV
old_csv = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\raw_data\macro_indicators_history_series_daily.csv'
df = pd.read_csv(old_csv, encoding='utf-8-sig', header=None)

# Column 3 is CN_R007_D
data_df = df.iloc[3:].copy()  # Skip first 3 rows
data_df.columns = ['date', 'col_1', 'col_2', 'cn_r007_d', 'col_4', 'col_5']

# Convert date
data_df['date'] = pd.to_datetime(data_df['date'], errors='coerce')
data_df = data_df.dropna(subset=['date'])
data_df['publish_date'] = data_df['date'].dt.strftime('%Y%m%d')

# Build records
records = []
count = 0
for _, row in data_df.iterrows():
    value = row['cn_r007_d']
    if pd.notna(value) and str(value).strip() != '':
        try:
            records.append({
                'indicator_code': 'CN_R007_D',
                'publish_date': row['publish_date'],
                'value': float(value),
                'frequency': 'daily',
                'period_type': 'absolute',
                'data_source': 'wind',
            })
            count += 1
        except (ValueError, TypeError):
            pass

print(f'[INFO] Prepared {count} records')

if records:
    value_df = pd.DataFrame(records)
    value_df.to_sql('macro_indicator_value', engine, if_exists='append', index=False)
    print(f'[OK] Imported {len(records)} records')
else:
    print('[WARN] No records found')

# 4. Verify
print()
print('=== Verification ===')
verify_sql = """
SELECT 
    indicator_code,
    COUNT(*) as cnt,
    MIN(publish_date) as start_date,
    MAX(publish_date) as end_date
FROM macro_indicator_value 
WHERE indicator_code = 'CN_R007_D'
GROUP BY indicator_code
"""
df_verify = pd.read_sql(verify_sql, engine)
print(df_verify.to_string(index=False))

# Check all liquidity daily indicators
print()
print('=== All Daily Liquidity Indicators ===')
all_sql = """
SELECT indicator_code, COUNT(*) as cnt, MIN(publish_date), MAX(publish_date)
FROM macro_indicator_value
WHERE indicator_code IN ('CN_DR007_D', 'CN_OMO_R007_D', 'CN_R007_D')
GROUP BY indicator_code
"""
df_all = pd.read_sql(all_sql, engine)
print(df_all.to_string(index=False))
