#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V7 宏观状态统计分析
- 象限持续时间
- 转换概率矩阵
- 月度汇总统计
"""

import pandas as pd
import numpy as np
import sys

sys.path.insert(0, r'D:\Study\Project\investment-agent')

# 读取数据
csv_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_detail.csv'
df = pd.read_csv(csv_path)
df['date'] = pd.to_datetime(df['publish_date'], format='%Y%m%d')

# ============================================================
# 1. 象限持续时间统计
# ============================================================

def analyze_regime_duration():
    print("=" * 70)
    print("一、象限持续时间统计")
    print("=" * 70)
    
    # 计算每个象限的连续持续时间
    current_regime = None
    start_date = None
    durations = []
    
    for idx, row in df.iterrows():
        if row['macro_regime'] != current_regime:
            if current_regime is not None:
                durations.append({
                    'regime': current_regime,
                    'start': start_date,
                    'end': df.iloc[idx-1]['date'],
                    'months': (df.iloc[idx-1]['date'].year - start_date.year) * 12 +
                             (df.iloc[idx-1]['date'].month - start_date.month) + 1
                })
            current_regime = row['macro_regime']
            start_date = row['date']
    
    # 最后一个区间
    durations.append({
        'regime': current_regime,
        'start': start_date,
        'end': df.iloc[-1]['date'],
        'months': (df.iloc[-1]['date'].year - start_date.year) * 12 +
                 (df.iloc[-1]['date'].month - start_date.month) + 1
    })
    
    duration_df = pd.DataFrame(durations)
    
    print("\n各象限持续区间:")
    print(duration_df.to_string(index=False))
    
    print("\n各象限持续时间统计:")
    stats = duration_df.groupby('regime')['months'].agg(['count', 'mean', 'min', 'max', 'std'])
    stats.columns = ['出现次数', '平均持续(月)', '最短(月)', '最长(月)', '标准差']
    print(stats.to_string())
    
    return duration_df

# ============================================================
# 2. 状态转换矩阵
# ============================================================

def analyze_transition_matrix():
    print("\n" + "=" * 70)
    print("二、状态转换概率矩阵")
    print("=" * 70)
    
    regimes = df['macro_regime'].unique()
    n = len(regimes)
    
    # 构建转换计数矩阵
    transition_counts = pd.DataFrame(0, index=regimes, columns=regimes)
    
    for i in range(len(df) - 1):
        from_regime = df['macro_regime'].iloc[i]
        to_regime = df['macro_regime'].iloc[i+1]
        transition_counts.loc[from_regime, to_regime] += 1
    
    # 计算概率
    transition_probs = transition_counts.div(transition_counts.sum(axis=1), axis=0).round(3)
    
    print("\n转换计数矩阵:")
    print(transition_counts.to_string())
    
    print("\n转换概率矩阵:")
    print(transition_probs.to_string())
    
    # 找出最常见的转换
    print("\n最常见的10个状态转换:")
    transitions = []
    for from_regime in regimes:
        for to_regime in regimes:
            count = transition_counts.loc[from_regime, to_regime]
            if count > 0:
                prob = transition_probs.loc[from_regime, to_regime]
                transitions.append({
                    'from': from_regime,
                    'to': to_regime,
                    'count': count,
                    'probability': prob
                })
    
    transitions_df = pd.DataFrame(transitions).sort_values('count', ascending=False)
    print(transitions_df.head(10).to_string(index=False))
    
    return transition_counts, transition_probs

# ============================================================
# 3. 各维度统计
# ============================================================

def analyze_dimensions():
    print("\n" + "=" * 70)
    print("三、各维度统计")
    print("=" * 70)
    
    # 增长维度
    print("\n增长维度分布:")
    growth_stats = df['growth_state'].value_counts()
    print(growth_stats.to_string())
    
    # 通胀维度
    print("\n通胀维度分布:")
    inf_stats = df['inflation_state'].value_counts()
    print(inf_stats.to_string())
    
    # 流动性维度
    print("\n流动性维度分布:")
    liq_stats = df['liquidity_state'].value_counts()
    print(liq_stats.to_string())
    
    # WARNING统计
    print("\n" + "=" * 70)
    print("四、WARNING日志统计")
    print("=" * 70)
    
    warning_records = df[df['warnings'].notna()]
    print(f"\n总WARNING记录数: {len(warning_records)} / {len(df)} ({len(warning_records)/len(df)*100:.1f}%)")
    
    # 解析WARNING类型
    warning_types = {
        '成本传导背离': 0,
        '结构性假衰退': 0,
        '流动性价格否决': 0,
        '社融财政干扰': 0,
    }
    
    for _, row in warning_records.iterrows():
        warnings = str(row['warnings'])
        if '成本传导' in warnings:
            warning_types['成本传导背离'] += 1
        if '服务业对冲' in warnings:
            warning_types['结构性假衰退'] += 1
        if '价格紧' in warnings:
            warning_types['流动性价格否决'] += 1
        if '财政干扰' in warnings:
            warning_types['社融财政干扰'] += 1
    
    print("\n各类型WARNING次数:")
    for wtype, count in warning_types.items():
        print(f"  {wtype}: {count}次")
    
    # 最近12个月的WARNING
    print("\n最近12个月WARNING详情:")
    recent_warnings = warning_records.tail(12)[['date', 'macro_regime', 'warnings']]
    for _, row in recent_warnings.iterrows():
        print(f"  {row['date'].strftime('%Y-%m')}: {row['macro_regime']} - {row['warnings']}")

# ============================================================
# 4. 生成统计报告CSV
# ============================================================

def generate_statistics_csv():
    print("\n" + "=" * 70)
    print("五、生成统计报告")
    print("=" * 70)
    
    # 1. 象限月度统计
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    regime_monthly = df.groupby(['year', 'month', 'macro_regime']).size().reset_index(name='count')
    regime_monthly.columns = ['year', 'month', 'regime', 'count']
    
    # 2. 维度统计
    dimension_stats = []
    for _, row in df.iterrows():
        dimension_stats.append({
            'date': row['date'].strftime('%Y-%m'),
            'growth_state': row['growth_state'],
            'inflation_state': row['inflation_state'],
            'liquidity_state': row['liquidity_state'],
            'macro_regime': row['macro_regime'],
            'has_warning': pd.notna(row['warnings']),
        })
    
    dimension_df = pd.DataFrame(dimension_stats)
    
    # 保存
    output_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\v7_statistics_summary.csv'
    dimension_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"[OK] 已生成统计报告: {output_path}")
    
    # 3. 转换矩阵保存
    _, transition_probs = analyze_transition_matrix()
    matrix_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\v7_transition_matrix.csv'
    transition_probs.to_csv(matrix_path, encoding='utf-8-sig')
    print(f"[OK] 已保存转换矩阵: {matrix_path}")

# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 70)
    print("V7 宏观状态统计分析")
    print("=" * 70)
    
    # 1. 持续时间分析
    duration_df = analyze_regime_duration()
    
    # 2. 转换矩阵
    transition_counts, transition_probs = analyze_transition_matrix()
    
    # 3. 维度统计
    analyze_dimensions()
    
    # 4. 生成报告
    generate_statistics_csv()
    
    print("\n" + "=" * 70)
    print("[DONE] 统计分析完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
