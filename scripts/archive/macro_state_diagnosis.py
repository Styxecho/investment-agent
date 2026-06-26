#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
宏观状态诊断引擎
基于三维框架：流动性(货币×信用) × 增长 × 通胀
输出：Markdown格式诊断报告
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'D:\Study\Project\investment-agent')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from datetime import datetime
import json

engine = create_engine('sqlite:///D:/Study/Project/investment-agent/data_external/db/external_data.db')

# ============================================================================
# 配置
# ============================================================================
TREND_WINDOW = 3  # 3个月趋势窗口

# 指标映射
INDICATORS = {
    'growth': {
        'pmi': 'CN_PMI_MFG_M',
        'iav': 'CN_IAV_YOY_M'
    },
    'inflation': {
        'ppi': 'CN_PPI_YOY_M',
        'cpi': 'CN_CPI_YOY_M'
    },
    'liquidity': {
        'money': 'm1m2_scissor',  # 需要计算
        'credit': 'CN_SFS_YOY_M'
    }
}

# 状态定义
STATES = {
    'liquidity': {
        ('宽松', '宽松'): '双宽',
        ('宽松', '紧缩'): '宽货币紧信用',
        ('紧缩', '宽松'): '紧货币宽信用',
        ('紧缩', '紧缩'): '双紧'
    },
    'cycle': {
        '复苏期': '流动性宽松 + 增长扩张 + 低通胀',
        '弱复苏': '流动性结构性宽松 + 增长扩张减速 + 低通胀',
        '过热期': '流动性紧缩 + 增长扩张 + 通胀上行',
        '紧过热': '紧货币宽信用 + 增长扩张 + 结构性通胀',
        '滞胀期': '流动性紧缩 + 增长收缩 + 通胀上行',
        '弱滞胀': '宽货币紧信用 + 增长收缩 + 通胀上行',
        '衰退期': '流动性宽松 + 增长收缩 + 低通胀',
        '宽衰退': '宽货币紧信用 + 增长收缩筑底 + 低通胀'
    }
}

# ============================================================================
# 数据读取
# ============================================================================
def load_macro_data(start_date='20160101', end_date='20261231'):
    """读取宏观因子数据"""
    
    # 读取所有需要的指标
    all_indicators = [
        'CN_PMI_MFG_M', 'CN_PPI_YOY_M', 'CN_CPI_YOY_M',
        'CN_M1_YOY_M', 'CN_M2_YOY_M', 'CN_SFS_YOY_M', 'CN_IAV_YOY_M'
    ]
    
    data = []
    for ind_code in all_indicators:
        sql = f"""
        SELECT publish_date, factor_value
        FROM macro_factor_value
        WHERE indicator_code = '{ind_code}'
            AND factor_type = 'level'
            AND publish_date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY publish_date
        """
        df = pd.read_sql(sql, engine)
        df['publish_date'] = pd.to_datetime(df['publish_date'].astype(str))
        df['year_month'] = df['publish_date'].dt.strftime('%Y%m')
        df = df.rename(columns={'factor_value': ind_code})
        df = df[['year_month', ind_code]]
        data.append(df)
    
    # 合并
    from functools import reduce
    macro_df = reduce(lambda left, right: pd.merge(left, right, on='year_month', how='outer'), data)
    macro_df = macro_df.sort_values('year_month').reset_index(drop=True)
    
    # 计算M1-M2剪刀差
    macro_df['m1m2_scissor'] = macro_df['CN_M1_YOY_M'] - macro_df['CN_M2_YOY_M']
    
    return macro_df

# ============================================================================
# 趋势计算
# ============================================================================
def calculate_trend(series, window=3):
    """
    计算趋势状态
    
    返回：{
        'direction': 'up'/'down'/'flat',
        'strength': 'accelerating'/'decelerating'/'stable',
        'ma_value': 移动平均值,
        'slope': 斜率
    }
    """
    if len(series) < window:
        return None
    
    # 移动平均
    ma = series.rolling(window=window).mean()
    ma_current = ma.iloc[-1]
    
    if pd.isna(ma_current):
        return None
    
    # 斜率（最近2个月的变化）
    if len(series) >= 2:
        slope = series.iloc[-1] - series.iloc[-2]
    else:
        slope = 0
    
    # 方向
    if ma_current > 0.5:
        direction = 'up'
    elif ma_current < -0.5:
        direction = 'down'
    else:
        direction = 'flat'
    
    # 强度（加速/减速/稳定）
    if len(series) >= window + 1:
        ma_prev = ma.iloc[-2]
        if not pd.isna(ma_prev):
            if ma_current > ma_prev + 0.1:
                strength = 'accelerating'
            elif ma_current < ma_prev - 0.1:
                strength = 'decelerating'
            else:
                strength = 'stable'
        else:
            strength = 'stable'
    else:
        strength = 'stable'
    
    return {
        'direction': direction,
        'strength': strength,
        'ma_value': round(ma_current, 3),
        'slope': round(slope, 3),
        'current_value': round(series.iloc[-1], 3)
    }

# ============================================================================
# 维度判定
# ============================================================================
def judge_liquidity(m1m2_series, sfs_series):
    """判定流动性状态（货币 × 信用）"""
    
    m1m2_trend = calculate_trend(m1m2_series, TREND_WINDOW)
    sfs_trend = calculate_trend(sfs_series, TREND_WINDOW)
    
    if m1m2_trend is None or sfs_trend is None:
        return {
            'money_status': 'unknown',
            'credit_status': 'unknown',
            'combo': 'unknown',
            'status': 'unknown',
            'm1m2_trend': None,
            'sfs_trend': None,
            'confidence': 0
        }
    
    # 货币状态（M1-M2剪刀差）
    if m1m2_trend['direction'] == 'up' and m1m2_trend['strength'] in ['accelerating', 'stable']:
        money = '宽松'
    elif m1m2_trend['direction'] == 'down' and m1m2_trend['strength'] in ['decelerating', 'stable']:
        money = '紧缩'
    else:
        money = '中性'
    
    # 信用状态（社融增速）
    if sfs_trend['direction'] == 'up' and sfs_trend['strength'] in ['accelerating', 'stable']:
        credit = '宽松'
    elif sfs_trend['direction'] == 'down' and sfs_trend['strength'] in ['decelerating', 'stable']:
        credit = '紧缩'
    else:
        credit = '中性'
    
    # 组合状态
    if money == '中性' or credit == '中性':
        combo = f'{money}货币{credit}信用'
        status = '结构性宽松' if (money == '宽松' or credit == '宽松') else '结构性紧缩'
    else:
        combo = f'{money}货币{credit}信用'
        status = STATES['liquidity'].get((money, credit), combo)
    
    return {
        'money_status': money,
        'credit_status': credit,
        'combo': combo,
        'status': status,
        'm1m2_trend': m1m2_trend,
        'sfs_trend': sfs_trend,
        'confidence': 0.8 if (money != '中性' and credit != '中性') else 0.6
    }

def judge_growth(pmi_series, iav_series):
    """判定增长状态"""
    
    pmi_trend = calculate_trend(pmi_series, TREND_WINDOW)
    iav_trend = calculate_trend(iav_series, TREND_WINDOW)
    
    if pmi_trend is None:
        return {'status': 'unknown', 'confidence': 0}
    
    # 综合判断（PMI权重60%，IAV权重40%）
    pmi_weight = 0.6
    iav_weight = 0.4 if iav_trend is not None else 0
    
    weighted_ma = pmi_trend['ma_value'] * pmi_weight
    if iav_trend:
        weighted_ma += iav_trend['ma_value'] * iav_weight
        weighted_ma /= (pmi_weight + iav_weight)
    
    # 状态判定
    if weighted_ma > 0.5:
        if pmi_trend['strength'] == 'accelerating':
            status = '扩张加速'
        elif pmi_trend['strength'] == 'decelerating':
            status = '扩张减速'
        else:
            status = '平稳扩张'
    elif weighted_ma < -0.5:
        if pmi_trend['strength'] == 'accelerating':
            status = '收缩筑底'
        elif pmi_trend['strength'] == 'decelerating':
            status = '收缩恶化'
        else:
            status = '收缩趋稳'
    else:
        status = '增长 uncertain'
    
    # 分歧检测
    if iav_trend and pmi_trend['direction'] != iav_trend['direction']:
        divergence = True
        status += '（分歧：PMI与工业增加�?方向不一致）'
    else:
        divergence = False
    
    return {
        'status': status,
        'weighted_ma': round(weighted_ma, 3),
        'pmi_trend': pmi_trend,
        'iav_trend': iav_trend,
        'divergence': divergence,
        'confidence': 0.7 if divergence else 0.9
    }

def judge_inflation(ppi_series, cpi_series):
    """判定通胀状态"""
    
    ppi_trend = calculate_trend(ppi_series, TREND_WINDOW)
    cpi_trend = calculate_trend(cpi_series, TREND_WINDOW)
    
    if ppi_trend is None:
        return {'status': 'unknown', 'confidence': 0}
    
    # PPI为主导指标（领先性更强）
    ppi_ma = ppi_trend['ma_value']
    cpi_ma = cpi_trend['ma_value'] if cpi_trend else 0
    
    # 状态判定
    if ppi_ma > 1.0 and cpi_ma > 0.5:
        status = '全面通胀'
    elif ppi_ma > 1.0 and cpi_ma < 0:
        status = '结构性通胀'
    elif ppi_ma < -0.5 and cpi_ma < -0.5:
        status = '通缩风险'
    elif ppi_ma < 0 and cpi_ma < 0:
        status = '低通胀'
    else:
        status = '通胀温和'
    
    return {
        'status': status,
        'ppi_trend': ppi_trend,
        'cpi_trend': cpi_trend,
        'confidence': 0.85
    }

# ============================================================================
# 状态综合
# ============================================================================
def determine_cycle_state(liquidity, growth, inflation):
    """
    综合三维判断，输出周期状态
    """
    
    # 简化映射（8种核心状态）
    money = liquidity['money_status']
    credit = liquidity['credit_status']
    growth_status = growth['status']
    inflation_status = inflation['status']
    
    # 增长方向
    growth_up = '扩张' in growth_status or '加速' in growth_status
    growth_down = '收缩' in growth_status or '恶化' in growth_status
    
    # 通胀方向
    inflation_high = '通胀' in inflation_status and '低' not in inflation_status and '温和' not in inflation_status
    inflation_low = '低通胀' in inflation_status or '通缩' in inflation_status or '温和' in inflation_status
    
    # 流动性方向
    liquidity_loose = money == '宽松' or credit == '宽松'
    liquidity_tight = money == '紧缩' and credit == '紧缩'
    
    # 状态判定
    if growth_up and inflation_low and liquidity_loose:
        state = '复苏期'
    elif growth_up and inflation_low and not liquidity_loose:
        state = '弱复苏'
    elif growth_up and inflation_high and liquidity_tight:
        state = '过热期'
    elif growth_up and inflation_high and not liquidity_tight:
        state = '紧过热'
    elif growth_down and inflation_high and liquidity_tight:
        state = '滞胀期'
    elif growth_down and inflation_high and not liquidity_tight:
        state = '弱滞胀'
    elif growth_down and inflation_low and liquidity_loose:
        state = '衰退期'
    elif growth_down and inflation_low and not liquidity_loose:
        state = '宽衰退'
    else:
        state = '过渡态'
    
    # 置信度
    confidences = [liquidity['confidence'], growth['confidence'], inflation['confidence']]
    avg_confidence = np.mean(confidences)
    
    # 如果增长分歧，降低置信度
    if growth['divergence']:
        avg_confidence *= 0.7
    
    return {
        'state': state,
        'confidence': round(avg_confidence, 2),
        'liquidity': liquidity,
        'growth': growth,
        'inflation': inflation
    }

# ============================================================================
# 报告生成
# ============================================================================
def generate_report(year_month, state_result, macro_df):
    """生成Markdown格式报告"""
    
    report = []
    
    # 标题
    report.append(f"# 宏观状态诊断报告\n")
    report.append(f"**报告月份**：{year_month}")
    report.append(f"**诊断周期**：过去3个月趋势\n")
    
    # 核心结论
    report.append(f"## 一、核心结论\n")
    report.append(f"**当前状态**：{state_result['state']}")
    report.append(f"**置信度**：{state_result['confidence']*100:.0f}%\n")
    
    # 三维定位
    report.append(f"## 二、三维定位\n")
    
    # 流动性
    liq = state_result['liquidity']
    report.append(f"### 2.1 流动性维度：{liq['status']}\n")
    report.append(f"- 货币（M1-M2剪刀差）：{liq['money_status']}（MA3={liq['m1m2_trend']['ma_value']}, 斜率={liq['m1m2_trend']['slope']}）")
    report.append(f"- 信用（社融增速）：{liq['credit_status']}（MA3={liq['sfs_trend']['ma_value'] if liq['sfs_trend'] else 'N/A'}, 斜率={liq['sfs_trend']['slope'] if liq['sfs_trend'] else 'N/A'}）\n")
    
    # 增长
    gr = state_result['growth']
    report.append(f"### 2.2 增长维度：{gr['status']}\n")
    report.append(f"- PMI制造业：MA3={gr['pmi_trend']['ma_value']}, 斜率={gr['pmi_trend']['slope']}, 方向={gr['pmi_trend']['direction']}")
    if gr['iav_trend']:
        report.append(f"- 工业增加值：MA3={gr['iav_trend']['ma_value']}, 斜率={gr['iav_trend']['slope']}, 方向={gr['iav_trend']['direction']}")
    if gr['divergence']:
        report.append(f"- **⚠️ 分歧警告**：PMI与工业增加值趋势不一致\n")
    
    # 通胀
    inf = state_result['inflation']
    report.append(f"### 2.3 通胀维度：{inf['status']}\n")
    report.append(f"- PPI：MA3={inf['ppi_trend']['ma_value']}, 斜率={inf['ppi_trend']['slope']}")
    if inf['cpi_trend']:
        report.append(f"- CPI：MA3={inf['cpi_trend']['ma_value']}, 斜率={inf['cpi_trend']['slope']}\n")
    
    return '\n'.join(report)

# ============================================================================
# 主程序
# ============================================================================
def main():
    print("="*80)
    print("宏观状态诊断引擎")
    print("="*80)
    
    # 加载数据
    print("\n[1/4] 加载宏观数据...")
    macro_df = load_macro_data()
    print(f"数据范围：{macro_df['year_month'].min()} 至 {macro_df['year_month'].max()}")
    print(f"数据条数：{len(macro_df)}")
    
    # 逐月计算状态（从第3个月开始）
    print("\n[2/4] 计算月度状态...")
    states_history = []
    
    for i in range(2, len(macro_df)):
        current_month = macro_df.iloc[i]['year_month']
        
        # 获取过去3个月数据
        window_df = macro_df.iloc[max(0, i-2):i+1]
        
        # 计算各维度
        liquidity = judge_liquidity(
            window_df['m1m2_scissor'],
            window_df['CN_SFS_YOY_M']
        )
        
        growth = judge_growth(
            window_df['CN_PMI_MFG_M'],
            window_df['CN_IAV_YOY_M']
        )
        
        inflation = judge_inflation(
            window_df['CN_PPI_YOY_M'],
            window_df['CN_CPI_YOY_M']
        )
        
        # 综合状态
        state = determine_cycle_state(liquidity, growth, inflation)
        state['year_month'] = current_month
        
        states_history.append(state)
    
    print(f"计算完成：{len(states_history)} 个月")
    
    # 英文映射（用于控制台输出避免编码问题）
    en_map = {
        '复苏期': 'Recovery', '弱复苏': 'WeakRecovery', '过热期': 'Overheat',
        '紧过热': 'TightOverheat', '滞胀期': 'Stagflation', '弱滞胀': 'WeakStagflation',
        '衰退期': 'Recession', '宽衰退': 'WideRecession', '过渡态': 'Transition',
        'unknown': 'Unknown',
        '双宽': 'DualLoose', '宽货币紧信用': 'LooseMoneyTightCredit',
        '紧货币宽信用': 'TightMoneyLooseCredit', '双紧': 'DualTight',
        '结构性宽松': 'StructLoose', '结构性紧缩': 'StructTight',
        '扩张加速': 'ExpAccel', '扩张减速': 'ExpDecel', '平稳扩张': 'ExpStable',
        '收缩筑底': 'ContrBottom', '收缩恶化': 'ContrWorsen', '收缩趋稳': 'ContrStable',
        '增长 uncertain': 'GrowthUncertain',
        '全面通胀': 'HighInflation', '结构性通胀': 'StructInflation',
        '通缩风险': 'DeflationRisk', '低通胀': 'LowInflation', '通胀温和': 'MildInflation'
    }
    
    # 输出历史状态表（英文以避免编码问题）
    print("\n[3/4] Historical States Summary:")
    print("-"*100)
    print(f"{'Month':<10} {'State':<15} {'Conf':<8} {'Liquidity':<25} {'Growth':<20} {'Inflation':<15}")
    print("-"*100)
    
    for s in states_history:
        state_en = en_map.get(s['state'], s['state'])
        liq_en = en_map.get(s['liquidity']['status'], s['liquidity']['status'])
        gr_en = en_map.get(s['growth']['status'], s['growth']['status'])
        inf_en = en_map.get(s['inflation']['status'], s['inflation']['status'])
        print(f"{s['year_month']:<10} {state_en:<15} {s['confidence']:<8.0%} "
              f"{liq_en:<25} {gr_en:<20} {inf_en:<15}")
    
    # 生成报告（所有历史月份）
    print("\n[4/4] Generating reports...")
    
    # 保存历史状态
    history_df = pd.DataFrame([{
        'year_month': s['year_month'],
        'state': s['state'],
        'confidence': s['confidence'],
        'liquidity': s['liquidity']['status'],
        'growth': s['growth']['status'],
        'inflation': s['inflation']['status']
    } for s in states_history])
    
    history_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_history.csv'
    history_df.to_csv(history_path, index=False, encoding='utf-8-sig')
    print(f"History saved: {history_path}")
    
    # 生成切片1 (2016-2017) 的详细报告
    slice1_states = [s for s in states_history if s['year_month'] >= '201607' and s['year_month'] <= '201712']
    if slice1_states:
        report_lines = []
        report_lines.append("# 宏观状态诊断报告：切片1 (2016-2017)\n")
        report_lines.append("## 状态演变时间线\n")
        
        for s in slice1_states:
            report_lines.append(f"### {s['year_month']}")
            report_lines.append(f"- **状态**: {s['state']} (置信度: {s['confidence']:.0%})")
            report_lines.append(f"- **流动性**: {s['liquidity']['status']}")
            report_lines.append(f"- **增长**: {s['growth']['status']}")
            report_lines.append(f"- **通胀**: {s['inflation']['status']}\n")
        
        slice1_report = '\n'.join(report_lines)
        
        report_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_slice1_2016_2017.md'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(slice1_report)
        
        print(f"\nSlice 1 report saved: {report_path}")
        
        # 打印前几个月的预览
        print("\nPreview (first 6 months):")
        for s in slice1_states[:6]:
            print(f"{s['year_month']}: {s['state']} (conf: {s['confidence']:.0%})")
    
    print("\n" + "="*80)
    print("Analysis complete!")
    print("="*80)

if __name__ == '__main__':
    main()
