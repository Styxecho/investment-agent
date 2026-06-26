import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
import pandas as pd

print('=== V7 Factor Values Summary ===')
sql = """
SELECT 
    indicator_code,
    COUNT(*) as cnt,
    MIN(publish_date) as start_date,
    MAX(publish_date) as end_date,
    filter_method
FROM macro_factor_value
GROUP BY indicator_code
ORDER BY indicator_code
"""
df = pd.read_sql(sql, engine)
print(df.to_string(index=False))
print()
print(f"Total: {df['cnt'].sum()} records")

print()
print('=== Sample Factor Values (CN_PMI_MFG_M) ===')
sql2 = """
SELECT publish_date, factor_value, raw_value, cycle_value, trend_value
FROM macro_factor_value
WHERE indicator_code = 'CN_PMI_MFG_M'
ORDER BY publish_date DESC
LIMIT 5
"""
df2 = pd.read_sql(sql2, engine)
print(df2.to_string(index=False))

print()
print('=== Sample Factor Values (CN_CCPI_YOY_M) ===')
sql3 = """
SELECT publish_date, factor_value, raw_value, cycle_value, trend_value
FROM macro_factor_value
WHERE indicator_code = 'CN_CCPI_YOY_M'
ORDER BY publish_date DESC
LIMIT 5
"""
df3 = pd.read_sql(sql3, engine)
print(df3.to_string(index=False))
