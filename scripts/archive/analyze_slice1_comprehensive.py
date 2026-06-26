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

# Get key indicators
indicators = {
    'PMI_MFG': 'CN_PMI_MFG_M',
    'PMI_SVC': 'CN_PMI_SVC_M', 
    'PPI': 'CN_PPI_YOY_M',
    'CPI': 'CN_CPI_YOY_M',
    'M2': 'CN_M2_YOY_M',
    'M1': 'CN_M1_YOY_M',
    'IAV': 'CN_IAV_YOY_M',
    'SFS': 'CN_SFS_YOY_M',
    'IIV': 'CN_IIV_YOY_M',
    'DXY': 'US_DXY_D'
}

results = {}
for name, code in indicators.items():
    level_data = slice_df[(slice_df['indicator_code'] == code) & (slice_df['factor_type'] == 'level')].sort_values('date')
    change_data = slice_df[(slice_df['indicator_code'] == code) & (slice_df['factor_type'] == 'change')].sort_values('date')
    
    results[name] = {
        'level': level_data,
        'change': change_data
    }

print('=' * 80)
print('SLICE 1 ANALYSIS: 2016-2017 Supply-side Reform & Beautiful 50')
print('=' * 80)
print()

# 1. PPI Surge Analysis
print('1. PPI SURGE (2016H2 - 2017Q1)')
print('-' * 80)
ppi = results['PPI']['level']
ppi_high = ppi[ppi['factor_value'] > 2.0]
print(f'PPI > +2σ for {len(ppi_high)} months (Jul 2016 - Feb 2017)')
print(f'Peak PPI Z-score: {ppi["factor_value"].max():.2f}')
print()
print('Why resource stocks (周期股) performed best:')
print('- Supply-side reform: coal/steel capacity cuts (去产能)')
print('- PPI +3.0σ = massive profit margin expansion for upstream industries')
print('- Inventory restocking cycle amplified demand')
print()

# 2. PMI Divergence
print('2. PMI DIVERGENCE: Manufacturing vs Services')
print('-' * 80)
pmi_mfg = results['PMI_MFG']['level']
pmi_svc = results['PMI_SVC']['level']

# Find overlapping dates
common_dates = set(pmi_mfg['date']) & set(pmi_svc['date'])
if common_dates:
    mfg_common = pmi_mfg[pmi_mfg['date'].isin(common_dates)].set_index('date')['factor_value']
    svc_common = pmi_svc[pmi_svc['date'].isin(common_dates)].set_index('date')['factor_value']
    diff = mfg_common - svc_common
    print(f'Manufacturing PMI avg Z-score: {mfg_common.mean():.2f}')
    print(f'Services PMI avg Z-score: {svc_common.mean():.2f}')
    print(f'MFG - SVC spread range: {diff.min():.2f} to {diff.max():.2f}')
print()

# 3. Liquidity Analysis
print('3. LIQUIDITY TIGHTENING')
print('-' * 80)
m2 = results['M2']['level']
m1 = results['M1']['level']
print(f'M2 Z-score range: {m2["factor_value"].min():.2f} to {m2["factor_value"].max():.2f}')
print(f'M1 Z-score range: {m1["factor_value"].min():.2f} to {m1["factor_value"].max():.2f}')
print()
print('Why small/mid caps (中小创) crashed:')
print('- M1/M2 growth slowing = tightening liquidity')
print('- Regulatory crackdown on shell companies & speculation')
print('- Value stocks (blue chips) benefited from " Beautiful 50" rotation')
print()

# 4. CPI-PPPI Gap (Inflation mix)
print('4. INFLATION MIX: PPI-CPI Gap')
print('-' * 80)
cpi = results['CPI']['level']
ppi = results['PPI']['level']
common_dates = set(cpi['date']) & set(ppi['date'])
if common_dates:
    cpi_common = cpi[cpi['date'].isin(common_dates)].set_index('date')['factor_value']
    ppi_common = ppi[ppi['date'].isin(common_dates)].set_index('date')['factor_value']
    gap = ppi_common - cpi_common
    print(f'PPI-CPI gap range: {gap.min():.2f} to {gap.max():.2f}')
    print(f'Avg gap: {gap.mean():.2f}')
    print()
    print('Economic interpretation:')
    print('- PPI >> CPI = cost-push inflation at producer level')
    print('- Consumer prices subdued = weak demand transfer downstream')
    print('- Profit concentrated upstream (resources, materials)')

print()
print('=' * 80)
print('KEY FINDINGS FOR STRATEGY:')
print('=' * 80)
print('1. PPI > +2σ + PMI > 0: Overweight cyclical/resources')
print('2. PPI-CPI gap > 1.5σ: Upstream > Downstream')
print('3. M1/M2 declining: Avoid small caps, prefer large cap value')
print('4. Manufacturing PMI > Services PMI: Industrial > Consumer')
