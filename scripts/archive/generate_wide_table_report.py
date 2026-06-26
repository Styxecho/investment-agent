#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成宽表格式的宏观状态历史报告
包含2016年至今所有月份的详细推导数据
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

# 读取所有宏观数据
indicators = {
    'CN_PMI_MFG_M': 'pmi',
    'CN_PPI_YOY_M': 'ppi', 
    'CN_CPI_YOY_M': 'cpi',
    'CN_M1_YOY_M': 'm1',
    'CN_M2_YOY_M': 'm2',
    'CN_SFS_YOY_M': 'sfs',
    'CN_IAV_YOY_M': 'iav'
}

macro_data = []
for ind_code, ind_name in indicators.items():
    sql = f"SELECT publish_date, factor_value FROM macro_factor_value WHERE indicator_code = '{ind_code}' AND factor_type = 'level' AND publish_date >= '20160101' ORDER BY publish_date"
    df = pd.read_sql(sql, engine)
    df['year_month'] = pd.to_datetime(df['publish_date'].astype(str)).dt.strftime('%Y%m')
    df = df.rename(columns={'factor_value': ind_name})
    macro_data.append(df[['year_month', ind_name]])

macro_df = reduce(lambda left, right: pd.merge(left, right, on='year_month', how='outer'), macro_data)
macro_df['m1m2'] = macro_df['m1'] - macro_df['m2']
macro_df = macro_df.sort_values('year_month').reset_index(drop=True)

print(f"Data loaded: {len(macro_df)} months from {macro_df['year_month'].min()} to {macro_df['year_month'].max()}")

# 趋势计算函数
def calc_trend(series, window=3):
    if len(series) < window:
        return None, None, None
    ma = series.rolling(window=window).mean()
    ma_current = ma.iloc[-1]
    slope = series.iloc[-1] - series.iloc[-2] if len(series) >= 2 else 0
    return ma_current, slope, series.iloc[-1]

# 存储所有月份的结果
results = []

for i in range(2, len(macro_df)):
    month = macro_df.iloc[i]['year_month']
    window_df = macro_df.iloc[max(0, i-2):i+1]
    
    # 各指标趋势
    pmi_ma, pmi_slope, pmi_raw = calc_trend(window_df['pmi'])
    iav_ma, iav_slope, iav_raw = calc_trend(window_df['iav'])
    ppi_ma, ppi_slope, ppi_raw = calc_trend(window_df['ppi'])
    cpi_ma, cpi_slope, cpi_raw = calc_trend(window_df['cpi'])
    m1m2_ma, m1m2_slope, m1m2_raw = calc_trend(window_df['m1m2'])
    sfs_ma, sfs_slope, sfs_raw = calc_trend(window_df['sfs']) if not window_df['sfs'].isna().all() else (None, None, None)
    
    # 判定函数：基于当前值与MA3的偏离（阈值0.2）
    def judge_dir(current, ma, threshold=0.2):
        if ma is None or current is None or pd.isna(current) or pd.isna(ma):
            return 'N/A'
        deviation = current - ma
        if deviation > threshold:
            return '↑'
        elif deviation < -threshold:
            return '↓'
        else:
            return '→'
    
    # 增长判定（基于当前值与MA3偏离）
    pmi_dir = judge_dir(pmi_raw, pmi_ma)
    iav_dir = judge_dir(iav_raw, iav_ma)
    
    # 增长维度合成逻辑（9种组合）
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
    growth_state = growth_combinations.get((pmi_dir, iav_dir), 'uncertain')
    
    # 通胀判定（基于当前值与MA3偏离）
    ppi_dir = judge_dir(ppi_raw, ppi_ma)
    cpi_dir = judge_dir(cpi_raw, cpi_ma)
    
    if ppi_ma and ppi_ma > 1.0 and cpi_ma and cpi_ma > 0.5:
        inf_state = '全面通胀'
    elif ppi_ma and ppi_ma > 1.0 and cpi_ma and cpi_ma < 0:
        inf_state = '结构性通胀'
    elif ppi_ma and ppi_ma < 0 and cpi_ma and cpi_ma < 0:
        inf_state = '低通胀'
    else:
        inf_state = '通胀温和'
    
    # 流动性判定（基于当前值与MA3偏离）
    m1m2_dir = judge_dir(m1m2_raw, m1m2_ma)
    
    if sfs_ma is not None:
        sfs_dir = judge_dir(sfs_raw, sfs_ma)
        if m1m2_dir == '↑' and sfs_dir == '↑':
            liq_state = '双宽'
        elif m1m2_dir == '↑' and sfs_dir == '↓':
            liq_state = '宽货币紧信用'
        elif m1m2_dir == '↓' and sfs_dir == '↑':
            liq_state = '紧货币宽信用'
        elif m1m2_dir == '↓' and sfs_dir == '↓':
            liq_state = '双紧'
        else:
            liq_state = '结构性宽松' if (m1m2_dir == '↑' or sfs_dir == '↑') else '结构性紧缩'
    else:
        liq_state = 'unknown'
        sfs_dir = 'N/A'
    
    # 最终状态
    growth_up = '扩张' in growth_state
    growth_down = '收缩' in growth_state
    inf_high = '通胀' in inf_state and '低' not in inf_state and '温和' not in inf_state
    inf_low = '低通胀' in inf_state or '通缩' in inf_state or '温和' in inf_state
    liq_loose = '宽' in liq_state and '紧' not in liq_state
    liq_tight = '紧' in liq_state and '宽' not in liq_state
    
    if growth_up and inf_low and liq_loose:
        final_state = '复苏期'
    elif growth_up and inf_low and not liq_loose:
        final_state = '弱复苏'
    elif growth_up and inf_high and liq_tight:
        final_state = '过热期'
    elif growth_up and inf_high and not liq_tight:
        final_state = '紧过热'
    elif growth_down and inf_high and liq_tight:
        final_state = '滞胀期'
    elif growth_down and inf_high and not liq_tight:
        final_state = '弱滞胀'
    elif growth_down and inf_low and liq_loose:
        final_state = '衰退期'
    elif growth_down and inf_low and not liq_loose:
        final_state = '宽衰退'
    else:
        final_state = '过渡态'
    
    # 置信度
    conf = 0.85
    if liq_state == 'unknown':
        conf -= 0.25
    if '分歧' in growth_state or 'uncertain' in growth_state or '承压' in growth_state:
        conf -= 0.15
    if '反弹' in growth_state:
        conf -= 0.10
    
    results.append({
        'year_month': month,
        'pmi_raw': round(pmi_raw, 2) if pmi_raw else None,
        'pmi_ma3': round(pmi_ma, 2) if pmi_ma else None,
        'pmi_dir': pmi_dir,
        'iav_raw': round(iav_raw, 2) if iav_raw else None,
        'iav_ma3': round(iav_ma, 2) if iav_ma else None,
        'iav_dir': iav_dir,
        'growth': growth_state,
        'ppi_raw': round(ppi_raw, 2) if ppi_raw else None,
        'ppi_ma3': round(ppi_ma, 2) if ppi_ma else None,
        'ppi_dir': ppi_dir,
        'cpi_raw': round(cpi_raw, 2) if cpi_raw else None,
        'cpi_ma3': round(cpi_ma, 2) if cpi_ma else None,
        'cpi_dir': cpi_dir,
        'inflation': inf_state,
        'm1m2_raw': round(m1m2_raw, 2) if m1m2_raw else None,
        'm1m2_ma3': round(m1m2_ma, 2) if m1m2_ma else None,
        'm1m2_dir': m1m2_dir,
        'sfs_raw': round(sfs_raw, 2) if sfs_raw else None,
        'sfs_ma3': round(sfs_ma, 2) if sfs_ma else None,
        'sfs_dir': sfs_dir,
        'liquidity': liq_state,
        'final_state': final_state,
        'confidence': f"{conf:.0%}"
    })

results_df = pd.DataFrame(results)

# 生成Markdown宽表报告
report_lines = []
report_lines.append("# 宏观状态诊断宽表报告（2016年至今）")
report_lines.append("")
report_lines.append("## 方法论说明")
report_lines.append("- **趋势计算**：3个月移动平均（MA3）")
report_lines.append("- **方向判定**：MA3 > 0.5 = 扩张/上行(↑)，MA3 < -0.5 = 收缩/下行(↓)，中间 = 平稳(→)")
report_lines.append("- **增长维度**：PMI制造业 + 工业增加值")
report_lines.append("- **通胀维度**：PPI（主导）+ CPI（验证）")
report_lines.append("- **流动性维度**：货币（M1-M2剪刀差）× 信用（社融增速）")
report_lines.append("")
report_lines.append("## 完整历史数据宽表")
report_lines.append("")

# 表头
headers = [
    "月份", "PMI原始", "PMI-MA3", "PMI方向", "IAV原始", "IAV-MA3", "IAV方向", "增长状态",
    "PPI原始", "PPI-MA3", "PPI方向", "CPI原始", "CPI-MA3", "CPI方向", "通胀状态",
    "M1M2原始", "M1M2-MA3", "M1M2方向", "SFS原始", "SFS-MA3", "SFS方向", "流动性状态",
    "最终状态", "置信度"
]

report_lines.append("| " + " | ".join(headers) + " |")
report_lines.append("|" + "|".join(["---"] * len(headers)) + "|")

# 数据行
for _, row in results_df.iterrows():
    vals = [
        str(row['year_month']),
        str(row['pmi_raw']) if row['pmi_raw'] else 'N/A',
        str(row['pmi_ma3']) if row['pmi_ma3'] else 'N/A',
        row['pmi_dir'],
        str(row['iav_raw']) if row['iav_raw'] else 'N/A',
        str(row['iav_ma3']) if row['iav_ma3'] else 'N/A',
        row['iav_dir'],
        row['growth'],
        str(row['ppi_raw']) if row['ppi_raw'] else 'N/A',
        str(row['ppi_ma3']) if row['ppi_ma3'] else 'N/A',
        row['ppi_dir'],
        str(row['cpi_raw']) if row['cpi_raw'] else 'N/A',
        str(row['cpi_ma3']) if row['cpi_ma3'] else 'N/A',
        row['cpi_dir'],
        row['inflation'],
        str(row['m1m2_raw']) if row['m1m2_raw'] else 'N/A',
        str(row['m1m2_ma3']) if row['m1m2_ma3'] else 'N/A',
        row['m1m2_dir'],
        str(row['sfs_raw']) if row['sfs_raw'] else 'N/A',
        str(row['sfs_ma3']) if row['sfs_ma3'] else 'N/A',
        row['sfs_dir'],
        row['liquidity'],
        row['final_state'],
        row['confidence']
    ]
    report_lines.append("| " + " | ".join(vals) + " |")

# 保存报告
report_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_wide_table.md'
with open(report_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report_lines))

print(f"\nReport saved: {report_path}")
print(f"Total months: {len(results_df)}")
print(f"Period: {results_df['year_month'].min()} to {results_df['year_month'].max()}")

# 同时保存CSV方便Excel查看
csv_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_wide_table.csv'
results_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f"CSV saved: {csv_path}")
