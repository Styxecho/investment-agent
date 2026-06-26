#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V7 宏观因子计算流水线
- 单向HP滤波 (λ=129600)
- 36月滚动Z-score
- 自适应偏离度阈值
- PMI绝对零点法
- 存储到 macro_factor_value
"""

import pandas as pd
import numpy as np
import sys
from scipy import linalg

sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
from sqlalchemy import text

# ============================================================
# V7 配置
# ============================================================

LAMBDA_HP = 129600  # 月度数据单向HP滤波参数
ZSCORE_WINDOW = 36  # Z-score滚动窗口
MIN_PERIODS = 12    # 最小样本数

# V7指标配置
V7_INDICATORS = {
    # 增长维度 - 需要HP滤波
    'CN_IAV_YOY_M': {'category': 'growth', 'hp_filter': True, 'name': '工业增加值同比'},
    
    # 增长维度 - PMI绝对零点法 (不HP滤波)
    'CN_PMI_MFG_M': {'category': 'growth', 'hp_filter': False, 'name': '制造业PMI', 'pmi_type': True},
    'CN_PMI_SVC_M': {'category': 'growth', 'hp_filter': False, 'name': '非制造业PMI', 'pmi_type': True},
    'CN_PMI_COMP_M': {'category': 'growth', 'hp_filter': False, 'name': '综合PMI', 'pmi_type': True},
    
    # 通胀维度 - 需要HP滤波
    'CN_CCPI_YOY_M': {'category': 'inflation', 'hp_filter': True, 'name': '核心CPI同比'},
    'CN_PPI_YOY_M': {'category': 'inflation', 'hp_filter': True, 'name': 'PPI同比'},
    
    # 流动性维度 - 需要HP滤波
    'CN_M2_YOY_M': {'category': 'liquidity', 'hp_filter': True, 'name': 'M2同比'},
    'CN_SFS_YOY_M': {'category': 'liquidity', 'hp_filter': True, 'name': '社融存量同比'},
}

# ============================================================
# 核心算法
# ============================================================

def one_sided_hp_filter(series, lamb=LAMBDA_HP):
    """
    单向HP滤波 (One-sided Hodrick-Prescott Filter)
    只使用当前及历史数据，避免未来函数
    
    参数:
        series: pandas Series, 月度频率
        lamb: 平滑参数，月度=129600
    
    返回:
        cycle: 周期项
        trend: 趋势项
    """
    n = len(series)
    if n < 3:
        return pd.Series(np.nan, index=series.index), pd.Series(np.nan, index=series.index)
    
    # 构建矩阵 (标准HP滤波矩阵)
    # I + lamb * K'K，其中K是二阶差分矩阵
    I = np.eye(n)
    K = np.zeros((n-2, n))
    for i in range(n-2):
        K[i, i] = 1
        K[i, i+1] = -2
        K[i, i+2] = 1
    
    A = I + lamb * K.T @ K
    
    # 解线性方程得到趋势项
    try:
        trend = linalg.solve(A, series.values, assume_a='pos')
    except:
        trend = linalg.solve(A, series.values)
    
    trend_series = pd.Series(trend, index=series.index)
    cycle_series = series - trend_series
    
    return cycle_series, trend_series


def rolling_zscore(series, window=ZSCORE_WINDOW, min_periods=MIN_PERIODS):
    """
    滚动Z-score标准化
    Z = (x - rolling_mean) / rolling_std
    """
    mean = series.rolling(window=window, min_periods=min_periods).mean()
    std = series.rolling(window=window, min_periods=min_periods).std()
    zscore = (series - mean) / std
    return zscore


def compute_pmi_zscore(pmi_series, window=ZSCORE_WINDOW, min_periods=MIN_PERIODS):
    """
    PMI绝对零点法: Z = (PMI - 50) / rolling_std(PMI - 50)
    """
    deviation = pmi_series - 50
    std = deviation.rolling(window=window, min_periods=min_periods).std()
    zscore = deviation / std
    return zscore


def compute_deviation(zscore_series):
    """
    计算偏离度: deviation = Z - MA3(Z)
    """
    ma3 = zscore_series.rolling(window=3, min_periods=1).mean()
    deviation = zscore_series - ma3
    return deviation


def compute_adaptive_threshold(deviation_series, window=ZSCORE_WINDOW, min_periods=MIN_PERIODS):
    """
    自适应阈值: ±1.0 × 过去36个月deviation序列的滚动标准差
    返回两个Series: upper_threshold, lower_threshold
    """
    threshold = deviation_series.rolling(window=window, min_periods=min_periods).std()
    upper = threshold
    lower = -threshold
    return upper, lower


def determine_direction(deviation, upper_threshold, lower_threshold):
    """
    方向判定: 
    - deviation > upper_threshold: 上行 (↑)
    - deviation < lower_threshold: 下行 (↓)
    - 否则: 平稳 (→)
    """
    direction = pd.Series('→', index=deviation.index)
    direction[deviation > upper_threshold] = '↑'
    direction[deviation < lower_threshold] = '↓'
    return direction


def apply_trend_persistence(raw_direction):
    """
    趋势持续性规则:
    - 首月: raw_dir ≠ → 则 trend_dir = raw_dir; 否则 →
    - 脱离中性(单次击发): trend_dir=→ 时, raw_dir非中性即翻转
    - 脱离非中性(双重确认): trend_dir=↑/↓ 时, 需连续两个月raw_dir相同才翻转
    """
    trend_direction = pd.Series('→', index=raw_direction.index)
    
    for i in range(len(raw_direction)):
        if i == 0:
            # 首月初始化
            trend_direction.iloc[i] = raw_direction.iloc[i] if raw_direction.iloc[i] != '→' else '→'
        else:
            current_raw = raw_direction.iloc[i]
            prev_trend = trend_direction.iloc[i-1]
            
            if prev_trend == '→':
                # 脱离中性: 单次击发
                if current_raw != '→':
                    trend_direction.iloc[i] = current_raw
                else:
                    trend_direction.iloc[i] = '→'
            else:
                # 脱离非中性: 需要双重确认
                if current_raw != '→' and current_raw != prev_trend:
                    # 检查是否连续两个月
                    if i >= 2 and raw_direction.iloc[i-1] == current_raw:
                        trend_direction.iloc[i] = current_raw
                    else:
                        trend_direction.iloc[i] = prev_trend
                elif current_raw == '→':
                    # 向中性回归: 需要连续两个月→
                    if i >= 2 and raw_direction.iloc[i-1] == '→':
                        trend_direction.iloc[i] = '→'
                    else:
                        trend_direction.iloc[i] = prev_trend
                else:
                    # current_raw == prev_trend
                    trend_direction.iloc[i] = prev_trend
    
    return trend_direction


# ============================================================
# 主计算流程
# ============================================================

def load_indicator_data(indicator_code):
    """从数据库加载指标数据"""
    sql = f"""
    SELECT publish_date, value 
    FROM macro_indicator_value 
    WHERE indicator_code = '{indicator_code}' 
      AND value IS NOT NULL
    ORDER BY publish_date
    """
    df = pd.read_sql(sql, engine)
    df['publish_date'] = pd.to_datetime(df['publish_date'], format='%Y%m%d')
    df = df.set_index('publish_date')['value'].sort_index()
    return df


def process_indicator(indicator_code, config):
    """处理单个指标，计算因子值"""
    print(f"\n[INFO] Processing {indicator_code} ({config['name']})")
    
    # 加载数据
    series = load_indicator_data(indicator_code)
    if len(series) < MIN_PERIODS:
        print(f"  [WARN] Insufficient data: {len(series)} records, need {MIN_PERIODS}")
        return None
    
    print(f"  Data range: {series.index[0].strftime('%Y-%m')} ~ {series.index[-1].strftime('%Y-%m')}, {len(series)} records")
    
    # 根据指标类型选择计算方法
    if config.get('pmi_type'):
        # PMI绝对零点法
        zscore = compute_pmi_zscore(series)
        cycle = series - 50  # PMI的cycle就是偏离50的程度
        trend = pd.Series(50, index=series.index)  # 趋势项固定为50
    else:
        # 标准流水线: HP滤波 -> Z-score
        cycle, trend = one_sided_hp_filter(series)
        zscore = rolling_zscore(cycle)
    
    # 计算偏离度
    deviation = compute_deviation(zscore)
    
    # 计算自适应阈值
    upper_threshold, lower_threshold = compute_adaptive_threshold(deviation)
    
    # 原始方向
    raw_direction = determine_direction(deviation, upper_threshold, lower_threshold)
    
    # 趋势方向 (应用持续性规则)
    trend_direction = apply_trend_persistence(raw_direction)
    
    # 构建结果DataFrame
    result = pd.DataFrame({
        'indicator_code': indicator_code,
        'publish_date': series.index.strftime('%Y%m%d'),
        'factor_type': 'level',
        'factor_value': zscore.round(4),
        'raw_value': series.round(4),
        'cycle_value': cycle.round(4),
        'trend_value': trend.round(4),
        'zscore_window': ZSCORE_WINDOW,
        'filter_method': 'one_sided_hp' if not config.get('pmi_type') else 'absolute_zero',
        'filter_params': f'{{"lamb": {LAMBDA_HP}}}' if not config.get('pmi_type') else '{"base": 50}',
        'is_winsorized': 0,
        'data_source': 'computed_v7',
    })
    
    # 添加方向信息到额外字段 (存储在filter_params或单独列)
    result['deviation'] = deviation.round(4)
    result['raw_direction'] = raw_direction
    result['trend_direction'] = trend_direction
    result['threshold'] = upper_threshold.round(4)
    
    return result


def store_factors(factor_df):
    """存储因子值到数据库"""
    if factor_df is None or len(factor_df) == 0:
        return 0
    
    # 选择需要存储的列
    store_cols = [
        'indicator_code', 'publish_date', 'factor_type', 'factor_value',
        'raw_value', 'cycle_value', 'trend_value', 'zscore_window',
        'filter_method', 'filter_params', 'is_winsorized', 'data_source',
        'deviation', 'raw_direction', 'trend_direction', 'threshold'
    ]
    
    store_df = factor_df[store_cols].copy()
    
    # 删除NaN值
    store_df = store_df.dropna(subset=['factor_value'])
    
    if len(store_df) == 0:
        return 0
    
    store_df.to_sql('macro_factor_value', engine, if_exists='append', index=False)
    return len(store_df)


def main():
    print("=" * 60)
    print("V7 宏观因子计算流水线")
    print("=" * 60)
    print(f"HP滤波参数: λ={LAMBDA_HP}")
    print(f"Z-score窗口: {ZSCORE_WINDOW}个月")
    print(f"最小样本数: {MIN_PERIODS}")
    print()
    
    total_records = 0
    
    for indicator_code, config in V7_INDICATORS.items():
        result = process_indicator(indicator_code, config)
        if result is not None:
            count = store_factors(result)
            total_records += count
            print(f"  [OK] Stored {count} factor records")
            
            # 显示最近3个月的方向
            recent = result[['publish_date', 'raw_direction', 'trend_direction']].tail(3)
            print(f"  Recent directions:")
            for _, row in recent.iterrows():
                print(f"    {row['publish_date']}: raw={row['raw_direction']}, trend={row['trend_direction']}")
    
    print()
    print("=" * 60)
    print(f"[DONE] Total stored: {total_records} records")
    print("=" * 60)


if __name__ == '__main__':
    main()
