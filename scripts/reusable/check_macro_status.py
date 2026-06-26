import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
import pandas as pd
from sqlalchemy import text

# Check current catalog
print('=== Catalog ===')
catalog = pd.read_sql('SELECT * FROM macro_indicator_catalog', engine)
print(catalog[['indicator_code', 'indicator_name']].to_string(index=False))

# Check daily data count
print('\n=== Daily Data Count ===')
daily = pd.read_sql("SELECT indicator_code, COUNT(*) as cnt FROM macro_indicator_value WHERE frequency='daily' GROUP BY indicator_code", engine)
print(daily.to_string(index=False) if len(daily) > 0 else 'No daily data')

# Check monthly data count
print('\n=== Monthly Data Count ===')
monthly = pd.read_sql("SELECT indicator_code, COUNT(*) as cnt FROM macro_indicator_value WHERE frequency='monthly' GROUP BY indicator_code", engine)
print(monthly.to_string(index=False))
