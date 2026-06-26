import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
import pandas as pd
import json

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
print('=== Recent Records with Warnings ===')
sql3 = """
SELECT publish_date, growth_state, inflation_state, liquidity_level, macro_regime, warnings
FROM macro_state
WHERE warnings IS NOT NULL
ORDER BY publish_date DESC
LIMIT 10
"""
df3 = pd.read_sql(sql3, engine)
if len(df3) > 0:
    for _, row in df3.iterrows():
        print(f"{row['publish_date']}: {row['growth_state']} | {row['inflation_state']} | {row['liquidity_level']} -> {row['macro_regime']}")
        if row['warnings']:
            try:
                warnings = json.loads(row['warnings'])
                for w in warnings:
                    print(f"  [WARN] {w}")
            except:
                print(f"  [WARN] {row['warnings']}")
else:
    print("No warnings in recent records")

print()
print('=== Data Summary ===')
sql4 = "SELECT COUNT(*) as total FROM macro_state"
df4 = pd.read_sql(sql4, engine)
print(f"Total records: {df4.iloc[0]['total']}")

sql5 = "SELECT MIN(publish_date) as start, MAX(publish_date) as end FROM macro_state"
df5 = pd.read_sql(sql5, engine)
print(f"Date range: {df5.iloc[0]['start']} to {df5.iloc[0]['end']}")
