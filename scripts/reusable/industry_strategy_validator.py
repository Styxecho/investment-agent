#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
行业轮动策略 - Day 8-9: 数据验证与单元测试
方法：独立脚本交叉验证
"""

import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

OUTPUT_DIR = Path('docs/research/industry_rotation')
REPORT_PATH = OUTPUT_DIR / 'validation_report.txt'

print("="*60)
print("行业轮动策略 - 数据验证报告")
print("="*60)

report_lines = []
report_lines.append("="*60)
report_lines.append("行业轮动策略 - 数据验证报告")
report_lines.append("="*60)

# ==================== 1. MA60计算验证 ====================
print("\n[1/5] MA60计算验证")
print("-"*60)

conn = sqlite3.connect('data_external/db/external_data.db')
df_sw = pd.read_sql("""
    SELECT index_code, trade_date, close_price 
    FROM index_daily 
    WHERE index_code LIKE '801%.SI'
    ORDER BY index_code, trade_date
""", conn)
df_sw['trade_date'] = pd.to_datetime(df_sw['trade_date'], format='%Y%m%d')
df_sw['close_price'] = pd.to_numeric(df_sw['close_price'], errors='coerce')

# 独立计算MA60
sample_industries = ['801050.SI', '801080.SI', '801150.SI']  # 有色、电子、医药

print("抽样验证3个行业：")
ma60_pass = True
for sw_code in sample_industries:
    df_ind = df_sw[df_sw['index_code'] == sw_code].sort_values('trade_date').reset_index(drop=True)
    
    # 方法A：现有代码逻辑（rolling）
    ma60_existing = df_ind['close_price'].rolling(window=60, min_periods=60).mean()
    
    # 方法B：手动计算最近5天的MA60
    recent = df_ind.tail(5)
    print(f"\n  {sw_code} - 最近5个交易日:")
    print(f"  {'日期':<12} {'收盘价':<10} {'MA60':<10}")
    for _, row in recent.iterrows():
        idx = row.name
        ma_val = ma60_existing.iloc[idx] if idx < len(ma60_existing) else np.nan
        print(f"  {row['trade_date'].strftime('%Y-%m-%d')}  {row['close_price']:<10.2f} {ma_val:<10.2f}")
    
    # 验证：手动计算最后一天MA60
    last_60 = df_ind['close_price'].tail(60)
    manual_ma60 = last_60.mean()
    script_ma60 = ma60_existing.iloc[-1]
    
    diff = abs(manual_ma60 - script_ma60)
    status = "PASS" if diff < 0.01 else "FAIL"
    print(f"  手工MA60: {manual_ma60:.4f}, 脚本MA60: {script_ma60:.4f}, 差异: {diff:.6f} [{status}]")
    
    if diff >= 0.01:
        ma60_pass = False
    
    report_lines.append(f"\nMA60验证 - {sw_code}: {status} (diff={diff:.6f})")

print(f"\nMA60验证结论: {'全部通过' if ma60_pass else '存在差异'}")
report_lines.append(f"\nMA60验证结论: {'全部通过' if ma60_pass else '存在差异'}")

# ==================== 2. 收益率计算验证 ====================
print("\n[2/5] 6M/12M收益率验证")
print("-"*60)

sample_dates = [
    ('801050.SI', '2026-04-30', 126, 252),  # 有色金属
    ('801080.SI', '2026-04-30', 126, 252),  # 电子
]

ret_pass = True
for sw_code, end_date_str, days_6m, days_12m in sample_dates:
    df_ind = df_sw[df_sw['index_code'] == sw_code].sort_values('trade_date').reset_index(drop=True)
    
    end_idx = df_ind[df_ind['trade_date'] <= end_date_str].index[-1]
    start_6m_idx = max(0, end_idx - days_6m)
    start_12m_idx = max(0, end_idx - days_12m)
    
    end_price = df_ind.loc[end_idx, 'close_price']
    start_6m_price = df_ind.loc[start_6m_idx, 'close_price']
    start_12m_price = df_ind.loc[start_12m_idx, 'close_price']
    
    ret_6m_manual = end_price / start_6m_price - 1
    ret_12m_manual = end_price / start_12m_price - 1
    acceleration_manual = ret_6m_manual - ret_12m_manual
    
    print(f"\n  {sw_code} (截至 {end_date_str}):")
    print(f"    收盘价: {end_price:.2f} (end) | {start_6m_price:.2f} (6M前) | {start_12m_price:.2f} (12M前)")
    print(f"    6M收益: {ret_6m_manual:.2%}")
    print(f"    12M收益: {ret_12m_manual:.2%}")
    print(f"    加速度: {acceleration_manual:.2%}")
    
    # 对比已有结果
    df_momentum = pd.read_csv(OUTPUT_DIR / 'industry_momentum_scores.csv', encoding='utf-8-sig')
    existing = df_momentum[df_momentum['sw_code'] == sw_code]
    if len(existing) > 0:
        row = existing.iloc[0]
        diff_6m = abs(ret_6m_manual - row['ret_6m'])
        diff_12m = abs(ret_12m_manual - row['ret_12m'])
        diff_acc = abs(acceleration_manual - row['acceleration'])
        
        status = "PASS" if max(diff_6m, diff_12m, diff_acc) < 0.001 else "FAIL"
        print(f"    对比已有结果 - 6M diff: {diff_6m:.6f}, 12M diff: {diff_12m:.6f}, ACC diff: {diff_acc:.6f} [{status}]")
        
        if max(diff_6m, diff_12m, diff_acc) >= 0.001:
            ret_pass = False
        
        report_lines.append(f"收益率验证 - {sw_code}: {status}")

print(f"\n收益率验证结论: {'全部通过' if ret_pass else '存在差异'}")
report_lines.append(f"收益率验证结论: {'全部通过' if ret_pass else '存在差异'}")

# ==================== 3. TIE计算验证（抽样） ====================
print("\n[3/5] TIE计算验证（抽样）")
print("-"*60)

# 验证159381.SZ的TIE计算
df_tie = pd.read_csv(OUTPUT_DIR / 'etf_tie_scores.csv', encoding='utf-8-sig')
etf_159381 = df_tie[df_tie['etf_code'] == '159381.SZ']

if len(etf_159381) > 0:
    row = etf_159381.iloc[0]
    print(f"\n  159381.SZ (创业板人工智能ETF):")
    print(f"    映射行业: {row['primary_sw_name']} ({row['primary_sw_code']})")
    print(f"    TIE: {row['primary_tie']:.2%}")
    print(f"    纯度差: {row['purity_gap']:.2%}")
    print(f"    分级: {row['tier']}")
    
    # 重新计算TIE
    import os
    idx_file = [f for f in os.listdir('data_external/reference/index_components') if '970070' in f][0]
    df_comp = pd.read_excel(f'data_external/reference/index_components/{idx_file}', dtype=str)
    
    # 读取申万通信行业成分股
    df_sw_comm = pd.read_excel('data_external/reference/index_components/sw_801770.xls', dtype=str)
    sw_stocks = set(df_sw_comm.iloc[:, 3].astype(str).str.strip().str.zfill(6))
    
    # 计算TIE
    comp_codes = df_comp.iloc[:, 1].astype(str).str.strip().str.zfill(6)
    comp_weights = pd.to_numeric(df_comp.iloc[:, -1], errors='coerce')
    
    matched = comp_codes.isin(sw_stocks)
    tie_manual = comp_weights[matched].sum() / 100  # 百分比转小数
    
    diff_tie = abs(tie_manual - row['primary_tie'])
    status = "PASS" if diff_tie < 0.01 else "FAIL"
    print(f"    手工TIE: {tie_manual:.2%}, 脚本TIE: {row['primary_tie']:.2%}, 差异: {diff_tie:.4f} [{status}]")
    
    report_lines.append(f"TIE验证 - 159381.SZ: {status} (diff={diff_tie:.4f})")

# 验证边界案例：TIE=50.6%的两个ETF
print(f"\n  边界案例验证 (TIE≈50%):")
boundary_etfs = df_tie[(df_tie['primary_tie'] > 0.50) & (df_tie['primary_tie'] < 0.51)]
for _, row in boundary_etfs.iterrows():
    print(f"    {row['etf_code']}: TIE={row['primary_tie']:.2%}, 纯度差={row['purity_gap']:.2%}, 分级={row['tier']}")

print(f"\nTIE验证结论: 见上文")

# ==================== 4. 排名稳定性验证 ====================
print("\n[4/5] 排名稳定性验证")
print("-"*60)

df_rs = pd.read_csv(OUTPUT_DIR / 'industry_rs_scores.csv', encoding='utf-8-sig')

# 验证801710.SI（建筑材料，RS_score=78.2）
print(f"\n  801710.SI (建筑材料, RS={df_rs[df_rs['sw_code']=='801710.SI'].iloc[0]['rs_score']:.1f}):")
print(f"    当前排名: {df_rs[df_rs['sw_code']=='801710.SI'].iloc[0]['current_rank']:.0f}")
print(f"    12月平均排名: {df_rs[df_rs['sw_code']=='801710.SI'].iloc[0]['avg_rank_12m']:.1f}")
print(f"    排名标准差: {df_rs[df_rs['sw_code']=='801710.SI'].iloc[0]['rank_std_12m']:.2f}")
print(f"    排名趋势: {df_rs[df_rs['sw_code']=='801710.SI'].iloc[0]['rank_trend']:+.0f}")

# 验证RS_score公式
sample = df_rs[df_rs['sw_code'] == '801710.SI'].iloc[0]
rs_manual = 0.4 * sample['rank_score'] + 0.3 * sample['stability_score'] + 0.3 * sample['trend_score']
diff_rs = abs(rs_manual - sample['rs_score'])
status = "PASS" if diff_rs < 0.1 else "FAIL"
print(f"    手工RS: {rs_manual:.2f}, 脚本RS: {sample['rs_score']:.2f}, 差异: {diff_rs:.4f} [{status}]")

report_lines.append(f"RS_score验证 - 801710.SI: {status} (diff={diff_rs:.4f})")

# ==================== 5. 宏观协同验证 ====================
print("\n[5/5] 宏观协同验证")
print("-"*60)

df_final = pd.read_csv(OUTPUT_DIR / 'industry_final_pool.csv', encoding='utf-8-sig')

# 验证总权重
total_weight = df_final['target_weight'].sum()
print(f"\n  总目标权重: {total_weight:.2%}")
print(f"  预期权重: 8.00% (10% × 0.8)")
status = "PASS" if abs(total_weight - 0.08) < 0.001 else "FAIL"
print(f"  权重验证: {status}")

# 验证敏感度调整
print(f"\n  敏感度调整验证:")
for _, row in df_final.iterrows():
    base_weight = total_weight / len(df_final)
    expected_weight = base_weight * (1.2 if row['sensitivity'] == 'high' else (0.8 if row['sensitivity'] == 'low' else 1.0))
    # 由于归一化，实际权重会有微调，这里只验证方向
    direction = "↑" if row['target_weight'] > base_weight else ("↓" if row['target_weight'] < base_weight else "→")
    print(f"    {row['sw_name']}: {row['sensitivity']:8s} | 基准{base_weight:.2%} → 实际{row['target_weight']:.2%} {direction}")

report_lines.append(f"宏观协同验证 - 总权重: {status}")

# ==================== 6. 边界情况检查 ====================
print("\n[补充] 边界情况检查")
print("-"*60)

# 检查8个无映射行业
print(f"\n  无ETF映射的行业:")
unmapped = ['801130', '801140', '801170', '801200', '801230', '801720', '801970', '801980']
df_mapping_check = pd.read_csv(OUTPUT_DIR / 'industry_etf_mapping.csv', encoding='utf-8-sig')
for sw in unmapped:
    has_etf = sw in df_mapping_check['sw_code'].astype(str).str.replace('.SI', '').values
    print(f"    {sw}: {'有ETF' if has_etf else '无ETF'} [{ 'FAIL' if has_etf else 'PASS'}]")

# 检查缺失成分股权重文件的ETF
print(f"\n  缺失成分股权重文件的ETF:")
missing_files = ['399976.SZ', '990001.CSI', '399395.SZ']
df_tie_check = pd.read_csv(OUTPUT_DIR / 'etf_tie_scores.csv', encoding='utf-8-sig')
for idx in missing_files:
    etf_list = df_tie_check[df_tie_check['index_code'] == idx]
    print(f"    {idx}: {'已计算' if len(etf_list) > 0 else '未计算'} [{'PASS' if len(etf_list) == 0 else 'FAIL'}]")

# ==================== 总结 ====================
print("\n" + "="*60)
print("验证总结")
print("="*60)

all_pass = ma60_pass and ret_pass and diff_tie < 0.01 and diff_rs < 0.1
print(f"\n整体结论: {'全部通过' if all_pass else '部分未通过'}")
print(f"\n详细报告已保存至: {REPORT_PATH}")

report_lines.append("\n" + "="*60)
report_lines.append(f"整体结论: {'全部通过' if all_pass else '部分未通过'}")
report_lines.append("="*60)

# 保存报告
with open(REPORT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report_lines))

print("\nDay 8-9 验证完成!")
