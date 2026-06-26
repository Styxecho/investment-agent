#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
行业轮动卫星策略 - Day 5-6修正版: 排名稳定性 + 优势池构建
严格遵循Phase_2.4&2.5_Methodology_Summary.md V5.0方法论

输入: industry_momentum_monthly_history.csv (月度RS_score历史)
输出: industry_rs_scores.csv + industry_selected_pool.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

OUTPUT_DIR = Path('docs/research/industry_rotation')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==================== Step 1: 读取月度历史数据 ====================
print("="*60)
print("Step 1: 读取月度RS_score历史数据")
print("="*60)

df_history = pd.read_csv(OUTPUT_DIR / 'industry_momentum_monthly_history.csv', encoding='utf-8-sig')
df_history['year_month'] = pd.to_datetime(df_history['year_month']).dt.to_period('M')

print(f"历史数据: {df_history['year_month'].min()} ~ {df_history['year_month'].max()}")
print(f"总记录数: {len(df_history)}")
print(f"行业数: {df_history['index_code'].nunique()}")
print(f"月份数: {df_history['year_month'].nunique()}")

# ==================== Step 2: 计算排名稳定性 ====================
print("\n" + "="*60)
print("Step 2: 计算排名稳定性 (Stability_score)")
print("="*60)

# 对每个月，统计通过MA60的行业总数N（用于缺失值惩罚）
# 这里假设所有在df_history中的记录都通过了MA60（因为MA60是前置过滤）
# 实际上，如果某月某行业未通过MA60，它不会出现在该月的df_history中
monthly_counts = df_history.groupby('year_month').size().reset_index(name='n_passed')

# 计算每个行业的排名稳定性（回溯6个月）
stability_results = []

for sw_code in df_history['index_code'].unique():
    df_ind = df_history[df_history['index_code'] == sw_code].sort_values('year_month')
    
    if len(df_ind) < 6:
        continue
    
    # 取最近6个月
    recent = df_ind.tail(6).copy()
    n_months = len(recent)
    
    # 获取这些月份的行业总数N
    recent_ym = recent['year_month'].tolist()
    n_data = monthly_counts[monthly_counts['year_month'].isin(recent_ym)]
    
    # 缺失值惩罚：如果某月没有记录（未通过MA60），该月排名 = N+1
    # 这里需要检查月份连续性
    ranks = recent['rank'].tolist()
    
    # 计算惩罚性排名（对缺失月份）
    penalty_ranks = []
    for _, row_n in n_data.iterrows():
        ym = row_n['year_month']
        if ym not in recent_ym:
            penalty_ranks.append(row_n['n_passed'] + 1)
    
    all_ranks = ranks + penalty_ranks
    n_missing = len(penalty_ranks)
    
    if len(all_ranks) < 3:
        continue
    
    # 排名标准差
    rank_std = np.std(all_ranks, ddof=1) if len(all_ranks) > 1 else 0
    
    # 最新一个月数据
    latest = recent.iloc[-1]
    
    stability_results.append({
        'index_code': sw_code,
        'year_month': latest['year_month'],
        'rs_score': latest['rs_score'],
        'rank': latest['rank'],
        'rank_std': rank_std,
        'n_months': n_months,
        'n_missing': n_missing,
        'excess_6m': latest['excess_6m'],
        'excess_12m': latest['excess_12m'],
        'z_acceleration': latest['z_acceleration']
    })

df_stability = pd.DataFrame(stability_results)

# 截面计算Stability_score = Z(-σ_rank)
df_stability['stability_raw'] = -df_stability['rank_std']
df_stability['stability_score'] = stats.zscore(df_stability['stability_raw'], nan_policy='omit')

print(f"计算完成，共 {len(df_stability)} 个行业有稳定性得分")

# ==================== Step 3: 计算Composite_score ====================
print("\n" + "="*60)
print("Step 3: 计算Composite_score = 0.6*RS_score + 0.4*Stability_score")
print("="*60)

df_stability['composite_score'] = 0.6 * df_stability['rs_score'] + 0.4 * df_stability['stability_score']

# 按Composite_score排序
df_stability = df_stability.sort_values('composite_score', ascending=False).reset_index(drop=True)

print("Composite_score排名前10:")
for _, row in df_stability.head(10).iterrows():
    print(f"  {row['index_code']}: Composite={row['composite_score']:.3f} (RS={row['rs_score']:.3f}, Stability={row['stability_score']:.3f}, rank_std={row['rank_std']:.2f})")

print("\nComposite_score排名后5:")
for _, row in df_stability.tail(5).iterrows():
    print(f"  {row['index_code']}: Composite={row['composite_score']:.3f} (RS={row['rs_score']:.3f}, Stability={row['stability_score']:.3f}, rank_std={row['rank_std']:.2f})")

# ==================== Step 4: 构建优势池 ====================
print("\n" + "="*60)
print("Step 4: 构建优势池（条件A或条件B）")
print("="*60)

n_total = len(df_stability)

# 条件A: Composite_score > 0
condition_a = df_stability['composite_score'] > 0

# 条件B: 排名前1/3 且 Composite_score > -0.5
top_third = int(n_total / 3)
condition_b = (df_stability.index < top_third) & (df_stability['composite_score'] > -0.5)

# 并集
df_selected = df_stability[condition_a | condition_b].copy()

print(f"总行业数: {n_total}")
print(f"条件A (Composite > 0): {condition_a.sum()}")
print(f"条件B (前1/3且 > -0.5): {condition_b.sum()}")
print(f"优势池规模: {len(df_selected)}")

# ==================== Step 5: 合并行业名称和ETF信息 ====================
print("\n" + "="*60)
print("Step 5: 合并行业名称和ETF映射")
print("="*60)

# 读取行业名称映射
df_sw_names = pd.read_csv('data_external/reference/sw_industry_mapping.csv', encoding='utf-8-sig', dtype={'sw_code': str})
df_sw_names['sw_code_clean'] = df_sw_names['sw_code'].astype(str).str.replace('.SI', '', regex=False)

# 读取ETF映射
df_mapping = pd.read_csv(OUTPUT_DIR / 'industry_etf_mapping.csv', encoding='utf-8-sig', dtype={'sw_code': str})
df_mapping['sw_code_clean'] = df_mapping['sw_code'].astype(str).str.replace('.SI', '', regex=False)

# 添加行业名称
name_map = dict(zip(df_sw_names['sw_code_clean'], df_sw_names['sw_name']))
df_stability['sw_code_clean'] = df_stability['index_code'].astype(str).str.replace('.SI', '', regex=False)
df_stability['sw_name'] = df_stability['sw_code_clean'].map(name_map)

df_selected['sw_code_clean'] = df_selected['index_code'].astype(str).str.replace('.SI', '', regex=False)
df_selected['sw_name'] = df_selected['sw_code_clean'].map(name_map)

# 添加ETF信息
df_selected = df_selected.merge(
    df_mapping[['sw_code_clean', 'primary_etf_code', 'primary_etf_name', 'tier']],
    on='sw_code_clean',
    how='left'
)

print("优势池行业列表:")
for _, row in df_selected.iterrows():
    etf_info = f"ETF: {row['primary_etf_code']}" if pd.notna(row['primary_etf_code']) else "无ETF映射"
    print(f"  {row['sw_name']} ({row['index_code']}): Composite={row['composite_score']:.3f} | {etf_info}")

# ==================== Step 6: 输出结果 ====================
print("\n" + "="*60)
print("Step 6: 输出结果文件")
print("="*60)

# 添加ETF信息到完整表
df_stability = df_stability.merge(
    df_mapping[['sw_code_clean', 'primary_etf_code', 'primary_etf_name', 'tier']],
    on='sw_code_clean',
    how='left'
)

# 1. 完整得分表
output_all = OUTPUT_DIR / 'industry_rs_scores.csv'
df_stability.to_csv(output_all, index=False, encoding='utf-8-sig')
print(f"  完整得分表: {output_all}")

# 2. 优势池
output_pool = OUTPUT_DIR / 'industry_selected_pool.csv'
df_selected.to_csv(output_pool, index=False, encoding='utf-8-sig')
print(f"  优势池: {output_pool}")

# 统计
print(f"\n统计:")
print(f"  总行业数: {len(df_stability)}")
print(f"  优势池: {len(df_selected)}")
print(f"  有ETF映射: {df_selected['primary_etf_code'].notna().sum()}")
print(f"  无ETF映射: {df_selected['primary_etf_code'].isna().sum()}")

print("\n" + "="*60)
print("Day 5-6 修正版执行完成!")
print("="*60)
