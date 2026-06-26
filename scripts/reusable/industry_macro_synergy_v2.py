#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
行业轮动卫星策略 - Day 7修正版: 宏观协同
严格遵循Phase_2.4&2.5_Methodology_Summary.md V5.0方法论

正确逻辑:
1. 极端象限(失速衰退/极端滞胀) → 清仓
2. 非极端象限 → 根据象限偏好，对不匹配行业Composite_score × 0.8
3. 降权后重新排序，构建最终池
4. 等权分配仓位
"""

import pandas as pd
import sqlite3
from pathlib import Path

OUTPUT_DIR = Path('docs/research/industry_rotation')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 配置 ====================
# 极端象限定义：清仓
EXTREME_REGIMES = ['失速衰退', '极端滞胀']

# 降权系数
DOWNSIDE_WEIGHT = 0.8

# 卫星仓位占总资产比例
SATELLITE_RATIO = 0.10

# 行业周期敏感度标签（静态预设，基于常识）
# TODO: 未来应替换为基于历史Beta或营收对GDP弹性的量化计算
CYCLE_SENSITIVITY = {
    # === 高敏感度（强周期） ===
    '801050': 'high',   # 有色金属
    '801040': 'high',   # 钢铁
    '801950': 'high',   # 煤炭
    '801710': 'high',   # 建筑材料
    '801890': 'high',   # 机械设备
    '801880': 'high',   # 汽车
    '801180': 'high',   # 房地产
    '801720': 'high',   # 建筑装饰（与基建/地产强相关）
    '801140': 'high',   # 轻工制造（家具/造纸，与地产/出口相关）
    
    # === 中敏感度（科技制造，部分顺周期+产业独立周期） ===
    '801030': 'medium', # 基础化工
    '801730': 'medium', # 电力设备
    '801080': 'medium', # 电子
    '801750': 'medium', # 计算机
    '801760': 'medium', # 传媒
    '801770': 'medium', # 通信
    '801230': 'medium', # 综合（多元化，难以归类）
    
    # === 低敏感度（防御型） ===
    '801120': 'low',    # 食品饮料
    '801150': 'low',    # 医药生物
    '801160': 'low',    # 公用事业
    '801170': 'low',    # 交通运输（基础设施属性）
    '801780': 'low',    # 银行
    '801790': 'low',    # 非银金融
    '801200': 'low',    # 商贸零售（必选消费属性）
    '801970': 'low',    # 环保（公用事业属性）
    '801980': 'low',    # 美容护理（可选消费但需求稳定）
    '801130': 'low',    # 纺织服饰（消费类，防御属性）
    '801210': 'low',    # 社会服务（服务消费，需求稳定）
    '801010': 'low',    # 农林牧渔（必选消费，但有一定周期）
}

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
    print("[!] 极端象限: 清仓卫星仓位")
else:
    print("[OK] 非极端象限: 进入降权判断")

# ==================== Step 3: 读取优势池 ====================
print("\n" + "="*60)
print("Step 3: 读取优势池")
print("="*60)

df_pool = pd.read_csv(OUTPUT_DIR / 'industry_selected_pool.csv', encoding='utf-8-sig')

# 过滤掉无ETF映射的行业
df_pool_valid = df_pool[df_pool['primary_etf_code'].notna()].copy()

print(f"优势池行业数: {len(df_pool)}")
print(f"有ETF映射的行业: {len(df_pool_valid)}")

# ==================== Step 4: 宏观协同降权 ====================
print("\n" + "="*60)
print("Step 4: 宏观协同降权（Composite_score层面）")
print("="*60)

if is_extreme:
    # 极端象限：全部清仓
    df_pool_valid['composite_score_adj'] = -999  # 标记为清仓
    df_pool_valid['action'] = '清仓'
    df_pool_valid['downside_reason'] = f'极端象限: {current_regime}'
    
else:
    # 非极端象限：根据象限判断偏好，对不匹配行业降权
    
    # 添加敏感度标签
    df_pool_valid['sw_code_clean'] = df_pool_valid['index_code'].astype(str).str.replace('.SI', '', regex=False)
    df_pool_valid['sensitivity'] = df_pool_valid['sw_code_clean'].map(CYCLE_SENSITIVITY).fillna('medium')
    
    # 判断当前象限的偏好
    # P7强势复苏 / P8完美扩张 / P3过热 → 偏好高敏感（顺周期），降权低敏感（防御型）
    # P5宽衰退 / P6弱复苏 → 偏好低敏感（防御型），降权高敏感（强周期）
    # P2典型滞胀 → 偏好上游资源/红利，降权成长型（中敏感中的科技成长）
    # P10震荡观望 / P9类衰退过渡 → 无显著偏好，不降权
    
    if any(r in current_regime for r in ['强势复苏', '完美扩张', '过热']):
        preferred = 'high'
        downside_target = 'low'
        reason = f'{current_regime}: 偏好顺周期，防御型降权'
        
    elif any(r in current_regime for r in ['宽衰退', '弱复苏']):
        preferred = 'low'
        downside_target = 'high'
        reason = f'{current_regime}: 偏好防御型，强周期降权'
        
    elif '滞胀' in current_regime:
        preferred = 'low'  # 上游资源/红利偏防御
        downside_target = 'medium'  # 降权成长型（科技成长）
        reason = f'{current_regime}: 偏好上游资源/红利，成长型降权'
        
    else:
        # 震荡/观望/类衰退过渡：无显著偏好
        preferred = None
        downside_target = None
        reason = f'{current_regime}: 无显著偏好，不做降权'
    
    print(f"象限偏好: {reason}")
    
    # 应用降权：不匹配的行业 composite_score × 0.8
    df_pool_valid['composite_score_adj'] = df_pool_valid.apply(
        lambda row: row['composite_score'] * DOWNSIDE_WEIGHT 
        if downside_target and row['sensitivity'] == downside_target 
        else row['composite_score'],
        axis=1
    )
    
    df_pool_valid['downside_reason'] = df_pool_valid.apply(
        lambda row: f'不匹配{downside_target}敏感度，降权{DOWNSIDE_WEIGHT}' 
        if downside_target and row['sensitivity'] == downside_target 
        else '匹配偏好或无需降权',
        axis=1
    )
    
    df_pool_valid['action'] = '持有'

# 按调整后的composite_score重新排序（极端象限除外）
if not is_extreme:
    df_pool_valid = df_pool_valid.sort_values('composite_score_adj', ascending=False).reset_index(drop=True)
    
    print(f"\n降权前后对比（Top 5）:")
    for _, row in df_pool_valid.head(5).iterrows():
        adj = row['composite_score_adj']
        orig = row['composite_score']
        mark = "*" if adj != orig else ""
        print(f"  {row['sw_name']}: {orig:.3f} → {adj:.3f} {mark} ({row['downside_reason']})")

# ==================== Step 5: 输出候选池（不含权重分配）====================
print("\n" + "="*60)
print("Step 5: 输出宏观协同后的候选池")
print("="*60)

# 注意：中观层只输出候选池，不做仓位分配
# 真正的权重分配属于Phase 2.5微观层（入场确认、仓位分配、风控防线）

# 构建输出
cols = ['index_code', 'sw_name', 'primary_etf_code', 'primary_etf_name', 
        'tier', 'composite_score', 'composite_score_adj', 'sensitivity', 'downside_reason']

df_final = df_pool_valid[cols].copy()

if not is_extreme:
    df_final = df_final.sort_values('composite_score_adj', ascending=False).reset_index(drop=True)

# 保存
output_path = OUTPUT_DIR / 'industry_final_pool.csv'
df_final.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"  候选池: {output_path}")

# 打印结果
if is_extreme:
    print("\n[!] 极端象限清仓，无候选池")
else:
    print("\n候选池行业列表（按Composite_score_adj排序）:")
    for _, row in df_final.iterrows():
        adj_mark = "*" if row['composite_score'] != row['composite_score_adj'] else ""
        print(f"  {row['sw_name']} ({row['index_code']}){adj_mark}")
        print(f"      ETF: {row['primary_etf_code']} | Composite: {row['composite_score_adj']:.3f} | 敏感度: {row['sensitivity']}")
        if adj_mark:
            print(f"      降权: {row['composite_score']:.3f} → {row['composite_score_adj']:.3f} ({row['downside_reason']})")

print(f"\n统计:")
print(f"  候选池行业数: {len(df_final)}")
print(f"  极端象限清仓: {is_extreme}")
if not is_extreme:
    n_downside = (df_final['composite_score'] != df_final['composite_score_adj']).sum()
    print(f"  被降权行业: {n_downside}")
    print(f"\n  注：权重分配需待Phase 2.5微观层（入场确认+仓位分配）完成后确定")
    print(f"      当前为候选池，非最终持仓")

print("\n" + "="*60)
print("Day 7 修正版执行完成!")
print("="*60)
