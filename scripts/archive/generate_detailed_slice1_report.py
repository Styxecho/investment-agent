#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成详细的逐月宏观状态推导报告
展示：原始数据 → 趋势计算 → 维度判定 → 状态综合 的完整过程
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

# 读取原始宏观数据
indicators = {
    'CN_PMI_MFG_M': 'pmi_mfg',
    'CN_PPI_YOY_M': 'ppi',
    'CN_M1_YOY_M': 'm1',
    'CN_M2_YOY_M': 'm2',
    'CN_SFS_YOY_M': 'sfs',
    'CN_IAV_YOY_M': 'iav',
    'CN_CPI_YOY_M': 'cpi'
}

macro_data = []
for ind_code, ind_name in indicators.items():
    sql = f"SELECT publish_date, factor_value FROM macro_factor_value WHERE indicator_code = '{ind_code}' AND factor_type = 'level' AND publish_date BETWEEN '20160101' AND '20171231' ORDER BY publish_date"
    df = pd.read_sql(sql, engine)
    df['year_month'] = pd.to_datetime(df['publish_date'].astype(str)).dt.strftime('%Y%m')
    df = df.rename(columns={'factor_value': ind_name})
    macro_data.append(df[['year_month', ind_name]])

macro_df = reduce(lambda left, right: pd.merge(left, right, on='year_month', how='outer'), macro_data)
macro_df['m1m2_scissor'] = macro_df['m1'] - macro_df['m2']
macro_df = macro_df.sort_values('year_month').reset_index(drop=True)

# 只保留切片1的数据
slice1_df = macro_df[(macro_df['year_month'] >= '201607') & (macro_df['year_month'] <= '201712')].copy()

print("="*100)
print("切片1详细推导报告：2016-2017 供给侧改革与漂亮50")
print("="*100)
print("\n【方法论说明】")
print("1. 趋势计算：3个月移动平均（MA3）+ 斜率（最近2月变化）")
print("2. 方向判定：MA3 > 0.5 = 扩张/上行，MA3 < -0.5 = 收缩/下行，中间 = 中性")
print("3. 流动性：货币（M1-M2剪刀差）× 信用（社融增速）")
print("4. 增长：PMI制造业（权重60%）+ 工业增加值（权重40%）")
print("5. 通胀：PPI（主导）+ CPI（验证）")
print("6. 状态判定：三维组合 → 8种核心状态（匹配度≥3的维度）")
print("="*100)

# 计算趋势
def calculate_trend_detailed(series, window=3):
    """详细趋势计算，返回所有中间值"""
    if len(series) < window:
        return None
    
    # 移动平均
    ma = series.rolling(window=window).mean()
    ma_current = ma.iloc[-1]
    ma_prev = ma.iloc[-2] if len(ma) >= 2 else None
    
    # 斜率
    slope = series.iloc[-1] - series.iloc[-2] if len(series) >= 2 else 0
    
    # 原始值
    raw_values = series.tail(window).tolist()
    
    return {
        'raw_values': raw_values,
        'ma_current': round(ma_current, 3) if not pd.isna(ma_current) else None,
        'ma_prev': round(ma_prev, 3) if ma_prev is not None and not pd.isna(ma_prev) else None,
        'slope': round(slope, 3),
        'current': round(series.iloc[-1], 3)
    }

# 维度判定
def judge_dimension(name, trend_data, up_threshold=0.5, down_threshold=-0.5):
    """判定维度方向"""
    if trend_data is None or trend_data['ma_current'] is None:
        return {'direction': 'unknown', 'strength': 'unknown', 'details': '数据不足'}
    
    ma = trend_data['ma_current']
    slope = trend_data['slope']
    
    # 方向
    if ma > up_threshold:
        direction = 'up'
        dir_desc = '扩张/上行'
    elif ma < down_threshold:
        direction = 'down'
        dir_desc = '收缩/下行'
    else:
        direction = 'flat'
        dir_desc = '中性/平稳'
    
    # 强度
    if slope > 0.1:
        strength = 'accelerating'
        str_desc = '加速'
    elif slope < -0.1:
        strength = 'decelerating'
        str_desc = '减速'
    else:
        strength = 'stable'
        str_desc = '稳定'
    
    details = f"MA3={ma}, 斜率={slope}, 方向={dir_desc}, 强度={str_desc}"
    
    return {
        'direction': direction,
        'strength': strength,
        'details': details,
        'ma': ma,
        'slope': slope
    }

# 逐月推导
for i in range(2, len(slice1_df)):
    current_month = slice1_df.iloc[i]['year_month']
    window_df = slice1_df.iloc[max(0, i-2):i+1]
    
    print(f"\n{'='*100}")
    print(f"【{current_month}月】")
    print(f"{'='*100}")
    
    # 1. 原始数据展示
    print("\n1. 原始因子数据（Z-score）：")
    current_row = slice1_df.iloc[i]
    print(f"   PMI制造业: {current_row['pmi_mfg']:.3f}")
    print(f"   工业增加值: {current_row['iav']:.3f}")
    print(f"   PPI: {current_row['ppi']:.3f}")
    print(f"   CPI: {current_row['cpi']:.3f}")
    print(f"   M1-M2剪刀差: {current_row['m1m2_scissor']:.3f}")
    sfs_val = current_row['sfs']
    if not pd.isna(sfs_val):
        print(f"   社融增速: {sfs_val:.3f}")
    else:
        print(f"   社融增速: N/A")
    
    # 2. 趋势计算
    print("\n2. 趋势计算（3个月窗口）：")
    
    pmi_trend = calculate_trend_detailed(window_df['pmi_mfg'])
    iav_trend = calculate_trend_detailed(window_df['iav'])
    ppi_trend = calculate_trend_detailed(window_df['ppi'])
    cpi_trend = calculate_trend_detailed(window_df['cpi'])
    m1m2_trend = calculate_trend_detailed(window_df['m1m2_scissor'])
    sfs_trend = calculate_trend_detailed(window_df['sfs']) if not window_df['sfs'].isna().all() else None
    
    if pmi_trend:
        print(f"   PMI制造业: 近3月={pmi_trend['raw_values']}, MA3={pmi_trend['ma_current']}, 斜率={pmi_trend['slope']}")
    if iav_trend:
        print(f"   工业增加值: 近3月={iav_trend['raw_values']}, MA3={iav_trend['ma_current']}, 斜率={iav_trend['slope']}")
    if ppi_trend:
        print(f"   PPI: 近3月={ppi_trend['raw_values']}, MA3={ppi_trend['ma_current']}, 斜率={ppi_trend['slope']}")
    if cpi_trend:
        print(f"   CPI: 近3月={cpi_trend['raw_values']}, MA3={cpi_trend['ma_current']}, 斜率={cpi_trend['slope']}")
    if m1m2_trend:
        print(f"   M1-M2: 近3月={m1m2_trend['raw_values']}, MA3={m1m2_trend['ma_current']}, 斜率={m1m2_trend['slope']}")
    if sfs_trend:
        print(f"   社融: 近3月={sfs_trend['raw_values']}, MA3={sfs_trend['ma_current']}, 斜率={sfs_trend['slope']}")
    elif sfs_trend is None:
        print(f"   社融: 数据缺失")
    
    # 3. 维度判定
    print("\n3. 维度判定：")
    
    # 流动性
    money_dim = judge_dimension('M1-M2', m1m2_trend)
    if sfs_trend:
        credit_dim = judge_dimension('社融', sfs_trend)
        print(f"   货币（M1-M2）: {money_dim['details']}")
        print(f"   信用（社融）: {credit_dim['details']}")
        
        # 货币×信用组合
        if money_dim['direction'] == 'up' and credit_dim['direction'] == 'up':
            liq_status = '双宽'
        elif money_dim['direction'] == 'up' and credit_dim['direction'] == 'down':
            liq_status = '宽货币紧信用'
        elif money_dim['direction'] == 'down' and credit_dim['direction'] == 'up':
            liq_status = '紧货币宽信用'
        elif money_dim['direction'] == 'down' and credit_dim['direction'] == 'down':
            liq_status = '双紧'
        else:
            liq_status = '结构性宽松' if (money_dim['direction'] == 'up' or credit_dim['direction'] == 'up') else '结构性紧缩'
        
        print(f"   → 流动性组合: {liq_status}")
    else:
        print(f"   货币（M1-M2）: {money_dim['details']}")
        print(f"   信用（社融）: 数据缺失，无法判定")
        liq_status = 'unknown'
    
    # 增长
    pmi_dim = judge_dimension('PMI', pmi_trend)
    iav_dim = judge_dimension('IAV', iav_trend)
    print(f"   PMI制造业: {pmi_dim['details']}")
    print(f"   工业增加值: {iav_dim['details']}")
    
    if pmi_dim['direction'] == 'up' and iav_dim['direction'] == 'up':
        growth_status = '扩张加速'
    elif pmi_dim['direction'] == 'up' and iav_dim['direction'] in ['flat', 'down']:
        growth_status = '扩张减速' if pmi_dim['strength'] == 'decelerating' else '平稳扩张'
    elif pmi_dim['direction'] == 'down' and iav_dim['direction'] == 'down':
        growth_status = '收缩恶化'
    elif pmi_dim['direction'] == 'flat' and iav_dim['direction'] == 'flat':
        growth_status = '增长 uncertain'
    else:
        growth_status = '增长 uncertain（分歧）'
    
    print(f"   → 增长状态: {growth_status}")
    
    # 通胀
    ppi_dim = judge_dimension('PPI', ppi_trend)
    cpi_dim = judge_dimension('CPI', cpi_trend)
    print(f"   PPI: {ppi_dim['details']}")
    print(f"   CPI: {cpi_dim['details']}")
    
    if ppi_dim['ma'] > 1.0 and cpi_dim['ma'] > 0.5:
        inf_status = '全面通胀'
    elif ppi_dim['ma'] > 1.0 and cpi_dim['ma'] < 0:
        inf_status = '结构性通胀'
    elif ppi_dim['ma'] < -0.5 and cpi_dim['ma'] < -0.5:
        inf_status = '通缩风险'
    elif ppi_dim['ma'] < 0 and cpi_dim['ma'] < 0:
        inf_status = '低通胀'
    else:
        inf_status = '通胀温和'
    
    print(f"   → 通胀状态: {inf_status}")
    
    # 4. 综合状态判定
    print("\n4. 综合状态判定：")
    print(f"   流动性: {liq_status}")
    print(f"   增长: {growth_status}")
    print(f"   通胀: {inf_status}")
    
    # 状态映射（简化版）
    growth_up = '扩张' in growth_status or '加速' in growth_status
    growth_down = '收缩' in growth_status or '恶化' in growth_status
    inf_high = '通胀' in inf_status and '低' not in inf_status and '温和' not in inf_status
    inf_low = '低通胀' in inf_status or '通缩' in inf_status or '温和' in inf_status
    liq_loose = '宽' in liq_status and '紧' not in liq_status
    liq_tight = '紧' in liq_status and '宽' not in liq_status
    
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
    confidences = []
    if liq_status != 'unknown':
        confidences.append(0.8)
    else:
        confidences.append(0.3)
    
    if '分歧' not in growth_status:
        confidences.append(0.9)
    else:
        confidences.append(0.6)
    
    confidences.append(0.85)
    
    avg_conf = np.mean(confidences)
    
    print(f"\n   → 最终判定: {final_state}")
    print(f"   → 置信度: {avg_conf:.2f}")
    
    # 5. 状态含义解读
    print("\n5. 状态含义：")
    state_meanings = {
        '复苏期': '经济回升，通胀低位，流动性宽松。最佳投资环境，股票>债券。',
        '弱复苏': '经济回升但动能不足，流动性结构性宽松。复苏不稳固，需观察。',
        '过热期': '经济高位，通胀上行，流动性紧缩。政策收紧风险，商品>股票。',
        '紧过热': '经济高位，通胀上行，但信用仍宽松。结构性机会，注意政策转向。',
        '滞胀期': '经济下滑，通胀高位，流动性紧缩。最恶劣组合，现金为王。',
        '弱滞胀': '经济下滑，通胀高位，但货币宽松。政策两难，避险为主。',
        '衰退期': '经济低迷，通胀下行，流动性宽松。等待转机，债券>股票。',
        '宽衰退': '经济低迷，但政策已发力。宽货币紧信用，效果待观察。',
        '过渡态': '宏观状态不明朗，多维度信号冲突。建议观望，等待明确信号。'
    }
    print(f"   {state_meanings.get(final_state, '状态含义待补充')}")

print("\n" + "="*100)
print("报告生成完成")
print("="*100)
