import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
import pandas as pd

print('=== V7 Macro State Results ===')
sql = """
SELECT 
    publish_date,
    growth_state,
    inflation_state,
    liquidity_level,
    macro_regime,
    warnings
FROM macro_state
ORDER BY publish_date DESC
LIMIT 12
"""
df = pd.read_sql(sql, engine)
print(df.to_string(index=False))

print()
print('=== Regime Distribution (All Time) ===')
sql2 = """
SELECT macro_regime, COUNT(*) as cnt, 
       MIN(publish_date) as first_seen,
       MAX(publish_date) as last_seen
FROM macro_state
GROUP BY macro_regime
ORDER BY cnt DESC
"""
df2 = pd.read_sql(sql2, engine)
print(df2.to_string(index=False))

print()
print('=== Recent Warning Records ===')
sql3 = """
SELECT publish_date, growth_state, inflation_state, liquidity_level, macro_regime, warnings
FROM macro_state
WHERE warnings IS NOT NULL
ORDER BY publish_date DESC
LIMIT 10
"""
df3 = pd.read_sql(sql3, engine)
if len(df3) > 0:
    print(df3.to_string(index=False))
else:
    print("No warnings in recent records")
