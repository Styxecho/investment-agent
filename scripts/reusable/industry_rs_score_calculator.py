#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
行业轮动卫星策略 - Day 5-6: 排名稳定性(RS_score) + 优势池构建
输入: index_daily表 (申万一级行业指数 + 中证全指)
输出: industry_rs_scores.csv, industry_selected_pool.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta

OUTPUT_DIR = Path('docs/research/industry_rotation')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==================== Step 1: 读取历史数据 ====================
print("="*60)
print("Step 1: 读取申万行业指数和中证全指历史数据")
print("="*60)

conn = sqlite3.connect('data_external/db/external_data.db')

# 读取所有申万行业指数日频数据
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
print(f"中证全指数据: {df_bench['trade_date'].min()} ~ {df_bench['trade_date'].max()}")

# ==================== Step 2: 计算月度动量指标 ====================
print("\n" + "="*60)
print("Step 2: 计算月度动量指标")
print("="*60)

# 取每月最后一个交易日
df_sw_monthly = df_sw.sort_values(['index_code', 'trade_date'])
df_sw_monthly['year_month'] = df_sw_monthly['trade_date'].dt.to_period('M')
df_sw_monthly = df_sw_monthly.groupby(['index_code', 'year_month']).last().reset_index()

df_bench_monthly = df_bench.sort_values('trade_date')
df_bench_monthly['year_month'] = df_bench_monthly['trade_date'].dt.to_period('M')
df_bench_monthly = df_bench_monthly.groupby('year_month').last().reset_index()

print(f"月度数据点数: {len(df_sw_monthly)} (行业×月份)")

# 计算月度收益率和动量
def calculate_momentum(df_ind, df_benchmark):
    """计算某行业的月度动量指标"""
    df = df_ind.sort_values('trade_date').copy()
    
    # 月度收益率
    df['monthly_ret'] = df['close_price'] / df['close_price'].shift(1) - 1
    
    # 6个月收益率
    df['ret_6m'] = df['close_price'] / df['close_price'].shift(6) - 1
    
    # 12个月收益率
    df['ret_12m'] = df['close_price'] / df['close_price'].shift(12) - 1
    
    # 加速度
    df['acceleration'] = df['ret_6m'] - df['ret_12m']
    
    # MA60 (约3个月)
    df['ma3'] = df['close_price'].rolling(window=3, min_periods=3).mean()
    df['above_ma3'] = df['close_price'] > df['ma3']
    
    return df

# 计算所有行业的月度动量
all_monthly = []

for sw_code in df_sw_monthly['index_code'].unique():
    df_ind = df_sw_monthly[df_sw_monthly['index_code'] == sw_code].copy()
    df_ind = calculate_momentum(df_ind, df_bench_monthly)
    all_monthly.append(df_ind)

df_all_monthly = pd.concat(all_monthly, ignore_index=True)

# 合并中证全指基准
df_bench_calc = df_bench_monthly.copy()
df_bench_calc['bench_ret_6m'] = df_bench_calc['close_price'] / df_bench_calc['close_price'].shift(6) - 1
df_bench_calc['bench_ret_12m'] = df_bench_calc['close_price'] / df_bench_calc['close_price'].shift(12) - 1
df_bench_calc['bench_acceleration'] = df_bench_calc['bench_ret_6m'] - df_bench_calc['bench_ret_12m']

df_all_monthly = df_all_monthly.merge(
    df_bench_calc[['year_month', 'bench_ret_6m', 'bench_ret_12m', 'bench_acceleration']], 
    on='year_month', 
    how='left'
)

# 计算相对指标
df_all_monthly['rel_ret_6m'] = df_all_monthly['ret_6m'] - df_all_monthly['bench_ret_6m']
df_all_monthly['rel_acceleration'] = df_all_monthly['acceleration'] - df_all_monthly['bench_acceleration']
df_all_monthly['composite_score'] = 0.5 * df_all_monthly['rel_ret_6m'] + 0.5 * df_all_monthly['rel_acceleration']

# 每月排名
df_all_monthly['monthly_rank'] = df_all_monthly.groupby('year_month')['composite_score'].rank(ascending=False, method='min')

print(f"计算完成，共 {len(df_all_monthly)} 条月度记录")

# ==================== Step 3: 计算排名稳定性(RS_score) ====================
print("\n" + "="*60)
print("Step 3: 计算排名稳定性(RS_score)")
print("="*60)

# 只取有至少12个月历史数据的行业
min_history = 12  # 至少12个月历史

current_month = df_all_monthly['year_month'].max()
rs_results = []

for sw_code in df_all_monthly['index_code'].unique():
    df_ind = df_all_monthly[df_all_monthly['index_code'] == sw_code].sort_values('year_month')
    
    if len(df_ind) < min_history:
        continue
    
    # 取最近12个月的排名
    recent = df_ind.tail(12)
    
    if len(recent) < 6:  # 至少6个月有数据
        continue
    
    # 计算排名稳定性指标
    avg_rank = recent['monthly_rank'].mean()
    rank_std = recent['monthly_rank'].std()
    rank_trend = recent['monthly_rank'].iloc[-1] - recent['monthly_rank'].iloc[0]  # 负值=排名上升
    
    # RS_score = 排名稳定性 + 趋势性
    # 排名越低越好（1=最好），所以用 32 - rank
    # 排名标准差小 = 稳定 = 好
    # 排名趋势下降（负值）= 上升 = 好
    
    # 归一化：平均排名(1-31) → 得分(0-100)
    rank_score = max(0, 100 - (avg_rank - 1) * 100 / 30)  # 排名1=100分, 排名31=0分
    
    # 稳定性得分：标准差小=高得分
    stability_score = max(0, 100 - rank_std * 10) if pd.notna(rank_std) else 50
    
    # 趋势得分：排名改善（负值）= 高得分
    trend_score = max(0, min(100, 50 - rank_trend * 5))  # 排名下降5位=75分
    
    # 综合RS_score
    rs_score = 0.4 * rank_score + 0.3 * stability_score + 0.3 * trend_score
    
    # 最新一期数据
    latest = df_ind.iloc[-1]
    
    rs_results.append({
        'sw_code': sw_code,
        'sw_name': sw_code,  # 稍后填充
        'current_rank': latest['monthly_rank'],
        'avg_rank_12m': avg_rank,
        'rank_std_12m': rank_std,
        'rank_trend': rank_trend,
        'rank_score': rank_score,
        'stability_score': stability_score,
        'trend_score': trend_score,
        'rs_score': rs_score,
        'above_ma3': latest['above_ma3'],
        'composite_score': latest['composite_score'],
        'rel_ret_6m': latest['rel_ret_6m'],
        'rel_acceleration': latest['rel_acceleration'],
        'trade_date': latest['trade_date']
    })

df_rs = pd.DataFrame(rs_results)

# 按RS_score排序
df_rs = df_rs.sort_values('rs_score', ascending=False).reset_index(drop=True)

print(f"计算完成，共 {len(df_rs)} 个行业有RS_score")
print("\nRS_score排名前10:")
for _, row in df_rs.head(10).iterrows():
    ma_status = "UP" if row['above_ma3'] else "DN"
    print(f"  [{ma_status}] {row['sw_code']}: RS={row['rs_score']:.1f} (排名={row['current_rank']:.0f}, 趋势={row['rank_trend']:+.0f})")

print("\nRS_score排名后5:")
for _, row in df_rs.tail(5).iterrows():
    ma_status = "UP" if row['above_ma3'] else "DN"
    print(f"  [{ma_status}] {row['sw_code']}: RS={row['rs_score']:.1f} (排名={row['current_rank']:.0f}, 趋势={row['rank_trend']:+.0f})")

# ==================== Step 4: 构建优势池 ====================
print("\n" + "="*60)
print("Step 4: 构建优势池")
print("="*60)

# 读取行业-ETF映射表和行业名称映射表
df_mapping = pd.read_csv(OUTPUT_DIR / 'industry_etf_mapping.csv', encoding='utf-8-sig', dtype={'sw_code': str})
df_sw_names = pd.read_csv('data_external/reference/sw_industry_mapping.csv', encoding='utf-8-sig', dtype={'sw_code': str})

# 合并行业名称（统一格式：去掉.SI后缀）
df_mapping['sw_code_clean'] = df_mapping['sw_code'].astype(str).str.replace('.SI', '', regex=False)
df_sw_names['sw_code_clean'] = df_sw_names['sw_code'].astype(str).str.replace('.SI', '', regex=False)
df_rs['sw_code_clean'] = df_rs['sw_code'].astype(str).str.replace('.SI', '', regex=False)

# 优先使用专用映射表，其次使用ETF映射表
sw_name_map = dict(zip(df_sw_names['sw_code_clean'], df_sw_names['sw_name']))
sw_name_map2 = dict(zip(df_mapping['sw_code_clean'], df_mapping['sw_name']))
sw_name_map.update(sw_name_map2)  # ETF映射表覆盖（如有差异）

df_rs['sw_name'] = df_rs['sw_code_clean'].map(sw_name_map)

# 优势池构建规则：
# 1. MA60过滤：只选above_ma3=True的
# 2. 取RS_score前50%（或前N个）
# 3. 每个行业最多1只ETF（首选）

# 先过滤MA60
df_pass_ma = df_rs[df_rs['above_ma3'] == True].copy()

print(f"MA60上方行业: {len(df_pass_ma)}/{len(df_rs)}")

# 取RS_score前50%（或至少前8个）
top_n = max(8, int(len(df_pass_ma) * 0.5))
df_selected = df_pass_ma.head(top_n).copy()

print(f"优势池规模: {len(df_selected)}个行业")

# 合并ETF信息（使用clean后的code）
df_selected['sw_code_clean'] = df_selected['sw_code'].astype(str).str.replace('.SI', '', regex=False)
df_mapping['sw_code_clean'] = df_mapping['sw_code'].astype(str).str.replace('.SI', '', regex=False)

df_selected = df_selected.merge(
    df_mapping[['sw_code_clean', 'primary_etf_code', 'primary_etf_name', 'tier']],
    on='sw_code_clean',
    how='left'
)

print("\n优势池行业列表:")
for i, row in df_selected.iterrows():
    print(f"  {i+1}. {row['sw_name']} ({row['sw_code']})")
    print(f"      ETF: {row['primary_etf_code']} | RS={row['rs_score']:.1f} | 排名={row['current_rank']:.0f} | 6M={row['rel_ret_6m']:.1%}")

# ==================== Step 5: 输出结果 ====================
print("\n" + "="*60)
print("Step 5: 输出结果文件")
print("="*60)

# 1. RS_score详细表
rs_path = OUTPUT_DIR / 'industry_rs_scores.csv'
df_rs.to_csv(rs_path, index=False, encoding='utf-8-sig')
print(f"  RS_score表: {rs_path}")

# 2. 优势池
pool_path = OUTPUT_DIR / 'industry_selected_pool.csv'
df_selected.to_csv(pool_path, index=False, encoding='utf-8-sig')
print(f"  优势池: {pool_path}")

# 统计
print(f"\n统计:")
print(f"  总行业数: {len(df_rs)}")
print(f"  MA60上方: {len(df_pass_ma)}")
print(f"  优势池规模: {len(df_selected)}")
print(f"  Core映射: {(df_selected['tier']=='core').sum()}")
print(f"  Backup映射: {(df_selected['tier']=='backup').sum()}")

print("\n" + "="*60)
print("Day 5-6 执行完成!")
print("="*60)
