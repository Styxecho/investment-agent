#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
宏观状态诊断引擎 - V3 改进版
改进内容：
1. 水平与趋势分离
2. 趋势持续性保护（连续2期才翻转）
3. 增长状态简化为4种 + 分歧
4. 通胀状态简化
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from functools import reduce

engine = create_engine('sqlite:///D:/Study/Project/investment-agent/data_external/db/external_data.db')

TREND_THRESHOLD = 0.2  # Z-score偏离MA3的阈值
REVERSE_CONFIRM = 2    # 趋势翻转需要连续2期

print("="*80)
print("宏观状态诊断引擎 - V3 改进版")
print("="*80)

# ============================================================================
# Step 1: 读取数据
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

# 读取IAV HP_Cycle
cycle_df = pd.read_csv('D:/Study/Project/investment-agent/docs/research/macro_analysis/macro_factors_detailed.csv')
cycle_df = cycle_df[cycle_df['Indicator'] == 'CN_IAV_YOY_M'][['Date', 'HP_Cycle']].copy()
cycle_df['year_month'] = pd.to_datetime(cycle_df['Date']).dt.strftime('%Y%m')
cycle_df = cycle_df.rename(columns={'HP_Cycle': 'iav_cycle'})
cycle_df = cycle_df[['year_month', 'iav_cycle']]

# 合并
macro_df = pd.merge(raw_df, z_df, on='year_month', how='outer')
macro_df = pd.merge(macro_df, cycle_df, on='year_month', how='outer')
macro_df['m1m2_raw'] = macro_df['m1_raw'] - macro_df['m2_raw']
macro_df['m1m2_z'] = macro_df['m1_z'] - macro_df['m2_z']
macro_df = macro_df.sort_values('year_month').reset_index(drop=True)

print(f"数据加载完成: {len(macro_df)} 个月")
print(f"时间范围: {macro_df['year_month'].min()} 至 {macro_df['year_month'].max()}")

# ============================================================================
# Step 2: 水平判定函数
# ============================================================================
def judge_level_pmi(raw_value):
    """PMI水平：基于原始值"""
    if pd.isna(raw_value):
        return 'N/A'
    return '扩张' if raw_value >= 50 else '收缩'

def judge_level_iav(cycle_value):
    """IAV水平：基于HP_Cycle"""
    if pd.isna(cycle_value):
        return 'N/A'
    return '扩张' if cycle_value >= 0 else '收缩'

def judge_level_combined(pmi_level, iav_level):
    """增长水平合成"""
    if pmi_level == 'N/A' or iav_level == 'N/A':
        return '不明'
    if pmi_level == iav_level:
        return pmi_level
    return '分歧'

# ============================================================================
# Step 3: 趋势判定函数（带持续性保护）
# ============================================================================
def judge_raw_direction(current, ma, threshold=TREND_THRESHOLD):
    """基于当前值与MA3偏离判定原始方向"""
    if current is None or ma is None or pd.isna(current) or pd.isna(ma):
        return '→'
    deviation = current - ma
    if deviation > threshold:
        return '↑'
    elif deviation < -threshold:
        return '↓'
    else:
        return '→'

class TrendTracker:
    """趋势追踪器：带持续性保护"""
    def __init__(self):
        self.confirmed_dir = '→'
        self.reverse_count = 0
        self.last_raw_dir = '→'
    
    def update(self, raw_dir):
        """更新趋势"""
        if raw_dir == '→':
            # 平稳月：继承上期确认趋势，不重置
            pass
        elif raw_dir == self.confirmed_dir:
            # 同向：重置反转计数
            self.reverse_count = 0
        else:
            # 反向：计数
            self.reverse_count += 1
            if self.reverse_count >= REVERSE_CONFIRM:
                # 连续REVERSE_CONFIRM期反向，翻转趋势
                self.confirmed_dir = raw_dir
                self.reverse_count = 0
        
        self.last_raw_dir = raw_dir
        return self.confirmed_dir
    
    def get_trend_status(self):
        """获取趋势状态"""
        if self.reverse_count == 0 and self.last_raw_dir == self.confirmed_dir and self.confirmed_dir != '→':
            return '确认'
        elif self.reverse_count > 0:
            return '翻转中'
        else:
            return '不明'

def calc_ma3(series):
    """计算MA3"""
    if len(series) < 3:
        return None
    return series.rolling(window=3).mean().iloc[-1]

# ============================================================================
# Step 4: 主循环
# ============================================================================
print("\n[Step 2] 逐月计算状态...")

results = []

# 初始化趋势追踪器
trackers = {
    'pmi': TrendTracker(),
    'iav': TrendTracker(),
    'ppi': TrendTracker(),
    'cpi': TrendTracker(),
    'm1m2': TrendTracker(),
    'sfs': TrendTracker()
}

for i in range(2, len(macro_df)):
    month = macro_df.iloc[i]['year_month']
    current_row = macro_df.iloc[i]
    
    # 计算MA3
    window_df = macro_df.iloc[max(0, i-2):i+1]
    pmi_ma3 = calc_ma3(window_df['pmi_z'])
    iav_ma3 = calc_ma3(window_df['iav_z'])
    ppi_ma3 = calc_ma3(window_df['ppi_z'])
    cpi_ma3 = calc_ma3(window_df['cpi_z'])
    m1m2_ma3 = calc_ma3(window_df['m1m2_z'])
    sfs_ma3 = calc_ma3(window_df['sfs_z'])
    
    # ============================================================================
    # 维度一：增长
    # ============================================================================
    # 水平判定
    pmi_level = judge_level_pmi(current_row['pmi_raw'])
    iav_level = judge_level_iav(current_row['iav_cycle'])
    growth_level = judge_level_combined(pmi_level, iav_level)
    
    # 趋势判定
    pmi_raw_dir = judge_raw_direction(current_row['pmi_z'], pmi_ma3)
    iav_raw_dir = judge_raw_direction(current_row['iav_z'], iav_ma3)
    
    pmi_trend_dir = trackers['pmi'].update(pmi_raw_dir)
    iav_trend_dir = trackers['iav'].update(iav_raw_dir)
    
    # 增长状态映射（4种 + 分歧）
    if growth_level == '分歧':
        growth_state = '分歧'
    elif growth_level == '不明':
        growth_state = '不明'
    elif growth_level == '扩张':
        if pmi_trend_dir == '↑' or iav_trend_dir == '↑':
            growth_state = '扩张加速'
        elif pmi_trend_dir == '↓' or iav_trend_dir == '↓':
            growth_state = '扩张减速'
        else:
            growth_state = '扩张减速' if (current_row['pmi_z'] < 0 if not pd.isna(current_row['pmi_z']) else False) else '扩张加速'
    else:  # 收缩
        if pmi_trend_dir == '↑' or iav_trend_dir == '↑':
            growth_state = '收缩减速'
        elif pmi_trend_dir == '↓' or iav_trend_dir == '↓':
            growth_state = '收缩加速'
        else:
            growth_state = '收缩减速' if (current_row['pmi_z'] > 0 if not pd.isna(current_row['pmi_z']) else False) else '收缩加速'
    
    # ============================================================================
    # 维度二：通胀（简化版）
    # ============================================================================
    # 水平判定（基于PPI原始值）
    ppi_raw = current_row['ppi_raw']
    if pd.isna(ppi_raw):
        inf_level = '不明'
    elif ppi_raw > 3:
        inf_level = '高通胀'
    elif ppi_raw > 0:
        inf_level = '温和通胀'
    else:
        inf_level = '低通胀'
    
    # 趋势判定
    ppi_raw_dir = judge_raw_direction(current_row['ppi_z'], ppi_ma3)
    cpi_raw_dir = judge_raw_direction(current_row['cpi_z'], cpi_ma3)
    
    ppi_trend_dir = trackers['ppi'].update(ppi_raw_dir)
    cpi_trend_dir = trackers['cpi'].update(cpi_raw_dir)
    
    # 通胀状态（简化：水平 × 趋势）
    # 趋势以PPI为主，CPI为辅
    if ppi_trend_dir == '↑' or (ppi_trend_dir == '→' and cpi_trend_dir == '↑'):
        inf_trend = '上行'
    elif ppi_trend_dir == '↓' or (ppi_trend_dir == '→' and cpi_trend_dir == '↓'):
        inf_trend = '下行'
    else:
        inf_trend = '不明'
    
    inf_state_map = {
        ('高通胀', '上行'): '高通胀上行',
        ('高通胀', '下行'): '高通胀下行',
        ('高通胀', '不明'): '高通胀',
        ('温和通胀', '上行'): '温和通胀上行',
        ('温和通胀', '下行'): '温和通胀下行',
        ('温和通胀', '不明'): '温和通胀',
        ('低通胀', '上行'): '低通胀上行',
        ('低通胀', '下行'): '低通胀下行',
        ('低通胀', '不明'): '低通胀',
        ('不明', '上行'): '通胀上行',
        ('不明', '下行'): '通胀下行',
        ('不明', '不明'): '不明'
    }
    inf_state = inf_state_map.get((inf_level, inf_trend), '不明')
    
    # ============================================================================
    # 维度三：流动性（保持原有逻辑）
    # ============================================================================
    m1m2_raw = current_row['m1m2_raw']
    m1m2_level = '货币活化' if pd.notna(m1m2_raw) and m1m2_raw > 0 else ('货币沉淀' if pd.notna(m1m2_raw) else 'N/A')
    
    m1m2_raw_dir = judge_raw_direction(current_row['m1m2_z'], m1m2_ma3)
    sfs_raw_dir = judge_raw_direction(current_row['sfs_z'], sfs_ma3) if sfs_ma3 is not None else '→'
    
    m1m2_trend_dir = trackers['m1m2'].update(m1m2_raw_dir)
    sfs_trend_dir = trackers['sfs'].update(sfs_raw_dir)
    
    # 保持原有9种流动性状态
    m1m2_effective = m1m2_trend_dir
    sfs_effective = sfs_trend_dir
    
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
    # 宏观状态映射（简化版）
    # ============================================================================
    # 增长归类
    if growth_state in ['扩张加速', '扩张减速']:
        growth_category = '扩张'
    elif growth_state in ['收缩减速', '收缩加速']:
        growth_category = '收缩'
    elif growth_state == '分歧':
        growth_category = '分歧'
    else:
        growth_category = '不明'
    
    # 通胀归类
    if inf_level in ['高通胀', '温和通胀']:
        inf_category = '高'
    elif inf_level == '低通胀':
        inf_category = '低'
    else:
        inf_category = '不明'
    
    # 流动性归类
    liq_category = '宽松' if liq_state in ['双宽', '宽货币中性信用', '紧货币宽信用', '中性货币宽信用'] else \
                   ('紧缩' if liq_state in ['双紧', '紧货币中性信用', '宽货币紧信用', '中性货币紧信用'] else '不明')
    
    # 8种核心状态映射（扩展以处理分歧）
    state_map = {
        ('扩张', '高', '宽松'): '紧过热',
        ('扩张', '高', '紧缩'): '过热期',
        ('扩张', '低', '宽松'): '复苏期',
        ('扩张', '低', '紧缩'): '弱复苏',
        ('收缩', '高', '宽松'): '弱滞胀',
        ('收缩', '高', '紧缩'): '滞胀期',
        ('收缩', '低', '宽松'): '衰退期',
        ('收缩', '低', '紧缩'): '宽衰退',
        ('分歧', '高', '宽松'): '过热分歧',
        ('分歧', '高', '紧缩'): '滞胀分歧',
        ('分歧', '低', '宽松'): '复苏分歧',
        ('分歧', '低', '紧缩'): '衰退分歧',
    }
    
    if growth_category != '不明' and inf_category != '不明' and liq_category != '不明':
        final_state = state_map.get((growth_category, inf_category, liq_category), '过渡态')
    else:
        final_state = '过渡态'
    
    # ============================================================================
    # 置信度计算
    # ============================================================================
    base_conf = 0.85
    adjustments = []
    
    # 维度调整
    if growth_category == '分歧':
        adjustments.append(-0.10)
    elif growth_category == '不明':
        adjustments.append(-0.15)
    
    if inf_category == '不明':
        adjustments.append(-0.10)
    
    if liq_category == '不明':
        adjustments.append(-0.10)
    
    # 数据缺失调整
    if pd.isna(current_row['sfs_z']):
        adjustments.append(-0.10)
    
    confidence = base_conf + sum(adjustments)
    confidence = max(0.30, min(0.95, confidence))
    
    # 存储结果
    results.append({
        'year_month': month,
        # PMI
        'pmi_raw': round(current_row['pmi_raw'], 1) if pd.notna(current_row['pmi_raw']) else None,
        'pmi_level': pmi_level,
        'pmi_z': round(current_row['pmi_z'], 2) if pd.notna(current_row['pmi_z']) else None,
        'pmi_ma3': round(pmi_ma3, 2) if pmi_ma3 else None,
        'pmi_raw_dir': pmi_raw_dir,
        'pmi_trend_dir': pmi_trend_dir,
        # IAV
        'iav_raw': round(current_row['iav_raw'], 1) if pd.notna(current_row['iav_raw']) else None,
        'iav_cycle': round(current_row['iav_cycle'], 2) if pd.notna(current_row['iav_cycle']) else None,
        'iav_level': iav_level,
        'iav_z': round(current_row['iav_z'], 2) if pd.notna(current_row['iav_z']) else None,
        'iav_ma3': round(iav_ma3, 2) if iav_ma3 else None,
        'iav_raw_dir': iav_raw_dir,
        'iav_trend_dir': iav_trend_dir,
        # 增长
        'growth_level': growth_level,
        'growth_state': growth_state,
        # PPI
        'ppi_raw': round(ppi_raw, 1) if pd.notna(ppi_raw) else None,
        'ppi_z': round(current_row['ppi_z'], 2) if pd.notna(current_row['ppi_z']) else None,
        'ppi_trend_dir': ppi_trend_dir,
        # CPI
        'cpi_raw': round(current_row['cpi_raw'], 1) if pd.notna(current_row['cpi_raw']) else None,
        'cpi_z': round(current_row['cpi_z'], 2) if pd.notna(current_row['cpi_z']) else None,
        'cpi_trend_dir': cpi_trend_dir,
        # 通胀
        'inf_level': inf_level,
        'inf_state': inf_state,
        # 流动性
        'm1m2_raw': round(m1m2_raw, 1) if pd.notna(m1m2_raw) else None,
        'm1m2_level': m1m2_level,
        'm1m2_trend_dir': m1m2_trend_dir,
        'sfs_raw': round(current_row['sfs_raw'], 1) if pd.notna(current_row['sfs_raw']) else None,
        'sfs_trend_dir': sfs_trend_dir,
        'liq_state': liq_state,
        # 最终
        'final_state': final_state,
        'confidence': f"{int(confidence*100)}%"
    })

results_df = pd.DataFrame(results)

print(f"计算完成: {len(results_df)} 个月")

# ============================================================================
# Step 5: 生成报告
# ============================================================================
print("\n[Step 3] 生成报告...")

# Markdown报告
report_lines = [
    "# 宏观状态诊断宽表报告 V3（改进版）",
    "",
    "## 方法论改进说明",
    "- **水平判定（Position）**:",
    "  - PMI：原始值 ≥ 50 = 扩张，< 50 = 收缩",
    "  - IAV：HP滤波周期值 ≥ 0 = 扩张，< 0 = 收缩",
    "- **趋势判定（Trend）**:",
    "  - 基于Z-score vs MA3偏离，阈值±0.2",
    "  - ↑: 当前值 > MA3 + 0.2（加速）",
    "  - ↓: 当前值 < MA3 - 0.2（减速）",
    "  - →: 偏离在±0.2内（平稳）",
    "- **趋势持续性保护**:",
    "  - 平稳月（→）不中断当前趋势",
    "  - 反向需连续2期才翻转趋势",
    "- **增长状态**:",
    "  - 水平 × 趋势 = 4种核心状态 + 分歧",
    "  - 扩张期 + 加速 = 扩张加速",
    "  - 扩张期 + 减速 = 扩张减速",
    "  - 收缩期 + 加速 = 收缩加速",
    "  - 收缩期 + 减速 = 收缩减速",
    "  - PMI与IAV不一致 = 分歧",
    "- **通胀状态（简化）**:",
    "  - 水平：PPI > 3%高通胀 / 0-3%温和通胀 / ≤ 0%低通胀",
    "  - 趋势：PPI-Z vs MA3 + 持续性保护",
    "  - 状态：高通胀上行/下行、温和通胀上行/下行、低通胀上行/下行",
    "- **流动性状态**：保持原有9种状态",
    "- **宏观状态**：增长 × 通胀 × 流动性 → 8种核心状态 + 分歧变体",
    "",
    "## 完整历史数据宽表",
    ""
]

# 表头
headers = [
    '月份', 'PMI原始', 'PMI水平', 'PMI-Z', 'PMI-MA3', 'PMI原始方向', 'PMI趋势',
    'IAV原始', 'IAV周期', 'IAV水平', 'IAV-Z', 'IAV-MA3', 'IAV原始方向', 'IAV趋势',
    '增长水平', '增长状态',
    'PPI原始', 'PPI-Z', 'PPI趋势', 'CPI原始', 'CPI-Z', 'CPI趋势', '通胀水平', '通胀状态',
    'M1M2原始', 'M1M2水平', 'M1M2趋势', '社融原始', '社融趋势', '流动性状态',
    '最终状态', '置信度'
]

report_lines.append('| ' + ' | '.join(headers) + ' |')
report_lines.append('|' + '|'.join(['---'] * len(headers)) + '|')

# 数据行
for _, row in results_df.iterrows():
    vals = [
        row['year_month'],
        row['pmi_raw'] if row['pmi_raw'] else 'N/A',
        row['pmi_level'],
        row['pmi_z'] if row['pmi_z'] else 'N/A',
        row['pmi_ma3'] if row['pmi_ma3'] else 'N/A',
        row['pmi_raw_dir'],
        row['pmi_trend_dir'],
        row['iav_raw'] if row['iav_raw'] else 'N/A',
        row['iav_cycle'] if row['iav_cycle'] else 'N/A',
        row['iav_level'],
        row['iav_z'] if row['iav_z'] else 'N/A',
        row['iav_ma3'] if row['iav_ma3'] else 'N/A',
        row['iav_raw_dir'],
        row['iav_trend_dir'],
        row['growth_level'],
        row['growth_state'],
        row['ppi_raw'] if row['ppi_raw'] else 'N/A',
        row['ppi_z'] if row['ppi_z'] else 'N/A',
        row['ppi_trend_dir'],
        row['cpi_raw'] if row['cpi_raw'] else 'N/A',
        row['cpi_z'] if row['cpi_z'] else 'N/A',
        row['cpi_trend_dir'],
        row['inf_level'],
        row['inf_state'],
        row['m1m2_raw'] if row['m1m2_raw'] else 'N/A',
        row['m1m2_level'],
        row['m1m2_trend_dir'],
        row['sfs_raw'] if row['sfs_raw'] else 'N/A',
        row['sfs_trend_dir'],
        row['liq_state'],
        row['final_state'],
        row['confidence']
    ]
    report_lines.append('| ' + ' | '.join([str(v) for v in vals]) + ' |')

# 保存Markdown
md_path = 'D:/Study/Project/investment-agent/docs/research/macro_analysis/macro_state_v3.md'
with open(md_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report_lines))

print(f"Markdown报告已保存: {md_path}")

# 保存CSV
csv_path = 'D:/Study/Project/investment-agent/docs/research/macro_analysis/macro_state_v3.csv'
results_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f"CSV已保存: {csv_path}")

# 打印样本
print("\n前10个月数据预览:")
print(results_df[['year_month', 'pmi_level', 'iav_level', 'growth_level', 'growth_state', 
                   'inf_level', 'inf_state', 'liq_state', 'final_state', 'confidence']].head(10).to_string(index=False))

print("\n201805-201910增长状态对比:")
sample = results_df[(results_df['year_month'] >= '201805') & (results_df['year_month'] <= '201910')]
print(sample[['year_month', 'pmi_raw', 'pmi_level', 'iav_cycle', 'iav_level', 'growth_level', 
              'pmi_trend_dir', 'iav_trend_dir', 'growth_state', 'final_state']].to_string(index=False))

print("\n" + "="*80)
print("报告生成完成!")
print("="*80)
