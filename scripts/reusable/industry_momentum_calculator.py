#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
行业轮动卫星策略 - Day 3-4: MA60过滤 + 多周期动量计算
输入: index_daily 表 (申万一级行业指数 + 中证全指)
输出: industry_momentum_scores.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sqlite3

OUTPUT_DIR = Path('docs/research/industry_rotation')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==================== Step 1: 读取数据 ====================
print("="*60)
print("Step 1: 读取申万行业指数和中证全指数据")
print("="*60)

# 连接数据库
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

print(f"申万行业指数记录数: {len(df_sw)}")
print(f"行业数量: {df_sw['index_code'].nunique()}")
print(f"日期范围: {df_sw['trade_date'].min()} ~ {df_sw['trade_date'].max()}")

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

print(f"\n中证全指记录数: {len(df_bench)}")
print(f"日期范围: {df_bench['trade_date'].min()} ~ {df_bench['trade_date'].max()}")

conn.close()

# ==================== Step 2: 计算技术指标 ====================
print("\n" + "="*60)
print("Step 2: 计算MA60、6M/12M收益率、加速度")
print("="*60)

# 交易日映射（用于查找N个交易日前的价格）
all_dates = sorted(df_sw['trade_date'].unique())
date_to_idx = {d: i for i, d in enumerate(all_dates)}

# 对每只行业指数计算技术指标
results = []

for sw_code in sorted(df_sw['index_code'].unique()):
    df_ind = df_sw[df_sw['index_code'] == sw_code].sort_values('trade_date').reset_index(drop=True)
    
    if len(df_ind) < 252:
        print(f"  警告: {sw_code} 数据不足252个交易日，跳过")
        continue
    
    # MA60
    df_ind['ma60'] = df_ind['close_price'].rolling(window=60, min_periods=60).mean()
    
    # 6个月收益率 (约126个交易日)
    df_ind['ret_6m'] = df_ind['close_price'] / df_ind['close_price'].shift(126) - 1
    
    # 12个月收益率 (约252个交易日)
    df_ind['ret_12m'] = df_ind['close_price'] / df_ind['close_price'].shift(252) - 1
    
    # 加速度 = 6M - 12M
    df_ind['acceleration'] = df_ind['ret_6m'] - df_ind['ret_12m']
    
    # 取最新一条记录
    latest = df_ind.iloc[-1].copy()
    
    results.append({
        'sw_code': sw_code,
        'trade_date': latest['trade_date'],
        'close_price': latest['close_price'],
        'ma60': latest['ma60'],
        'above_ma60': latest['close_price'] > latest['ma60'] if pd.notna(latest['ma60']) else False,
        'ret_6m': latest['ret_6m'],
        'ret_12m': latest['ret_12m'],
        'acceleration': latest['acceleration']
    })

df_momentum = pd.DataFrame(results)
print(f"计算完成，共 {len(df_momentum)} 个行业")

# ==================== Step 3: 计算相对中证全指指标 ====================
print("\n" + "="*60)
print("Step 3: 计算相对中证全指的超额动量")
print("="*60)

# 计算中证全指的同期指标
df_bench_calc = df_bench.copy()
df_bench_calc['ret_6m'] = df_bench_calc['close_price'] / df_bench_calc['close_price'].shift(126) - 1
df_bench_calc['ret_12m'] = df_bench_calc['close_price'] / df_bench_calc['close_price'].shift(252) - 1
df_bench_calc['acceleration'] = df_bench_calc['ret_6m'] - df_bench_calc['ret_12m']

latest_bench = df_bench_calc.iloc[-1]
print(f"中证全指最新日期: {latest_bench['trade_date']}")
print(f"中证全指 6M收益: {latest_bench['ret_6m']:.2%}")
print(f"中证全指 12M收益: {latest_bench['ret_12m']:.2%}")
print(f"中证全指 加速度: {latest_bench['acceleration']:.2%}")

# 计算相对指标
df_momentum['rel_ret_6m'] = df_momentum['ret_6m'] - latest_bench['ret_6m']
df_momentum['rel_ret_12m'] = df_momentum['ret_12m'] - latest_bench['ret_12m']
df_momentum['rel_acceleration'] = df_momentum['acceleration'] - latest_bench['acceleration']

# ==================== Step 4: 计算Composite Score ====================
print("\n" + "="*60)
print("Step 4: 计算 Composite Score")
print("="*60)

# Composite = 0.5 * 相对6M + 0.5 * 相对加速度
df_momentum['composite_score'] = 0.5 * df_momentum['rel_ret_6m'] + 0.5 * df_momentum['rel_acceleration']

# 按Composite Score排序
df_momentum = df_momentum.sort_values('composite_score', ascending=False).reset_index(drop=True)
df_momentum['rank'] = range(1, len(df_momentum) + 1)

print("Composite Score 排名前10:")
for _, row in df_momentum.head(10).iterrows():
    status = "UP" if row['above_ma60'] else "DN"
    print(f"  [{status}] {row['sw_code']}: {row['composite_score']:.2%} (6M={row['rel_ret_6m']:.2%}, ACC={row['rel_acceleration']:.2%})")

print("\nComposite Score 排名后10:")
for _, row in df_momentum.tail(10).iterrows():
    status = "UP" if row['above_ma60'] else "DN"
    print(f"  [{status}] {row['sw_code']}: {row['composite_score']:.2%} (6M={row['rel_ret_6m']:.2%}, ACC={row['rel_acceleration']:.2%})")

# ==================== Step 5: 输出结果 ====================
print("\n" + "="*60)
print("Step 5: 输出结果文件")
print("="*60)

# 保存完整动量得分表
output_path = OUTPUT_DIR / 'industry_momentum_scores.csv'
df_momentum.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"  动量得分表: {output_path}")

# 统计
ma60_pass = df_momentum['above_ma60'].sum()
print(f"\n统计:")
print(f"  总行业数: {len(df_momentum)}")
print(f"  MA60上方: {ma60_pass} ({ma60_pass/len(df_momentum)*100:.1f}%)")
print(f"  MA60下方: {len(df_momentum)-ma60_pass}")
print(f"  正Composite: {(df_momentum['composite_score'] > 0).sum()}")
print(f"  负Composite: {(df_momentum['composite_score'] <= 0).sum()}")

print("\n" + "="*60)
print("Day 3-4 执行完成!")
print("="*60)
