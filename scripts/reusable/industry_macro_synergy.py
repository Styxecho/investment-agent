#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
行业轮动卫星策略 - Day 7: 宏观协同
输入: macro_state_detail表 + industry_selected_pool.csv
输出: industry_final_pool.csv (含仓位建议)
"""

import pandas as pd
import sqlite3
from pathlib import Path

OUTPUT_DIR = Path('docs/research/industry_rotation')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 配置 ====================
# 极端象限定义：这些状态下清仓卫星仓位
EXTREME_REGIMES = [
    '深度衰退',
    '过热',
    '滞胀',
]

# 非极端象限降权系数
NON_EXTREME_WEIGHT = 0.8

# 卫星仓位占总资产比例
SATELLITE_RATIO = 0.10

# ==================== Step 1: 读取宏观状态 ====================
print("="*60)
print("Step 1: 读取最新宏观状态")
print("="*60)

conn = sqlite3.connect('data_external/db/external_data.db')

df_macro = pd.read_sql("""
    SELECT publish_date, growth_state, inflation_state, liquidity_state, macro_regime, warnings
    FROM macro_state_detail
    ORDER BY publish_date DESC
    LIMIT 3
""", conn)

conn.close()

latest = df_macro.iloc[0]
print(f"最新宏观状态日期: {latest['publish_date']}")
print(f"增长: {latest['growth_state']}")
print(f"通胀: {latest['inflation_state']}")
print(f"流动性: {latest['liquidity_state']}")
print(f"象限: {latest['macro_regime']}")

# ==================== Step 2: 判断极端象限 ====================
print("\n" + "="*60)
print("Step 2: 判断极端象限")
print("="*60)

current_regime = latest['macro_regime']
is_extreme = any(regime in current_regime for regime in EXTREME_REGIMES)

print(f"当前象限: {current_regime}")
print(f"是否极端象限: {is_extreme}")

if is_extreme:
    print("[!] 极端象限 detected: 建议清仓卫星仓位")
    weight_multiplier = 0.0
else:
    print("[OK] 非极端象限: 卫星仓位降权至80%")
    weight_multiplier = NON_EXTREME_WEIGHT

# ==================== Step 3: 读取优势池 ====================
print("\n" + "="*60)
print("Step 3: 读取优势池")
print("="*60)

df_pool = pd.read_csv(OUTPUT_DIR / 'industry_selected_pool.csv', encoding='utf-8-sig')

# 过滤掉无ETF映射的行业（primary_etf_code为空）
df_pool_valid = df_pool[df_pool['primary_etf_code'].notna()].copy()

print(f"优势池行业数: {len(df_pool)}")
print(f"有ETF映射的行业: {len(df_pool_valid)}")

print(f"优势池行业数: {len(df_pool)}")
print(f"有ETF映射的行业: {len(df_pool_valid)}")

# ==================== Step 4: 仓位分配 ====================
print("\n" + "="*60)
print("Step 4: 仓位分配")
print("="*60)

if is_extreme:
    # 极端象限：清仓
    df_pool_valid['target_weight'] = 0.0
    df_pool_valid['action'] = '清仓'
    print("极端象限：所有行业仓位设为0")
else:
    # 非极端象限：等权分配，然后降权
    n = len(df_pool_valid)
    if n > 0:
        equal_weight = 1.0 / n  # 行业内等权
        final_weight = equal_weight * weight_multiplier * SATELLITE_RATIO  # 降权后占总资产比例
        
        df_pool_valid['target_weight'] = final_weight
        df_pool_valid['action'] = '持有'
        
        print(f"非极端象限：{n}个行业等权")
        print(f"  每个行业权重: {equal_weight:.1%} (占卫星池)")
        print(f"  降权后权重: {final_weight:.2%} (占总资产)")
        print(f"  卫星池总占用: {final_weight * n:.1%} (目标: {SATELLITE_RATIO * weight_multiplier:.1%})")

# ==================== Step 5: 行业周期敏感度调整 ====================
print("\n" + "="*60)
print("Step 5: 行业周期敏感度调整")
print("="*60)

# 定义行业周期敏感度（高/中/低）
cycle_sensitivity = {
    '801050': 'high',   # 有色金属
    '801040': 'high',   # 钢铁
    '801950': 'high',   # 煤炭
    '801710': 'high',   # 建材
    '801890': 'high',   # 机械设备
    '801880': 'high',   # 汽车
    '801180': 'high',   # 房地产
    '801030': 'medium', # 化工
    '801730': 'medium', # 电力设备
    '801080': 'medium', # 电子
    '801750': 'medium', # 计算机
    '801760': 'medium', # 传媒
    '801770': 'medium', # 通信
    '801120': 'low',    # 食品饮料
    '801150': 'low',    # 医药生物
    '801160': 'low',    # 公用事业
    '801170': 'low',    # 交通运输
    '801780': 'low',    # 银行
    '801790': 'low',    # 非银金融
}

# 提取申万代码（去掉.SI）
df_pool_valid['sw_code_clean'] = df_pool_valid['index_code'].astype(str).str.replace('.SI', '', regex=False)
df_pool_valid['sensitivity'] = df_pool_valid['sw_code_clean'].map(cycle_sensitivity).fillna('medium')

# 根据宏观增长状态调整权重
# 扩张期：高敏感度行业加配；衰退期：低敏感度行业加配
growth_state = latest['growth_state']
print(f"增长状态: {growth_state}")

if '扩张' in growth_state or '复苏' in growth_state:
    # 扩张期：高敏+20%，低敏-20%
    print("扩张期：高敏感度行业加配20%，低敏感度降配20%")
    df_pool_valid['sensitivity_adj'] = df_pool_valid['sensitivity'].apply(
        lambda x: 1.2 if x == 'high' else (0.8 if x == 'low' else 1.0)
    )
elif '衰退' in growth_state or '收缩' in growth_state:
    # 衰退期：低敏+20%，高敏-20%
    print("衰退期：低敏感度行业加配20%，高敏感度降配20%")
    df_pool_valid['sensitivity_adj'] = df_pool_valid['sensitivity'].apply(
        lambda x: 0.8 if x == 'high' else (1.2 if x == 'low' else 1.0)
    )
else:
    # 中性：不加调整
    print("中性状态：不做敏感度调整")
    df_pool_valid['sensitivity_adj'] = 1.0

# 应用敏感度调整（仅在非极端象限）
if not is_extreme:
    df_pool_valid['target_weight'] = df_pool_valid['target_weight'] * df_pool_valid['sensitivity_adj']
    
    # 归一化，确保总权重不超过卫星池上限
    total_weight = df_pool_valid['target_weight'].sum()
    max_total = SATELLITE_RATIO * weight_multiplier
    if total_weight > max_total:
        df_pool_valid['target_weight'] = df_pool_valid['target_weight'] / total_weight * max_total
        print(f"归一化后总权重: {max_total:.2%}")

# ==================== Step 6: 输出结果 ====================
print("\n" + "="*60)
print("Step 6: 输出最终池")
print("="*60)

# 构建最终输出
df_final = df_pool_valid[['index_code', 'sw_name', 'primary_etf_code', 'primary_etf_name', 
                          'tier', 'composite_score', 'target_weight', 'action', 'sensitivity']].copy()

df_final = df_final.sort_values('target_weight', ascending=False).reset_index(drop=True)

# 保存
output_path = OUTPUT_DIR / 'industry_final_pool.csv'
df_final.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"  最终池: {output_path}")

# 打印结果
print("\n最终池行业列表:")
for _, row in df_final.iterrows():
    print(f"  {row['sw_name']} ({row['index_code']})")
    print(f"      ETF: {row['primary_etf_code']} | 操作: {row['action']} | 目标权重: {row['target_weight']:.2%} | 敏感度: {row['sensitivity']}")

print("\n统计:")
print(f"  总行业数: {len(df_final)}")
print(f"  总目标权重: {df_final['target_weight'].sum():.2%}")
print(f"  极端象限清仓: {is_extreme}")

print("\n" + "="*60)
print("Day 7 执行完成!")
print("="*60)
