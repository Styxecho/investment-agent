#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
行业轮动卫星策略 - ETF映射引擎 (TIE方法)
目标: 建立申万一级行业 → 可交易ETF的定量映射表
输出: 更新 etf_universe.csv 的 pool_role 字段，生成 industry_etf_mapping.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ==================== 配置 ====================
COMPONENTS_DIR = Path('data_external/reference/index_components')
ETF_UNIVERSE_PATH = Path('data_external/reference/etf_universe.csv')
OUTPUT_DIR = Path('docs/research/industry_rotation')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# TIE分级阈值
TIE_THRESHOLD_CORE = 0.50       # TIE ≥ 50%
PURITY_GAP_CORE = 0.10          # 纯度差 ≥ 10%
TIE_THRESHOLD_BACKUP = 0.30     # TIE ≥ 30%

# ==================== Step 1: 读取申万行业成分股 ====================
print("="*60)
print("Step 1: 读取申万一级行业成分股")
print("="*60)

sw_files = sorted([f for f in COMPONENTS_DIR.glob('sw_*.xls')])
print(f"申万行业文件数量: {len(sw_files)}")

# 建立: 股票代码 -> 申万一级行业代码 的映射
stock_to_sw = {}
sw_industries = {}

for f in sw_files:
    sw_code = f.name.replace('sw_', '').replace('.xls', '')
    df = pd.read_excel(f, dtype=str)
    
    # 列名映射（使用列索引，避免编码问题）
    # 列顺序: 0=日期, 1=指数代码, 2=指数名称, 3=成分股代码, 4=成分股简称, 5=权重%
    code_col_idx = 3  # 成分股代码
    name_col_idx = 2  # 指数名称
    
    if len(df.columns) <= code_col_idx:
        print(f"  警告: {f.name} 列数不足，跳过")
        continue
    
    stocks = df.iloc[:, code_col_idx].astype(str).str.strip().tolist()
    # 行业名称：优先用第2列(指数名称)，如果没有则用文件名
    if len(df.columns) > name_col_idx:
        industry_name = str(df.iloc[:, name_col_idx].iloc[0])
    else:
        industry_name = sw_code
    
    sw_industries[sw_code] = {
        'name': industry_name,
        'stock_count': len(stocks),
        'stocks': set(stocks)
    }
    
    for stock in stocks:
        stock_to_sw[stock] = sw_code

print(f"  成功读取 {len(sw_industries)} 个申万行业")
print(f"  总成分股数量: {len(stock_to_sw)}")
print(f"  申万行业列表:")
for code, info in sorted(sw_industries.items()):
    print(f"    {code}: {info['name']} ({info['stock_count']}只)")

# ==================== Step 2: 读取ETF列表 ====================
print("\n" + "="*60)
print("Step 2: 读取行业主题ETF列表")
print("="*60)

df_etf = pd.read_csv(ETF_UNIVERSE_PATH, encoding='utf-8-sig')
industry_etfs = df_etf[df_etf['asset_class_l2'] == '行业主题'].copy()

# 排除跨境ETF（港股、美股等）
a_share_etfs = industry_etfs[
    ~industry_etfs['index_code'].astype(str).str.contains(r'\.(HK|NQI|GI)$', regex=True, na=False)
].copy()

print(f"行业主题ETF总数: {len(industry_etfs)}")
print(f"A股行业主题ETF: {len(a_share_etfs)} (排除跨境ETF)")

# ==================== Step 3: 读取ETF跟踪指数成分股权重 ====================
print("\n" + "="*60)
print("Step 3: 读取ETF跟踪指数成分股权重")
print("="*60)

# 建立 index_code -> 文件名 映射
idx_file_map = {}
for f in COMPONENTS_DIR.glob('*'):
    if f.name.startswith('sw_') or f.name.startswith('000985'):
        continue
    parts = f.name.split('_')
    if len(parts) >= 1:
        idx_code = parts[0]
        idx_file_map[idx_code] = f

print(f"指数权重文件数量: {len(idx_file_map)}")

# 为每只A股ETF读取成分股权重
etf_components = {}
missing_files = []

for _, etf in a_share_etfs.iterrows():
    etf_code = etf['code']
    idx_code = str(etf['index_code'])
    base_code = idx_code.split('.')[0] if '.' in idx_code else idx_code
    
    if base_code not in idx_file_map:
        missing_files.append((etf_code, idx_code, etf['name']))
        continue
    
    file_path = idx_file_map[base_code]
    try:
        df_comp = pd.read_excel(file_path, dtype=str)
        
        # 找到成分券代码和权重列
        # 支持多种列名格式（Wind导出格式或.xlsx中文格式）
        code_col = None
        weight_col = None
        
        for col in df_comp.columns:
            col_str = str(col).lower()
            # 代码列：可能包含 "code", "代码", "成分券代码"
            if any(kw in col_str for kw in ['constituent code', '成分券代码', '成分股代码', 'stock code', '证券代码']):
                code_col = col
            # 权重列：可能包含 "weight", "权重"
            if any(kw in col_str for kw in ['weight', '权重']):
                weight_col = col
        
        if code_col is None or weight_col is None:
            # 尝试按位置找（常见格式：第1列=日期, 第2列=代码, 第6列=权重）
            if len(df_comp.columns) >= 6:
                # 猜测第2列是代码，最后1列是权重
                code_col = df_comp.columns[1]  # 通常是第2列（索引1）
                weight_col = df_comp.columns[-1]  # 最后1列
                print(f"  提示: {file_path.name} 按位置推断列: code={code_col}, weight={weight_col}")
            else:
                print(f"  警告: {file_path.name} 无法识别代码/权重列（共{len(df_comp.columns)}列: {list(df_comp.columns)}），跳过")
                continue
        
        # 清洗数据
        df_comp = df_comp[[code_col, weight_col]].copy()
        df_comp.columns = ['stock_code', 'weight']
        df_comp['stock_code'] = df_comp['stock_code'].astype(str).str.strip().str.zfill(6)
        df_comp['weight'] = pd.to_numeric(df_comp['weight'], errors='coerce')
        df_comp = df_comp.dropna()
        
        # 权重归一化为百分比
        if df_comp['weight'].max() < 1.0:
            # 已经是小数形式（如0.05）
            pass
        elif df_comp['weight'].max() > 50:
            # 已经是百分比形式（如5.0）
            df_comp['weight'] = df_comp['weight'] / 100.0
        else:
            # 可能是百分比但小于50，统一除100
            df_comp['weight'] = df_comp['weight'] / 100.0
        
        etf_components[etf_code] = {
            'index_code': idx_code,
            'name': etf['name'],
            'file': file_path.name,
            'components': df_comp
        }
        
    except Exception as e:
        print(f"  错误: 读取 {file_path.name} 失败: {e}")
        missing_files.append((etf_code, idx_code, etf['name']))

print(f"  成功读取成分股权重的ETF: {len(etf_components)}")
if missing_files:
    print(f"  缺失成分股权重文件的ETF: {len(missing_files)}")
    for code, idx, name in missing_files[:10]:
        print(f"    {code} ({name}): {idx}")

# ==================== Step 4: 计算TIE (目标行业暴露度) ====================
print("\n" + "="*60)
print("Step 4: 计算TIE (目标行业暴露度)")
print("="*60)

tie_results = []

for etf_code, info in etf_components.items():
    df_comp = info['components']
    
    # 计算该ETF在每个申万行业中的暴露度
    sw_exposure = {}
    for sw_code in sw_industries:
        # 找出属于该行业的成分股
        industry_stocks = sw_industries[sw_code]['stocks']
        matched = df_comp[df_comp['stock_code'].isin(industry_stocks)]
        
        if len(matched) > 0:
            exposure = matched['weight'].sum()
            sw_exposure[sw_code] = exposure
    
    if not sw_exposure:
        # 无匹配，可能是指数成分股全是港股/美股等
        continue
    
    # 排序，找出TIE最高的行业
    sorted_exposure = sorted(sw_exposure.items(), key=lambda x: x[1], reverse=True)
    primary_sw = sorted_exposure[0][0]
    primary_tie = sorted_exposure[0][1]
    
    # 计算纯度差
    if len(sorted_exposure) > 1:
        secondary_tie = sorted_exposure[1][1]
        purity_gap = primary_tie - secondary_tie
    else:
        secondary_tie = 0.0
        purity_gap = primary_tie
    
    # 分级
    if primary_tie >= TIE_THRESHOLD_CORE and purity_gap >= PURITY_GAP_CORE:
        tier = 'industry_rotation_core'
    elif primary_tie >= TIE_THRESHOLD_BACKUP:
        tier = 'industry_rotation_backup'
    else:
        tier = 'unmapped'
    
    tie_results.append({
        'etf_code': etf_code,
        'etf_name': info['name'],
        'index_code': info['index_code'],
        'primary_sw_code': primary_sw,
        'primary_sw_name': sw_industries.get(primary_sw, {}).get('name', primary_sw),
        'primary_tie': primary_tie,
        'secondary_tie': secondary_tie,
        'purity_gap': purity_gap,
        'tier': tier,
        'total_matched_weight': sum(sw_exposure.values()),
        'num_industries': len(sw_exposure)
    })

df_tie = pd.DataFrame(tie_results)
print(f"计算完成，共 {len(df_tie)} 只ETF有有效TIE")

# 统计分级
print("\n分级统计:")
tier_counts = df_tie['tier'].value_counts()
for tier, count in tier_counts.items():
    print(f"  {tier}: {count}只")

# 显示core池
print("\nCore池 (TIE≥50% & 纯度差≥10%):")
core_etfs = df_tie[df_tie['tier'] == 'industry_rotation_core'].sort_values('primary_tie', ascending=False)
for _, row in core_etfs.iterrows():
    print(f"  {row['etf_code']} {row['etf_name']} -> {row['primary_sw_name']} (TIE={row['primary_tie']:.1%}, 纯度差={row['purity_gap']:.1%})")

# 显示backup池
print("\nBackup池 (30%≤TIE<50% 或 纯度差<10%):")
backup_etfs = df_tie[df_tie['tier'] == 'industry_rotation_backup'].sort_values('primary_tie', ascending=False)
for _, row in backup_etfs.head(20).iterrows():
    print(f"  {row['etf_code']} {row['etf_name']} -> {row['primary_sw_name']} (TIE={row['primary_tie']:.1%}, 纯度差={row['purity_gap']:.1%})")

# ==================== Step 5: 行业覆盖度检查 ====================
print("\n" + "="*60)
print("Step 5: 行业覆盖度检查")
print("="*60)

covered_sw = set(df_tie[df_tie['tier'].isin(['industry_rotation_core', 'industry_rotation_backup'])]['primary_sw_code'].unique())
all_sw = set(sw_industries.keys())
uncovered = all_sw - covered_sw

print(f"31个申万一级行业中:")
print(f"  有映射的行业: {len(covered_sw)}")
print(f"  无映射的行业: {len(uncovered)}")

if uncovered:
    print("\n  无映射的行业:")
    for sw_code in sorted(uncovered):
        print(f"    {sw_code}: {sw_industries[sw_code]['name']}")

# ==================== Step 6: 流动性筛选 (同一行业多只ETF时选成交额最大的) ====================
print("\n" + "="*60)
print("Step 6: 流动性筛选")
print("="*60)

# 读取 daily_turnover
df_etf_with_turnover = df_etf[['code', 'daily_turnover']].copy()
df_etf_with_turnover['daily_turnover'] = pd.to_numeric(df_etf_with_turnover['daily_turnover'], errors='coerce')

# 合并TIE结果与成交额
df_tie = df_tie.merge(df_etf_with_turnover, left_on='etf_code', right_on='code', how='left')

# 对每个行业，如果有多个core，标记成交额最大的为首选
industry_mapping = []
for sw_code in sorted(covered_sw):
    sw_name = sw_industries[sw_code]['name']
    
    # 该行业的所有core和backup
    sw_etfs = df_tie[df_tie['primary_sw_code'] == sw_code].sort_values('primary_tie', ascending=False)
    
    core_candidates = sw_etfs[sw_etfs['tier'] == 'industry_rotation_core']
    backup_candidates = sw_etfs[sw_etfs['tier'] == 'industry_rotation_backup']
    
    if len(core_candidates) > 0:
        # 选成交额最大的作为首选
        primary_etf = core_candidates.sort_values('daily_turnover', ascending=False).iloc[0]
        backup_etfs = core_candidates[core_candidates['etf_code'] != primary_etf['etf_code']]
        
        industry_mapping.append({
            'sw_code': sw_code,
            'sw_name': sw_name,
            'primary_etf_code': primary_etf['etf_code'],
            'primary_etf_name': primary_etf['etf_name'],
            'primary_tie': primary_etf['primary_tie'],
            'primary_purity_gap': primary_etf['purity_gap'],
            'primary_turnover': primary_etf['daily_turnover'],
            'backup_etfs': ';'.join(backup_etfs['etf_code'].tolist()) if len(backup_etfs) > 0 else '',
            'has_backup': len(backup_etfs) > 0,
            'tier': 'core'
        })
    elif len(backup_candidates) > 0:
        # 没有core，用backup中TIE最高的
        primary_etf = backup_candidates.iloc[0]
        backup_etfs = backup_candidates[backup_candidates['etf_code'] != primary_etf['etf_code']]
        
        industry_mapping.append({
            'sw_code': sw_code,
            'sw_name': sw_name,
            'primary_etf_code': primary_etf['etf_code'],
            'primary_etf_name': primary_etf['etf_name'],
            'primary_tie': primary_etf['primary_tie'],
            'primary_purity_gap': primary_etf['purity_gap'],
            'primary_turnover': primary_etf['daily_turnover'],
            'backup_etfs': ';'.join(backup_etfs['etf_code'].tolist()) if len(backup_etfs) > 0 else '',
            'has_backup': len(backup_etfs) > 0,
            'tier': 'backup'
        })

df_mapping = pd.DataFrame(industry_mapping)
print(f"行业映射表构建完成，共 {len(df_mapping)} 个行业有映射")
print(f"  Core映射: {(df_mapping['tier']=='core').sum()}")
print(f"  Backup映射: {(df_mapping['tier']=='backup').sum()}")

# ==================== Step 7: 更新 etf_universe.csv ====================
print("\n" + "="*60)
print("Step 7: 更新 etf_universe.csv")
print("="*60)

# 备份原文件
import shutil
backup_path = ETF_UNIVERSE_PATH.with_suffix('.csv.backup')
shutil.copy(ETF_UNIVERSE_PATH, backup_path)
print(f"  已备份原文件: {backup_path}")

# 更新 pool_role
df_etf_updated = df_etf.copy()

# 初始化: 所有行业主题ETF先标记为 industry_rotation_backup
# 已标记为 core/satellite/extended 的不覆盖
for idx, row in df_etf_updated.iterrows():
    if row['asset_class_l2'] == '行业主题':
        current_role = str(row.get('pool_role', ''))
        if current_role not in ['core', 'satellite', 'extended']:
            df_etf_updated.at[idx, 'pool_role'] = 'industry_rotation_backup'

# Core池覆盖为 industry_rotation_core
core_codes = set(df_tie[df_tie['tier'] == 'industry_rotation_core']['etf_code'].tolist())
for idx, row in df_etf_updated.iterrows():
    if row['code'] in core_codes:
        df_etf_updated.at[idx, 'pool_role'] = 'industry_rotation_core'

# 统计
core_count = (df_etf_updated['pool_role'] == 'industry_rotation_core').sum()
backup_count = (df_etf_updated['pool_role'] == 'industry_rotation_backup').sum()
print(f"  industry_rotation_core: {core_count}")
print(f"  industry_rotation_backup: {backup_count}")

# 保存
df_etf_updated.to_csv(ETF_UNIVERSE_PATH, index=False, encoding='utf-8-sig')
print(f"  已更新: {ETF_UNIVERSE_PATH}")

# ==================== Step 8: 输出附属文件 ====================
print("\n" + "="*60)
print("Step 8: 输出附属文件")
print("="*60)

# 1. 行业-ETF映射表
mapping_path = OUTPUT_DIR / 'industry_etf_mapping.csv'
df_mapping.to_csv(mapping_path, index=False, encoding='utf-8-sig')
print(f"  行业-ETF映射表: {mapping_path}")

# 2. TIE详细得分表
tie_path = OUTPUT_DIR / 'etf_tie_scores.csv'
df_tie.to_csv(tie_path, index=False, encoding='utf-8-sig')
print(f"  TIE详细得分: {tie_path}")

# 3. 行业覆盖度报告
coverage_report = []
for sw_code in sorted(all_sw):
    sw_name = sw_industries[sw_code]['name']
    has_mapping = sw_code in covered_sw
    
    if has_mapping:
        mapping_info = df_mapping[df_mapping['sw_code'] == sw_code].iloc[0]
        coverage_report.append({
            'sw_code': sw_code,
            'sw_name': sw_name,
            'has_mapping': True,
            'tier': mapping_info['tier'],
            'primary_etf': mapping_info['primary_etf_code'],
            'primary_tie': mapping_info['primary_tie'],
            'primary_turnover': mapping_info['primary_turnover'],
            'backup_etfs': mapping_info['backup_etfs']
        })
    else:
        coverage_report.append({
            'sw_code': sw_code,
            'sw_name': sw_name,
            'has_mapping': False,
            'tier': 'unmapped',
            'primary_etf': '',
            'primary_tie': 0.0,
            'primary_turnover': 0.0,
            'backup_etfs': ''
        })

df_coverage = pd.DataFrame(coverage_report)
coverage_path = OUTPUT_DIR / 'industry_coverage_report.csv'
df_coverage.to_csv(coverage_path, index=False, encoding='utf-8-sig')
print(f"  行业覆盖度报告: {coverage_path}")

print("\n" + "="*60)
print("TIE映射引擎执行完成！")
print("="*60)
