import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
import pandas as pd
import numpy as np

for code in ['CBA00101.CS', 'CBA00601.CS']:
    df = pd.read_sql("SELECT trade_date, close_price FROM index_daily WHERE index_code='%s' ORDER BY trade_date" % code, engine)
    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    df['ret'] = df['close_price'].pct_change()
    df = df.dropna()
    
    print('\n=== %s ===' % code)
    print('Range: %s to %s' % (df['trade_date'].min().date(), df['trade_date'].max().date()))
    print('Count: %d' % len(df))
    print('Full sample annualized vol: %.2f%%' % (df['ret'].std() * np.sqrt(252) * 100))
    
    df['vol_120'] = df['ret'].rolling(120).std() * np.sqrt(252)
    df['year'] = df['trade_date'].dt.year
    
    print('\nYearly volatility:')
    for year, vol in (df.groupby('year')['ret'].std() * np.sqrt(252)).items():
        print('  %d: %.2f%%' % (year, vol * 100))
    
    print('\nLatest 120-day vol: %.2f%%' % (df['vol_120'].iloc[-1] * 100))
    print('2024 avg vol: %.2f%%' % (df[df['year']==2024]['ret'].std() * np.sqrt(252) * 100))
    print('2023 avg vol: %.2f%%' % (df[df['year']==2023]['ret'].std() * np.sqrt(252) * 100))
    print('2022 avg vol: %.2f%%' % (df[df['year']==2022]['ret'].std() * np.sqrt(252) * 100))
    print('Max 120-day vol in history: %.2f%%' % (df['vol_120'].max() * 100))
    print('P95 120-day vol: %.2f%%' % (df['vol_120'].quantile(0.95) * 100))
    print('Median 120-day vol: %.2f%%' % (df['vol_120'].median() * 100))
