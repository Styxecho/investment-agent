#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证两个问题：
1. 春节效应：使用准确春节日期 vs 简单1-2月
2. 回归中加入trend是否与HP滤波重叠
"""
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
import pandas as pd
import numpy as np
from data_external.db.engine import engine
from scipy import stats

print('=== 验证1：春节效应对比（准确日期 vs 1-2月简单处理） ===\n')

# 准确的春节日期
spring_festival_dates = {
    2015: '20150219', 2016: '20160208', 2017: '20170128', 2018: '20180216',
    2019: '20190205', 2020: '20200125', 2021: '20210212', 2022: '20220201',
    2023: '20230122', 2024: '20240210', 2025: '20250129', 2026: '20260217'
}

indicators = ['CN_IAV_YOY_M', 'CN_CPI_YOY_M', 'CN_PPI_YOY_M', 'CN_M2_YOY_M', 
              'CN_M1_YOY_M', 'CN_M0_YOY_M', 'CN_SFS_YOY_M', 'CN_IIV_YOY_M', 'CN_M1M2_DIFF_M']

for code in indicators:
    df = pd.read_sql(f"""
        SELECT publish_date, value
        FROM macro_indicator_value
        WHERE indicator_code = '{code}' AND publish_date >= '20150101'
        ORDER BY publish_date
    """, engine)
    
    if df.empty:
        continue
    
    df['date'] = pd.to_datetime(df['publish_date'], format='%Y%m%d')
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    
    # 方法A：准确春节月
    df['is_sf_exact'] = False
    for year, sf_date in spring_festival_dates.items():
        sf_month = int(sf_date[4:6])
        df.loc[(df['year'] == year) & (df['month'] == sf_month), 'is_sf_exact'] = True
    
    # 方法B：简单1-2月
    df['is_sf_simple'] = df['month'].isin([1, 2])
    
    # 统计对比
    sf_exact = df[df['is_sf_exact'] == True]['value'].dropna()
    sf_simple = df[df['is_sf_simple'] == True]['value'].dropna()
    non_sf = df[(df['is_sf_exact'] == False) & (df['is_sf_simple'] == False)]['value'].dropna()
    
    if len(sf_exact) >= 5 and len(non_sf) >= 20:
        # 准确春节月 vs 非春节
        diff_exact = sf_exact.mean() - non_sf.mean()
        t_exact, p_exact = stats.ttest_ind(sf_exact, non_sf)
        
        # 简单1-2月 vs 非春节
        diff_simple = sf_simple.mean() - non_sf.mean()
        t_simple, p_simple = stats.ttest_ind(sf_simple, non_sf)
        
        sig_e = '***' if p_exact < 0.01 else '**' if p_exact < 0.05 else '*' if p_exact < 0.1 else ''
        sig_s = '***' if p_simple < 0.01 else '**' if p_simple < 0.05 else '*' if p_simple < 0.1 else ''
        
        print(f"{code}:")
        print(f"  准确春节月: 均值={sf_exact.mean():.2f}, 差异={diff_exact:.2f} {sig_e}, p={p_exact:.3f}")
        print(f"  简单1-2月:  均值={sf_simple.mean():.2f}, 差异={diff_simple:.2f} {sig_s}, p={p_simple:.3f}")
        print(f"  非春节月:   均值={non_sf.mean():.2f}")
        print()

print('\n=== 验证2：trend变量与HP滤波是否重叠 ===\n')

# 取一个指标做示例（PMI）
df_pmi = pd.read_sql("""
    SELECT publish_date, value
    FROM macro_indicator_value
    WHERE indicator_code = 'CN_PMI_MFG_M' AND publish_date >= '20150101'
    ORDER BY publish_date
""", engine)

df_pmi['date'] = pd.to_datetime(df_pmi['publish_date'], format='%Y%m%d')
df_pmi = df_pmi.set_index('date').sort_index()
df_pmi['value_50'] = df_pmi['value'] - 50

# 方法A：先回归提取trend，再HP滤波
from sklearn.linear_model import LinearRegression
X = np.arange(len(df_pmi)).reshape(-1, 1)
y = df_pmi['value_50'].values
model = LinearRegression().fit(X, y)
trend_reg = model.predict(X)
resid_reg = y - trend_reg

# 方法B：直接HP滤波
from statsmodels.tsa.filters.hp_filter import hpfilter
cycle_hp, trend_hp = hpfilter(df_pmi['value_50'], lamb=14400)

# 对比两种方法的trend
print("方法对比（前5个月）:")
print(f"  月份: {df_pmi.index[:5].strftime('%Y-%m').tolist()}")
print(f"  回归trend: {trend_reg[:5].round(3)}")
print(f"  HP-trend:  {trend_hp.values[:5].round(3)}")
print(f"  回归resid: {resid_reg[:5].round(3)}")
print(f"  HP-cycle:  {cycle_hp.values[:5].round(3)}")

# 相关性
corr_trend = np.corrcoef(trend_reg, trend_hp.values)[0, 1]
corr_resid = np.corrcoef(resid_reg, cycle_hp.values)[0, 1]

print(f"\n两种方法trend的相关性: {corr_trend:.4f}")
print(f"两种方法cycle的相关性: {corr_resid:.4f}")

if corr_trend > 0.95:
    print("结论: trend回归与HP-trend高度相关(>0.95)，确实存在冗余!")
else:
    print("结论: 两者相关性不高，可以共存")
