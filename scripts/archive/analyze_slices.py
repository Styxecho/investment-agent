#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd

csv_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_history.csv'
df = pd.read_csv(csv_path, encoding='utf-8-sig')
df['year_month'] = df['year_month'].astype(str)

slices = {
    'Slice 1: 2016-2017 (Supply-side Reform)': ('201607', '201712'),
    'Slice 2: 2019-2020 (Trade War + COVID)': ('201901', '202012'),
    'Slice 3: 2021-2022 (Inflation + Policy Turn)': ('202101', '202212'),
    'Slice 4: 2023-2024 (Recovery Validation)': ('202301', '202412')
}

for slice_name, (start, end) in slices.items():
    print()
    print('='*80)
    print(slice_name)
    print('='*80)
    
    mask = (df['year_month'] >= start) & (df['year_month'] <= end)
    slice_df = df[mask].copy()
    
    if len(slice_df) == 0:
        print('No data available')
        continue
    
    print('\nCoverage:', len(slice_df), 'months')
    print('Period:', slice_df['year_month'].min(), 'to', slice_df['year_month'].max())
    
    print('\n[State Distribution]')
    state_counts = slice_df['state'].value_counts()
    for state, count in state_counts.items():
        pct = count / len(slice_df) * 100
        print(' ', state, ':', count, 'months (', f'{pct:.1f}%)')
    
    avg_conf = slice_df['confidence'].mean()
    print('\nAvg Confidence:', f'{avg_conf:.2f}')
    
    print('\n[Liquidity Distribution]')
    liq_counts = slice_df['liquidity'].value_counts()
    for liq, count in liq_counts.items():
        pct = count / len(slice_df) * 100
        print(' ', liq, ':', count, 'months (', f'{pct:.1f}%)')
    
    print('\n[Inflation Distribution]')
    inf_counts = slice_df['inflation'].value_counts()
    for inf, count in inf_counts.items():
        pct = count / len(slice_df) * 100
        print(' ', inf, ':', count, 'months (', f'{pct:.1f}%)')
    
    print('\n[Monthly Details - First 12 months]')
    print('Month     State       Conf   Liquidity       Inflation')
    print('-' * 55)
    for _, row in slice_df.head(12).iterrows():
        print(row['year_month'], '  ', row['state'], '  ', f"{row['confidence']:.2f}", '  ', row['liquidity'], '  ', row['inflation'])
    
    if len(slice_df) > 12:
        print('... and', len(slice_df)-12, 'more months')

print('\nDone!')
