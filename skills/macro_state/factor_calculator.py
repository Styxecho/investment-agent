# skills/macro_state/factor_calculator.py
"""
V7 Factor Calculator - Core computation logic

Implements:
- One-sided HP filter (lambda=129600)
- 36-month rolling Z-score
- PMI absolute zero method
- Adaptive deviation threshold

Internal module - no external script dependencies.
"""

import pandas as pd
import numpy as np
from scipy import linalg
from typing import Dict, Tuple, Optional

# Configuration
LAMBDA_HP = 129600
ZSCORE_WINDOW = 36
MIN_PERIODS = 12

V7_INDICATORS = {
    'CN_IAV_YOY_M': {'category': 'growth', 'hp_filter': True, 'name': '工业增加值同比'},
    'CN_PMI_MFG_M': {'category': 'growth', 'hp_filter': False, 'name': '制造业PMI', 'pmi_type': True},
    'CN_PMI_SVC_M': {'category': 'growth', 'hp_filter': False, 'name': '非制造业PMI', 'pmi_type': True},
    'CN_PMI_COMP_M': {'category': 'growth', 'hp_filter': False, 'name': '综合PMI', 'pmi_type': True},
    'CN_CCPI_YOY_M': {'category': 'inflation', 'hp_filter': True, 'name': '核心CPI同比'},
    'CN_PPI_YOY_M': {'category': 'inflation', 'hp_filter': True, 'name': 'PPI同比'},
    'CN_M2_YOY_M': {'category': 'liquidity', 'hp_filter': True, 'name': 'M2同比'},
    'CN_SFS_YOY_M': {'category': 'liquidity', 'hp_filter': True, 'name': '社融存量同比'},
}


def one_sided_hp_filter(series: pd.Series, lamb: int = LAMBDA_HP) -> Tuple[pd.Series, pd.Series]:
    """One-sided Hodrick-Prescott filter"""
    n = len(series)
    if n < 3:
        return pd.Series(np.nan, index=series.index), pd.Series(np.nan, index=series.index)
    
    I = np.eye(n)
    K = np.zeros((n-2, n))
    for i in range(n-2):
        K[i, i] = 1
        K[i, i+1] = -2
        K[i, i+2] = 1
    
    A = I + lamb * K.T @ K
    
    try:
        trend = linalg.solve(A, series.values, assume_a='pos')
    except:
        trend = linalg.solve(A, series.values)
    
    # Ensure 1-dimensional
    if len(trend.shape) > 1:
        trend = trend.flatten()
    
    trend_series = pd.Series(trend, index=series.index)
    cycle_series = series - trend_series
    
    return cycle_series, trend_series


def rolling_zscore(series: pd.Series, window: int = ZSCORE_WINDOW, min_periods: int = MIN_PERIODS) -> pd.Series:
    """Rolling Z-score"""
    mean = series.rolling(window=window, min_periods=min_periods).mean()
    std = series.rolling(window=window, min_periods=min_periods).std()
    zscore = (series - mean) / std
    return zscore


def compute_pmi_zscore(pmi_series: pd.Series, window: int = ZSCORE_WINDOW, min_periods: int = MIN_PERIODS) -> pd.Series:
    """PMI absolute zero method"""
    deviation = pmi_series - 50
    std = deviation.rolling(window=window, min_periods=min_periods).std()
    zscore = deviation / std
    return zscore


def compute_deviation(zscore_series: pd.Series) -> pd.Series:
    """Deviation = Z - MA3(Z)"""
    ma3 = zscore_series.rolling(window=3, min_periods=1).mean()
    deviation = zscore_series - ma3
    return deviation


def compute_adaptive_threshold(deviation_series: pd.Series, window: int = ZSCORE_WINDOW, min_periods: int = MIN_PERIODS) -> Tuple[pd.Series, pd.Series]:
    """Adaptive threshold: ±1.0 × rolling std"""
    threshold = deviation_series.rolling(window=window, min_periods=min_periods).std()
    upper = threshold
    lower = -threshold
    return upper, lower


def determine_direction(deviation: pd.Series, upper_threshold: pd.Series, lower_threshold: pd.Series) -> pd.Series:
    """Direction determination"""
    # Convert to numpy arrays for safe comparison
    dev_vals = deviation.values
    upper_vals = upper_threshold.values
    lower_vals = lower_threshold.values
    
    # Initialize with '→'
    direction_vals = np.full(len(deviation), '→', dtype='<U1')
    
    # Apply thresholds
    mask_up = dev_vals > upper_vals
    mask_down = dev_vals < lower_vals
    
    direction_vals[mask_up] = '↑'
    direction_vals[mask_down] = '↓'
    
    # Handle NaN values
    direction_vals[np.isnan(dev_vals)] = '→'
    
    return pd.Series(direction_vals, index=deviation.index)


def apply_trend_persistence(raw_direction: pd.Series) -> pd.Series:
    """Trend persistence rules"""
    trend_direction = pd.Series('→', index=raw_direction.index)
    
    for i in range(len(raw_direction)):
        if i == 0:
            trend_direction.iloc[i] = raw_direction.iloc[i] if raw_direction.iloc[i] != '→' else '→'
        else:
            current_raw = raw_direction.iloc[i]
            prev_trend = trend_direction.iloc[i-1]
            
            if prev_trend == '→':
                trend_direction.iloc[i] = current_raw if current_raw != '→' else '→'
            else:
                if current_raw != '→' and current_raw != prev_trend:
                    if i >= 2 and raw_direction.iloc[i-1] == current_raw:
                        trend_direction.iloc[i] = current_raw
                    else:
                        trend_direction.iloc[i] = prev_trend
                elif current_raw == '→':
                    if i >= 2 and raw_direction.iloc[i-1] == '→':
                        trend_direction.iloc[i] = '→'
                    else:
                        trend_direction.iloc[i] = prev_trend
                else:
                    trend_direction.iloc[i] = prev_trend
    
    return trend_direction


class FactorCalculator:
    """V7 Factor Calculator"""
    
    def __init__(self):
        self.indicators = V7_INDICATORS
    
    def calculate_factor(self, series: pd.Series, config: Dict) -> Optional[pd.DataFrame]:
        """Calculate factor for a single indicator"""
        if len(series) < MIN_PERIODS:
            return None
        
        if config.get('pmi_type'):
            # PMI absolute zero method
            zscore = compute_pmi_zscore(series)
            cycle = series - 50
            trend = pd.Series(50, index=series.index)
            filter_method = 'absolute_zero'
            filter_params = '{"base": 50}'
        else:
            # Standard pipeline: HP filter -> Z-score
            cycle, trend = one_sided_hp_filter(series)
            zscore = rolling_zscore(cycle)
            filter_method = 'one_sided_hp'
            filter_params = f'{{"lamb": {LAMBDA_HP}}}'
        
        # Compute deviation and direction
        ma3 = zscore.rolling(window=3, min_periods=1).mean()
        deviation = compute_deviation(zscore)
        upper_threshold, lower_threshold = compute_adaptive_threshold(deviation)
        raw_direction = determine_direction(deviation, upper_threshold, lower_threshold)
        trend_direction = apply_trend_persistence(raw_direction)
        
        # Compute threshold (absolute value)
        threshold = upper_threshold.round(4)
        
        # Build result DataFrame - ensure 1-dimensional data
        result = pd.DataFrame({
            'indicator_code': str(series.name) if hasattr(series, 'name') and series.name is not None else 'unknown',
            'publish_date': series.index.strftime('%Y%m%d').tolist(),
            'factor_type': 'level',
            'factor_value': zscore.round(4).tolist(),
            'raw_value': series.round(4).tolist(),
            'cycle_value': cycle.round(4).tolist(),
            'trend_value': trend.round(4).tolist(),
            'deviation': deviation.round(4).tolist(),
            'ma3_z': ma3.round(4).tolist(),
            'threshold': threshold.round(4).tolist(),
            'raw_direction': raw_direction.tolist(),
            'trend_direction': trend_direction.tolist(),
            'zscore_window': ZSCORE_WINDOW,
            'filter_method': filter_method,
            'filter_params': filter_params,
            'is_winsorized': 0,
            'data_source': 'computed_v7',
        }, index=series.index)
        
        return result
    
    def calculate_all_factors(self, data_dict: Dict) -> Dict[str, pd.DataFrame]:
        """Calculate factors for all indicators"""
        results = {}
        
        for indicator_code, data in data_dict.items():
            if indicator_code not in self.indicators:
                continue
            
            # Convert DataFrame to Series if needed
            if isinstance(data, pd.DataFrame):
                if len(data.columns) == 1:
                    series = data.iloc[:, 0]
                else:
                    series = data['value'] if 'value' in data.columns else data.iloc[:, 0]
                series.name = indicator_code
            else:
                series = data
            
            config = self.indicators[indicator_code]
            result = self.calculate_factor(series, config)
            
            if result is not None:
                results[indicator_code] = result
        
        return results
