import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
from sqlalchemy import text

print('=== Clear Old Factor Values ===')
with engine.connect() as conn:
    result = conn.execute(text('DELETE FROM macro_factor_value'))
    conn.commit()
    print(f'[OK] Cleared {result.rowcount} old factor records')

# Verify
import pandas as pd
df = pd.read_sql('SELECT COUNT(*) as cnt FROM macro_factor_value', engine)
print(f'Current count: {df.iloc[0]["cnt"]}')
