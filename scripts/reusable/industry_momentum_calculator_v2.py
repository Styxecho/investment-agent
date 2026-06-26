#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
行业轮动卫星策略 - Day 3-4修正版: 多周期动量与加速度
严格遵循Phase_2.4&2.5_Methodology_Summary.md V5.0方法论

正确公式:
RS_score = 0.40 × Z(6M超额) + 0.30 × Z(12M超额) + 0.30 × Z(加速度)
其中 加速度 = Z(1M超额) - Z(3M超额)，再对结果做截面Z-score

所有Z-score均为当月31个行业的截面标准化
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sqlite3
from scipy import stats

OUTPUT_DIR = Path('docs/research/industry_rotation')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==================== Step 1: 读取数据 ====================
print("="*60)
print("Step 1: 读取申万行业指数和中证全指数据")
print("="*60)

conn = sqlite3.connect('data_external/db/external_data.db')

# 读取所有申万行业指数
df_sw = pd.read_sql("""
    SELECT index_code, trade_date, close_price 
    FROM index_daily 
    WHERE index_code LIKE '801%.SI'
    ORDER BY index_code, trade_date
""", conn)

df_sw['trade_date'] = pd.to_datetime(df_sw['trade_date'], format='%Y%m%d')
df_sw['close_price'] = pd.to_numeric(df_sw['close_price'], errors='coerce')
df_sw = df_sw.dropna()

# 读取中证全指
df_bench = pd.read_sql("""
    SELECT index_code, trade_date, close_price 
    FROM index_daily 
    WHERE index_code = '000985.CSI'
    ORDER BY trade_date
""", conn)

df_bench['trade_date'] = pd.to_datetime(df_bench['trade_date'], format='%Y%m%d')
df_bench['close_price'] = pd.to_numeric(df_bench['close_price'], errors='coerce')
df_bench = df_bench.dropna()

conn.close()

print(f"申万行业数据: {df_sw['trade_date'].min()} ~ {df_sw['trade_date'].max()}")
print(f"行业数量: {df_sw['index_code'].nunique()}")

# ==================== Step 2: 计算月度收益率和超额收益 ====================
print("\n" + "="*60)
print("Step 2: 计算月度收益率和超额收益")
print("="*60)

# 取每月最后一个交易日
df_sw_monthly = df_sw.sort_values(['index_code', 'trade_date'])
df_sw_monthly['year_month'] = df_sw_monthly['trade_date'].dt.to_period('M')
df_sw_monthly = df_sw_monthly.groupby(['index_code', 'year_month']).last().reset_index()

df_bench_monthly = df_bench.sort_values('trade_date')
df_bench_monthly['year_month'] = df_bench_monthly['trade_date'].dt.to_period('M')
df_bench_monthly = df_bench_monthly.groupby('year_month').last().reset_index()

# 合并基准
df_all = df_sw_monthly.merge(
    df_bench_monthly[['year_month', 'close_price']], 
    on='year_month', 
    how='left',
    suffixes=('_ind', '_bench')
)

# 计算月度收益率
df_all = df_all.sort_values(['index_code', 'year_month'])
df_all['ret_1m'] = df_all.groupby('index_code')['close_price_ind'].pct_change(1)
df_all['ret_3m'] = df_all.groupby('index_code')['close_price_ind'].pct_change(3)
df_all['ret_6m'] = df_all.groupby('index_code')['close_price_ind'].pct_change(6)
df_all['ret_12m'] = df_all.groupby('index_code')['close_price_ind'].pct_change(12)

# 基准收益率
df_bench_monthly['bench_ret_1m'] = df_bench_monthly['close_price'].pct_change(1)
df_bench_monthly['bench_ret_3m'] = df_bench_monthly['close_price'].pct_change(3)
df_bench_monthly['bench_ret_6m'] = df_bench_monthly['close_price'].pct_change(6)
df_bench_monthly['bench_ret_12m'] = df_bench_monthly['close_price'].pct_change(12)

df_all = df_all.merge(
    df_bench_monthly[['year_month', 'bench_ret_1m', 'bench_ret_3m', 'bench_ret_6m', 'bench_ret_12m']], 
    on='year_month', 
    how='left'
)

# 超额收益 = 行业收益 - 基准收益
df_all['excess_1m'] = df_all['ret_1m'] - df_all['bench_ret_1m']
df_all['excess_3m'] = df_all['ret_3m'] - df_all['bench_ret_3m']
df_all['excess_6m'] = df_all['ret_6m'] - df_all['bench_ret_6m']
df_all['excess_12m'] = df_all['ret_12m'] - df_all['bench_ret_12m']

print(f"月度数据点数: {len(df_all)} (行业×月份)")

# ==================== Step 3: 每月截面计算RS_score ====================
print("\n" + "="*60)
print("Step 3: 每月截面计算RS_score（严格按方法论V5.0）")
print("="*60)

monthly_results = []

for ym, group in df_all.groupby('year_month'):
    # 只保留有完整数据（1M/3M/6M/12M超额都不为空）的行业
    valid = group[
        group['excess_1m'].notna() & 
        group['excess_3m'].notna() & 
        group['excess_6m'].notna() & 
        group['excess_12m'].notna()
    ].copy()
    
    if len(valid) < 5:  # 至少需要5个行业
        continue
    
    # 1. 截面Z-score标准化（使用总体标准差 ddof=0，处理极端值clip到±3倍标准差）
    def safe_zscore(x):
        z = stats.zscore(x, nan_policy='omit', ddof=0)
        return np.clip(z, -3, 3)  # 防止极端值影响
    
    valid['z_6m'] = safe_zscore(valid['excess_6m'])
    valid['z_12m'] = safe_zscore(valid['excess_12m'])
    valid['z_1m'] = safe_zscore(valid['excess_1m'])
    valid['z_3m'] = safe_zscore(valid['excess_3m'])
    
    # 2. 加速度 = Z(1M超额) - Z(3M超额)
    valid['acceleration_raw'] = valid['z_1m'] - valid['z_3m']
    
    # 3. 对加速度再做截面Z-score标准化
    valid['z_acceleration'] = safe_zscore(valid['acceleration_raw'])
    
    # 4. RS_score = 0.4*Z(6M) + 0.3*Z(12M) + 0.3*Z(加速度)
    valid['rs_score'] = 0.4 * valid['z_6m'] + 0.3 * valid['z_12m'] + 0.3 * valid['z_acceleration']
    
    # 5. 截面排名（1=最好）
    valid['rank'] = valid['rs_score'].rank(ascending=False, method='min')
    
    monthly_results.append(valid[[
        'index_code', 'year_month', 'rs_score', 'rank',
        'excess_1m', 'excess_3m', 'excess_6m', 'excess_12m',
        'z_1m', 'z_3m', 'z_6m', 'z_12m',
        'acceleration_raw', 'z_acceleration',
        'close_price_ind'
    ]])

df_monthly = pd.concat(monthly_results, ignore_index=True)
print(f"计算完成，共 {len(df_monthly)} 条月度记录")
print(f"覆盖 {df_monthly['year_month'].nunique()} 个月份")

# 显示最新月份结果
latest_ym = df_monthly['year_month'].max()
print(f"\n最新月份 ({latest_ym}) RS_score Top 5:")
latest_df = df_monthly[df_monthly['year_month'] == latest_ym].sort_values('rs_score', ascending=False)
for _, row in latest_df.head(5).iterrows():
    print(f"  {row['index_code']}: RS={row['rs_score']:.3f} (6M={row['excess_6m']:.2%}, 12M={row['excess_12m']:.2%}, ACC={row['acceleration_raw']:.3f})")

# ==================== Step 4: 计算MA60（日频）====================
print("\n" + "="*60)
print("Step 4: 计算MA60并标记最新状态")
print("="*60)

# 对每只行业计算最新MA60
ma60_results = []
for sw_code in df_sw['index_code'].unique():
    df_ind = df_sw[df_sw['index_code'] == sw_code].sort_values('trade_date')
    if len(df_ind) >= 60:
        latest = df_ind.iloc[-1]
        ma60 = df_ind['close_price'].tail(60).mean()
        ma60_results.append({
            'index_code': sw_code,
            'trade_date': latest['trade_date'],
            'close_price': latest['close_price'],
            'ma60': ma60,
            'above_ma60': latest['close_price'] > ma60
        })

df_ma60 = pd.DataFrame(ma60_results)
print(f"MA60计算完成，共 {len(df_ma60)} 个行业")

# ==================== Step 5: 合并最新RS_score和MA60 ====================
print("\n" + "="*60)
print("Step 5: 合并最新动量和MA60状态")
print("="*60)

# 取每个月份最新的RS_score（最新月份）
latest_monthly = df_monthly[df_monthly['year_month'] == latest_ym].copy()

# 合并MA60
df_momentum = latest_monthly.merge(df_ma60, on='index_code', how='left')

# 添加行业名称
df_sw_names = pd.read_csv('data_external/reference/sw_industry_mapping.csv', encoding='utf-8-sig', dtype={'sw_code': str})
df_sw_names['sw_code_clean'] = df_sw_names['sw_code'].astype(str).str.replace('.SI', '', regex=False)
df_momentum['sw_code_clean'] = df_momentum['index_code'].astype(str).str.replace('.SI', '', regex=False)
name_map = dict(zip(df_sw_names['sw_code_clean'], df_sw_names['sw_name']))
df_momentum['sw_name'] = df_momentum['sw_code_clean'].map(name_map)

# 按RS_score排序
df_momentum = df_momentum.sort_values('rs_score', ascending=False).reset_index(drop=True)

print("最新动量排名:")
for _, row in df_momentum.iterrows():
    ma_status = "UP" if row['above_ma60'] else "DN"
    print(f"  [{ma_status}] {row['sw_name']} ({row['index_code']}): RS={row['rs_score']:.3f} | rank={row['rank']:.0f}")

# ==================== Step 6: 输出结果 ====================
print("\n" + "="*60)
print("Step 6: 输出结果文件")
print("="*60)

# 保存完整月度历史（用于后续稳定性计算）
history_path = OUTPUT_DIR / 'industry_momentum_monthly_history.csv'
df_monthly.to_csv(history_path, index=False, encoding='utf-8-sig')
print(f"  月度历史数据: {history_path}")

# 保存最新动量得分
output_path = OUTPUT_DIR / 'industry_momentum_scores.csv'
df_momentum.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"  最新动量得分: {output_path}")

# 统计
ma60_pass = df_momentum['above_ma60'].sum()
print(f"\n统计:")
print(f"  总行业数: {len(df_momentum)}")
print(f"  MA60上方: {ma60_pass} ({ma60_pass/len(df_momentum)*100:.1f}%)")
print(f"  MA60下方: {len(df_momentum)-ma60_pass}")

print("\n" + "="*60)
print("Day 3-4 修正版执行完成!")
print("="*60)
