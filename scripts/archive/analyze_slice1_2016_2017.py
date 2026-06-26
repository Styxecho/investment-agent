#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pandas as pd
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine

# Load factor data
df = pd.read_sql('SELECT * FROM macro_factor_value', engine)
df['date'] = pd.to_datetime(df['publish_date'].astype(str))

# Filter 2016-2017 slice
slice_df = df[(df['date'] >= '2016-01-01') & (df['date'] <= '2017-12-31')].copy()

# Get PMI and PPI data
pmi_mfg = slice_df[(slice_df['indicator_code'] == 'CN_PMI_MFG_M') & (slice_df['factor_type'] == 'level')].sort_values('date')
ppi = slice_df[(slice_df['indicator_code'] == 'CN_PPI_YOY_M') & (slice_df['factor_type'] == 'level')].sort_values('date')
cpi = slice_df[(slice_df['indicator_code'] == 'CN_CPI_YOY_M') & (slice_df['factor_type'] == 'level')].sort_values('date')

print('=== Slice 1: 2016-2017 Supply-side Reform ===')
print(f'Period: {slice_df["date"].min().date()} to {slice_df["date"].max().date()}')
print(f'Indicators: {slice_df["indicator_code"].nunique()}')
print()

print('PMI Manufacturing (Z-score with baseline=0):')
print(pmi_mfg[['date', 'factor_value']].to_string(index=False))
print()

print('PPI YoY (Z-score):')
print(ppi[['date', 'factor_value']].to_string(index=False))
print()

print('CPI YoY (Z-score):')
print(cpi[['date', 'factor_value']].to_string(index=False))

# Summary stats
print('\n=== Key Statistics ===')
print(f'PMI Z-score range: {pmi_mfg["factor_value"].min():.2f} to {pmi_mfg["factor_value"].max():.2f}')
print(f'PPI Z-score range: {ppi["factor_value"].min():.2f} to {ppi["factor_value"].max():.2f}')
print(f'CPI Z-score range: {cpi["factor_value"].min():.2f} to {cpi["factor_value"].max():.2f}')

# Check if PPI is high (above 2 sigma)
ppi_high = ppi[ppi['factor_value'] > 2.0]
print(f'\nPPI > +2σ months: {len(ppi_high)}')
if len(ppi_high) > 0:
    print(ppi_high[['date', 'factor_value']].to_string(index=False))

# Check PMI contraction (below 0 since baseline=0)
pmi_contract = pmi_mfg[pmi_mfg['factor_value'] < 0]
print(f'\nPMI contraction months (Z<0): {len(pmi_contract)}')
if len(pmi_contract) > 0:
    print(pmi_contract[['date', 'factor_value']].to_string(index=False))
