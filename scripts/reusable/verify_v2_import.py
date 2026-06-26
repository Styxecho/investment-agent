import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
import pandas as pd

print('=== V2 Macro Data Import Complete ===')
print()

sql = """
SELECT 
    indicator_code,
    COUNT(*) as cnt,
    MIN(publish_date) as start_date,
    MAX(publish_date) as end_date,
    frequency
FROM macro_indicator_value
WHERE indicator_code IN (
    'CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M', 'CN_IAV_YOY_M',
    'CN_CPI_YOY_M', 'CN_CCPI_YOY_M', 'CN_CPI_MOM_M', 'CN_CCPI_MOM_M',
    'CN_CPI_NPF_M', 'CN_PPI_YOY_M', 'CN_PPI_MOM_M', 'CN_PPI_NPF_M',
    'CN_M0_YOY_M', 'CN_M1_YOY_M', 'CN_M2_YOY_M', 'CN_SFS_YOY_M',
    'CN_SFS_FLOW_M', 'CN_IIV_YOY_M', 'CN_DR007_D', 'CN_OMO_R007_D'
)
GROUP BY indicator_code
ORDER BY frequency DESC, indicator_code
"""

df = pd.read_sql(sql, engine)
print(df.to_string(index=False))
print()
print(f"Total: {df['cnt'].sum()} records")
print()

print("=== Preserved Old Indicators ===")
sql2 = """
SELECT indicator_code, COUNT(*) as cnt, frequency 
FROM macro_indicator_value 
WHERE indicator_code NOT IN (
    'CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M', 'CN_IAV_YOY_M',
    'CN_CPI_YOY_M', 'CN_CCPI_YOY_M', 'CN_CPI_MOM_M', 'CN_CCPI_MOM_M',
    'CN_CPI_NPF_M', 'CN_PPI_YOY_M', 'CN_PPI_MOM_M', 'CN_PPI_NPF_M',
    'CN_M0_YOY_M', 'CN_M1_YOY_M', 'CN_M2_YOY_M', 'CN_SFS_YOY_M',
    'CN_SFS_FLOW_M', 'CN_IIV_YOY_M', 'CN_DR007_D', 'CN_OMO_R007_D'
)
GROUP BY indicator_code
"""
df2 = pd.read_sql(sql2, engine)
print(df2.to_string(index=False))
