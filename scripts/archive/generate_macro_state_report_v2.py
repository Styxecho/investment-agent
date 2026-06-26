#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
宏观状态诊断引擎 - 完整版
三维度状态判定 + 宏观状态映射 + 置信度计算
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from functools import reduce

engine = create_engine('sqlite:///D:/Study/Project/investment-agent/data_external/db/external_data.db')

TREND_WINDOW = 3
TREND_THRESHOLD = 0.2  # 偏离MA3的阈值

print("="*80)
print("宏观状态诊断引擎 - 完整版")
print("="*80)

# ============================================================================
# Step 1: 读取数据（原始值 + Z-score）
# ============================================================================
print("\n[Step 1] 读取数据...")

# 读取原始值
raw_indicators = {
    'CN_PMI_MFG_M': 'pmi_raw',
    'CN_PPI_YOY_M': 'ppi_raw',
    'CN_CPI_YOY_M': 'cpi_raw',
    'CN_M1_YOY_M': 'm1_raw',
    'CN_M2_YOY_M': 'm2_raw',
    'CN_SFS_YOY_M': 'sfs_raw',
    'CN_IAV_YOY_M': 'iav_raw'
}

raw_data = []
for ind_code, ind_name in raw_indicators.items():
    sql = f"SELECT publish_date, value FROM macro_indicator_value WHERE indicator_code = '{ind_code}' AND publish_date >= '20160101' ORDER BY publish_date"
    df = pd.read_sql(sql, engine)
    df['year_month'] = pd.to_datetime(df['publish_date'].astype(str)).dt.strftime('%Y%m')
    df = df.rename(columns={'value': ind_name})
    raw_data.append(df[['year_month', ind_name]])

raw_df = reduce(lambda left, right: pd.merge(left, right, on='year_month', how='outer'), raw_data)

# 读取Z-score
z_indicators = {
    'CN_PMI_MFG_M': 'pmi_z',
    'CN_PPI_YOY_M': 'ppi_z',
    'CN_CPI_YOY_M': 'cpi_z',
    'CN_M1_YOY_M': 'm1_z',
    'CN_M2_YOY_M': 'm2_z',
    'CN_SFS_YOY_M': 'sfs_z',
    'CN_IAV_YOY_M': 'iav_z'
}

z_data = []
for ind_code, ind_name in z_indicators.items():
    sql = f"SELECT publish_date, factor_value FROM macro_factor_value WHERE indicator_code = '{ind_code}' AND factor_type = 'level' AND publish_date >= '20160101' ORDER BY publish_date"
    df = pd.read_sql(sql, engine)
    df['year_month'] = pd.to_datetime(df['publish_date'].astype(str)).dt.strftime('%Y%m')
    df = df.rename(columns={'factor_value': ind_name})
    z_data.append(df[['year_month', ind_name]])

z_df = reduce(lambda left, right: pd.merge(left, right, on='year_month', how='outer'), z_data)

# 合并
macro_df = pd.merge(raw_df, z_df, on='year_month', how='outer')
macro_df['m1m2_raw'] = macro_df['m1_raw'] - macro_df['m2_raw']
macro_df['m1m2_z'] = macro_df['m1_z'] - macro_df['m2_z']
macro_df = macro_df.sort_values('year_month').reset_index(drop=True)

print(f"数据加载完成: {len(macro_df)} 个月")
print(f"时间范围: {macro_df['year_month'].min()} 至 {macro_df['year_month'].max()}")

# ============================================================================
# Step 2: 趋势计算函数
# ============================================================================
def calc_trend(series, window=3):
    """计算趋势：MA3 + 当前值偏离"""
    if len(series) < window:
        return None, None, None
    ma = series.rolling(window=window).mean()
    ma_current = ma.iloc[-1]
    current = series.iloc[-1]
    return current, ma_current, (current - ma_current) if not pd.isna(ma_current) else None

# ============================================================================
# Step 3: 方向判定函数
# ============================================================================
def judge_direction(current, ma, threshold=TREND_THRESHOLD):
    """基于当前值与MA3偏离判定方向"""
    if current is None or ma is None or pd.isna(current) or pd.isna(ma):
        return 'N/A'
    deviation = current - ma
    if deviation > threshold:
        return '↑'
    elif deviation < -threshold:
        return '↓'
    else:
        return '→'

# ============================================================================
# Step 4: 趋势持续性追踪
# ============================================================================
def track_trend_continuity(directions):
    """
    追踪趋势持续性
    返回：趋势确认月数、当前趋势方向
    """
    if len(directions) == 0 or directions[-1] == 'N/A':
        return 0, 'N/A'
    
    current_dir = directions[-1]
    if current_dir == '→':
        return 0, '→'
    
    count = 0
    for d in reversed(directions):
        if d == current_dir:
            count += 1
        elif d == '→':
            continue  # 平稳月不中断计数
        else:
            break
    
    return count, current_dir

# ============================================================================
# Step 5: 主循环 - 逐月计算
# ============================================================================
print("\n[Step 2] 逐月计算状态...")

results = []

# 存储历史方向用于追踪持续性
hist_directions = {
    'pmi': [], 'iav': [], 'ppi': [], 'cpi': [], 'm1m2': [], 'sfs': []
}

for i in range(2, len(macro_df)):
    month = macro_df.iloc[i]['year_month']
    window_df = macro_df.iloc[max(0, i-2):i+1]
    current_row = macro_df.iloc[i]
    
    # 各指标趋势计算
    pmi_cur, pmi_ma, pmi_dev = calc_trend(window_df['pmi_z'])
    iav_cur, iav_ma, iav_dev = calc_trend(window_df['iav_z'])
    ppi_cur, ppi_ma, ppi_dev = calc_trend(window_df['ppi_z'])
    cpi_cur, cpi_ma, cpi_dev = calc_trend(window_df['cpi_z'])
    m1m2_cur, m1m2_ma, m1m2_dev = calc_trend(window_df['m1m2_z'])
    sfs_cur, sfs_ma, sfs_dev = calc_trend(window_df['sfs_z']) if not window_df['sfs_z'].isna().all() else (None, None, None)
    
    # 方向判定
    pmi_dir = judge_direction(pmi_cur, pmi_ma)
    iav_dir = judge_direction(iav_cur, iav_ma)
    ppi_dir = judge_direction(ppi_cur, ppi_ma)
    cpi_dir = judge_direction(cpi_cur, cpi_ma)
    m1m2_dir = judge_direction(m1m2_cur, m1m2_ma)
    sfs_dir = judge_direction(sfs_cur, sfs_ma) if sfs_cur is not None else 'N/A'
    
    # 更新历史方向
    hist_directions['pmi'].append(pmi_dir)
    hist_directions['iav'].append(iav_dir)
    hist_directions['ppi'].append(ppi_dir)
    hist_directions['cpi'].append(cpi_dir)
    hist_directions['m1m2'].append(m1m2_dir)
    hist_directions['sfs'].append(sfs_dir)
    
    # 趋势持续性
    pmi_count, pmi_confirmed = track_trend_continuity(hist_directions['pmi'])
    iav_count, iav_confirmed = track_trend_continuity(hist_directions['iav'])
    ppi_count, ppi_confirmed = track_trend_continuity(hist_directions['ppi'])
    cpi_count, cpi_confirmed = track_trend_continuity(hist_directions['cpi'])
    m1m2_count, m1m2_confirmed = track_trend_continuity(hist_directions['m1m2'])
    sfs_count, sfs_confirmed = track_trend_continuity(hist_directions['sfs'])
    
    # ============================================================================
    # 维度一：增长
    # ============================================================================
    # PMI趋势确认？
    pmi_trend = '确认' if pmi_count >= 3 else ('形成中' if pmi_count == 2 else '不明')
    iav_trend = '确认' if iav_count >= 3 else ('形成中' if iav_count == 2 else '不明')
    
    # 增长组合（9种）
    growth_combinations = {
        ('↑', '↑'): '扩张加速',
        ('↑', '→'): '预期增长',
        ('↑', '↓'): '增长分歧',
        ('→', '↑'): '弱增长',
        ('→', '→'): '增长平稳',
        ('→', '↓'): '增长承压',
        ('↓', '↑'): '衰退反弹',
        ('↓', '→'): '增长放缓',
        ('↓', '↓'): '收缩加速'
    }
    
    pmi_effective = pmi_confirmed if pmi_trend != '不明' else '→'
    iav_effective = iav_confirmed if iav_trend != '不明' else '→'
    growth_state = growth_combinations.get((pmi_effective, iav_effective), 'uncertain')
    
    # PMI绝对水平
    pmi_level = '荣枯线上' if current_row['pmi_raw'] > 50 else '荣枯线下'
    
    # ============================================================================
    # 维度二：通胀
    # ============================================================================
    # PPI趋势确认？
    ppi_trend = '确认' if ppi_count >= 3 else ('形成中' if ppi_count == 2 else '不明')
    cpi_trend = '确认' if cpi_count >= 3 else ('形成中' if cpi_count == 2 else '不明')
    
    # PPI绝对水平
    ppi_raw = current_row['ppi_raw']
    if pd.notna(ppi_raw):
        if ppi_raw > 5:
            ppi_level = '高位'
        elif ppi_raw > 0:
            ppi_level = '中位'
        elif ppi_raw > -2:
            ppi_level = '低位'
        else:
            ppi_level = '负区间'
    else:
        ppi_level = 'N/A'
    
    # CPI绝对水平
    cpi_raw = current_row['cpi_raw']
    if pd.notna(cpi_raw):
        if cpi_raw > 3:
            cpi_level = '高位'
        elif cpi_raw > 0:
            cpi_level = '中位'
        elif cpi_raw > -1:
            cpi_level = '低位'
        else:
            cpi_level = '负区间'
    else:
        cpi_level = 'N/A'
    
    # 通胀组合（简化版，基于PPI主导）
    ppi_effective = ppi_confirmed if ppi_trend != '不明' else '→'
    cpi_effective = cpi_confirmed if cpi_trend != '不明' else '→'
    
    # 通胀状态判定
    if ppi_effective == '↑' and cpi_effective == '↑':
        inf_state = '全面通胀'
    elif ppi_effective == '↑' and cpi_effective in ['→', 'N/A']:
        inf_state = '成本推动型通胀'
    elif ppi_effective == '↑' and cpi_effective == '↓':
        inf_state = '输入性通胀'
    elif ppi_effective == '→' and cpi_effective == '↑':
        inf_state = '需求拉动型通胀'
    elif ppi_effective == '→' and cpi_effective in ['→', 'N/A']:
        inf_state = '通胀温和'
    elif ppi_effective == '→' and cpi_effective == '↓':
        inf_state = '通缩边缘'
    elif ppi_effective == '↓' and cpi_effective == '↑':
        inf_state = '滞胀后期'
    elif ppi_effective == '↓' and cpi_effective in ['→', 'N/A']:
        inf_state = '通胀回落'
    elif ppi_effective == '↓' and cpi_effective == '↓':
        inf_state = '通缩风险'
    else:
        inf_state = '通胀观望'
    
    # ============================================================================
    # 维度三：流动性
    # ============================================================================
    # M1M2趋势确认？
    m1m2_trend = '确认' if m1m2_count >= 3 else ('形成中' if m1m2_count == 2 else '不明')
    sfs_trend = '确认' if sfs_count >= 3 else ('形成中' if sfs_count == 2 else '不明')
    
    # M1M2绝对水平
    m1m2_raw = current_row['m1m2_raw']
    if pd.notna(m1m2_raw):
        m1m2_level = '货币活化' if m1m2_raw > 0 else '货币沉淀'
    else:
        m1m2_level = 'N/A'
    
    # 流动性组合（9种）
    m1m2_effective = m1m2_confirmed if m1m2_trend != '不明' else '→'
    sfs_effective = sfs_confirmed if sfs_trend != '不明' else '→'
    
    liquidity_combinations = {
        ('↑', '↑'): '双宽',
        ('↑', '→'): '宽货币中性信用',
        ('↑', '↓'): '宽货币紧信用',
        ('→', '↑'): '中性货币宽信用',
        ('→', '→'): '流动性观望',
        ('→', '↓'): '中性货币紧信用',
        ('↓', '↑'): '紧货币宽信用',
        ('↓', '→'): '紧货币中性信用',
        ('↓', '↓'): '双紧'
    }
    
    liq_state = liquidity_combinations.get((m1m2_effective, sfs_effective), '流动性观望')
    
    # ============================================================================
    # 宏观状态映射
    # ============================================================================
    # 各维度归类
    growth_category = '扩张' if growth_state in ['扩张加速', '预期增长', '弱增长', '增长平稳'] else \
                     ('收缩' if growth_state in ['收缩加速', '增长放缓', '增长承压', '衰退反弹'] else '不确定')
    
    inf_category = '高' if inf_state in ['全面通胀', '成本推动型通胀', '输入性通胀', '滞胀后期', '需求拉动型通胀'] else \
                   ('低' if inf_state in ['通胀回落', '通缩风险', '通缩边缘'] else '不确定')
    
    liq_category = '宽松' if liq_state in ['双宽', '宽货币中性信用', '紧货币宽信用', '中性货币宽信用'] else \
                   ('紧缩' if liq_state in ['双紧', '紧货币中性信用', '宽货币紧信用', '中性货币紧信用'] else '不确定')
    
    # 8种核心状态映射
    state_map = {
        ('扩张', '高', '宽松'): '紧过热',
        ('扩张', '高', '紧缩'): '过热期',
        ('扩张', '低', '宽松'): '复苏期',
        ('扩张', '低', '紧缩'): '弱复苏',
        ('收缩', '高', '宽松'): '弱滞胀',
        ('收缩', '高', '紧缩'): '滞胀期',
        ('收缩', '低', '宽松'): '衰退期',
        ('收缩', '低', '紧缩'): '宽衰退'
    }
    
    if growth_category != '不确定' and inf_category != '不确定' and liq_category != '不确定':
        final_state = state_map.get((growth_category, inf_category, liq_category), '过渡态')
    else:
        final_state = '过渡态'
    
    # ============================================================================
    # 置信度计算
    # ============================================================================
    base_conf = 0.85
    adjustments = []
    
    # 维度调整
    if growth_category == '不确定':
        adjustments.append(-0.10)
    if inf_category == '不确定':
        adjustments.append(-0.10)
    if liq_category == '不确定':
        adjustments.append(-0.10)
    
    # 数据缺失调整
    if liq_state == 'unknown' or 'N/A' in [m1m2_level]:
        adjustments.append(-0.15)
    
    # 状态调整
    uncertain_dims = sum([growth_category == '不确定', inf_category == '不确定', liq_category == '不确定'])
    if uncertain_dims == 1 and final_state != '过渡态':
        adjustments.append(-0.05)
    elif uncertain_dims >= 2:
        adjustments.append(-0.20)
    
    confidence = base_conf + sum(adjustments)
    confidence = max(0.30, min(0.95, confidence))
    
    # 存储结果
    results.append({
        'year_month': month,
        'pmi_raw': round(current_row['pmi_raw'], 1) if pd.notna(current_row['pmi_raw']) else None,
        'pmi_z': round(pmi_cur, 2) if pmi_cur else None,
        'pmi_ma3': round(pmi_ma, 2) if pmi_ma else None,
        'pmi_dir': pmi_dir,
        'pmi_trend': pmi_trend,
        'iav_raw': round(current_row['iav_raw'], 1) if pd.notna(current_row['iav_raw']) else None,
        'iav_z': round(iav_cur, 2) if iav_cur else None,
        'iav_ma3': round(iav_ma, 2) if iav_ma else None,
        'iav_dir': iav_dir,
        'iav_trend': iav_trend,
        'growth_state': growth_state,
        'pmi_level': pmi_level,
        'ppi_raw': round(ppi_raw, 1) if pd.notna(ppi_raw) else None,
        'ppi_z': round(ppi_cur, 2) if ppi_cur else None,
        'ppi_ma3': round(ppi_ma, 2) if ppi_ma else None,
        'ppi_dir': ppi_dir,
        'ppi_trend': ppi_trend,
        'ppi_level': ppi_level,
        'cpi_raw': round(cpi_raw, 1) if pd.notna(cpi_raw) else None,
        'cpi_z': round(cpi_cur, 2) if cpi_cur else None,
        'cpi_ma3': round(cpi_ma, 2) if cpi_ma else None,
        'cpi_dir': cpi_dir,
        'cpi_trend': cpi_trend,
        'cpi_level': cpi_level,
        'inf_state': inf_state,
        'm1m2_raw': round(m1m2_raw, 1) if pd.notna(m1m2_raw) else None,
        'm1m2_z': round(m1m2_cur, 2) if m1m2_cur else None,
        'm1m2_ma3': round(m1m2_ma, 2) if m1m2_ma else None,
        'm1m2_dir': m1m2_dir,
        'm1m2_trend': m1m2_trend,
        'm1m2_level': m1m2_level,
        'sfs_raw': round(current_row['sfs_raw'], 1) if pd.notna(current_row['sfs_raw']) else None,
        'sfs_z': round(sfs_cur, 2) if sfs_cur else None,
        'sfs_ma3': round(sfs_ma, 2) if sfs_ma else None,
        'sfs_dir': sfs_dir,
        'sfs_trend': sfs_trend,
        'liq_state': liq_state,
        'final_state': final_state,
        'confidence': f"{confidence:.0%}"
    })

results_df = pd.DataFrame(results)

print(f"计算完成: {len(results_df)} 个月")

# ============================================================================
# Step 6: 生成Markdown宽表报告
# ============================================================================
print("\n[Step 3] 生成报告...")

report_lines = []
report_lines.append("# 宏观状态诊断宽表报告（2016年至今）- 完整版")
report_lines.append("")
report_lines.append("## 方法论说明")
report_lines.append("- **趋势计算**: 3个月移动平均（MA3）")
report_lines.append("- **方向判定**: 当前Z-score vs MA3偏离，阈值±0.2")
report_lines.append("  - ↑: 当前值 > MA3 + 0.2（加速上行）")
report_lines.append("  - ↓: 当前值 < MA3 - 0.2（加速下行）")
report_lines.append("  - →: 偏离在±0.2内（趋势不明）")
report_lines.append("- **趋势持续性**: 连续3个月同向 = 确认，否则 = 趋势不明")
report_lines.append("- **增长维度**: PMI（荣枯线50为界）+ IAV（趋势方向）")
report_lines.append("- **通胀维度**: PPI原始值分层（>5%高位/0-5%中位/-2-0%低位/<-2%负区间）+ 趋势方向")
report_lines.append("- **流动性维度**: M1-M2（0为界，活化/沉淀）+ 社融（趋势方向）")
report_lines.append("- **宏观状态**: 增长×通胀×流动性 → 8种核心状态")
report_lines.append("- **置信度**: 基础0.85 - 维度调整(各-0.10) - 数据调整(-0.15) - 状态调整")
report_lines.append("")
report_lines.append("## 完整历史数据宽表")
report_lines.append("")

# 表头
headers = [
    "月份",
    "PMI原始", "PMI-Z", "PMI-MA3", "PMI方向", "PMI趋势",
    "IAV原始", "IAV-Z", "IAV-MA3", "IAV方向", "IAV趋势", "增长状态",
    "PPI原始", "PPI水平", "PPI-Z", "PPI-MA3", "PPI方向", "PPI趋势",
    "CPI原始", "CPI水平", "CPI-Z", "CPI-MA3", "CPI方向", "CPI趋势", "通胀状态",
    "M1M2原始", "M1M2水平", "M1M2-Z", "M1M2-MA3", "M1M2方向", "M1M2趋势",
    "SFS原始", "SFS-Z", "SFS-MA3", "SFS方向", "SFS趋势", "流动性状态",
    "最终状态", "置信度"
]

report_lines.append("| " + " | ".join(headers) + " |")
report_lines.append("|" + "|".join(["---"] * len(headers)) + "|")

# 数据行
for _, row in results_df.iterrows():
    vals = [
        str(row['year_month']),
        str(row['pmi_raw']) if row['pmi_raw'] else 'N/A',
        str(row['pmi_z']) if row['pmi_z'] else 'N/A',
        str(row['pmi_ma3']) if row['pmi_ma3'] else 'N/A',
        row['pmi_dir'], row['pmi_trend'],
        str(row['iav_raw']) if row['iav_raw'] else 'N/A',
        str(row['iav_z']) if row['iav_z'] else 'N/A',
        str(row['iav_ma3']) if row['iav_ma3'] else 'N/A',
        row['iav_dir'], row['iav_trend'],
        row['growth_state'],
        str(row['ppi_raw']) if row['ppi_raw'] else 'N/A',
        row['ppi_level'],
        str(row['ppi_z']) if row['ppi_z'] else 'N/A',
        str(row['ppi_ma3']) if row['ppi_ma3'] else 'N/A',
        row['ppi_dir'], row['ppi_trend'],
        str(row['cpi_raw']) if row['cpi_raw'] else 'N/A',
        row['cpi_level'],
        str(row['cpi_z']) if row['cpi_z'] else 'N/A',
        str(row['cpi_ma3']) if row['cpi_ma3'] else 'N/A',
        row['cpi_dir'], row['cpi_trend'],
        row['inf_state'],
        str(row['m1m2_raw']) if row['m1m2_raw'] else 'N/A',
        row['m1m2_level'],
        str(row['m1m2_z']) if row['m1m2_z'] else 'N/A',
        str(row['m1m2_ma3']) if row['m1m2_ma3'] else 'N/A',
        row['m1m2_dir'], row['m1m2_trend'],
        str(row['sfs_raw']) if row['sfs_raw'] else 'N/A',
        str(row['sfs_z']) if row['sfs_z'] else 'N/A',
        str(row['sfs_ma3']) if row['sfs_ma3'] else 'N/A',
        row['sfs_dir'], row['sfs_trend'],
        row['liq_state'],
        row['final_state'],
        row['confidence']
    ]
    report_lines.append("| " + " | ".join(vals) + " |")

# 保存报告
report_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_wide_table.md'
with open(report_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report_lines))

print(f"Markdown报告已保存: {report_path}")

# 同时保存CSV
csv_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_wide_table.csv'
results_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f"CSV已保存: {csv_path}")

# 打印前5行预览
print("\n前5个月数据预览:")
print(results_df[['year_month', 'growth_state', 'inf_state', 'liq_state', 'final_state', 'confidence']].head().to_string(index=False))

print("\n" + "="*80)
print("报告生成完成!")
print("="*80)
