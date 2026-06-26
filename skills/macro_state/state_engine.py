# skills/macro_state/state_engine.py
"""
V8 State Engine - Macro state synthesis logic

Implements:
- Growth dimension synthesis (PMI + IAV + SVC PMI)
- Inflation dimension synthesis (Core CPI + PPI)
- Liquidity dimension synthesis V8 (M2 + SFS + OMO/DR007 price direction)
- 10-priority regime mapping
- 4-type WARNING detection

V8 Updates:
- Replaced price veto with price-direction arbitration
- Added structural arbitration using non-manufacturing PMI
- OMO intent detection and transmission validation

Internal module - no external script dependencies.
"""

import pandas as pd
import numpy as np
import json
from typing import Dict, List, Tuple, Optional

# Constants
ZSCORE_WINDOW = 36
FISCAL_INTERFERENCE_STD = 2.0

# V8 Liquidity Constants
OMO_INTENT_WINDOW_MONTHS = 6
OMO_INTENT_THRESHOLD = 0.10  # 10bp
OMO_INTENT_EXTEND_WINDOW = 12
SMA_WINDOW = 20
DIFF_SPAN = 5
TREND_CONFIRM_DAYS = 5
OMO_MUTATION_THRESHOLD = 0.05  # 5bp
LEAD_LAG_TOLERANCE_DAYS = 20


class StateEngine:
    """V8宏观状态合成引擎"""
    
    def __init__(self):
        pass
    
    def compute_growth_state(self, pmi_raw: float, pmi_dir: str, 
                            iav_raw: Optional[float], iav_cycle: Optional[float], 
                            iav_dir: str, svc_raw: Optional[float] = None) -> Tuple[str, str, str, bool]:
        """
        增长维度合成
        返回: (level, direction, state, svc_arbitration)
        """
        pmi_level = '扩张' if pmi_raw >= 50 else '收缩'
        
        if iav_cycle is None or np.isnan(iav_cycle):
            iav_level = 'N/A'
        else:
            iav_level = '扩张' if iav_cycle >= 0 else '收缩'
        
        # 水平合成
        if iav_level == 'N/A':
            growth_level = pmi_level
            growth_dir = pmi_dir
        elif pmi_level == iav_level:
            growth_level = pmi_level
            if pmi_dir == iav_dir:
                growth_dir = pmi_dir
            elif pmi_dir == '→' or iav_dir == '→':
                growth_dir = pmi_dir if iav_dir == '→' else iav_dir
            else:
                growth_dir = '→'
        elif pmi_level == '扩张' and iav_level == '收缩':
            growth_level = '扩张' if pmi_dir == '↑' else '中性'
            growth_dir = pmi_dir
        elif pmi_level == '收缩' and iav_level == '扩张':
            growth_level = '收缩' if pmi_dir == '↓' else '中性'
            growth_dir = pmi_dir
        else:
            growth_level = '中性'
            growth_dir = '→'
        
        # V8: 结构性防误判仲裁（非制造业PMI）
        svc_arbitration = False
        if growth_level == '收缩' and svc_raw is not None and svc_raw > 53:
            growth_level = '中性'
            svc_arbitration = True
        
        # 方向映射：箭头→文字
        dir_map = {'↑': '上行', '↓': '下行', '→': '平稳'}
        growth_state = f"{growth_level}{dir_map[growth_dir]}"
        
        return growth_level, growth_dir, growth_state, svc_arbitration
    
    def compute_inflation_state(self, ccpi_raw: float, ccpi_dir: str, 
                               ppi_dir: str) -> Tuple[str, str, str, bool]:
        """
        通胀维度合成
        返回: (level, direction, state, cost_divergence)
        """
        if ccpi_raw > 3:
            inf_level = '高通胀'
        elif ccpi_raw >= 1:
            inf_level = '温和通胀'
        else:
            inf_level = '低通胀'
        
        # 方向合成
        if ccpi_dir == ppi_dir:
            inf_dir = ccpi_dir
        elif ccpi_dir == '→' or ppi_dir == '→':
            inf_dir = ccpi_dir if ppi_dir == '→' else ppi_dir
        else:
            inf_dir = '→'
        
        dir_map = {'↑': '上行', '↓': '下行', '→': '平稳'}
        inf_state = f"{inf_level}{dir_map[inf_dir]}"
        cost_divergence = (ccpi_dir == '↑' and ppi_dir == '↓') or (ccpi_dir == '↓' and ppi_dir == '↑')
        
        return inf_level, inf_dir, inf_state, cost_divergence
    
    # ==================== V8 Liquidity Direction ====================
    
    def detect_omo_intent(self, omo_series: pd.Series, current_date) -> str:
        """
        识别央行意图
        
        Returns: 'tighten' | 'ease' | 'neutral'
        """
        if omo_series is None or len(omo_series) == 0:
            return 'neutral'
        
        # 规则1: 6个月净变化
        current_omo = omo_series.asof(current_date)
        if current_omo is None or np.isnan(current_omo):
            return 'neutral'
        
        # 找6个月前的日期
        six_month_ago = current_date - pd.DateOffset(months=OMO_INTENT_WINDOW_MONTHS)
        past_omo = omo_series.asof(six_month_ago)
        
        if past_omo is None or np.isnan(past_omo):
            # 尝试找最早的可用值
            past_omo = omo_series.iloc[0]
        
        net_change = current_omo - past_omo
        
        if net_change > OMO_INTENT_THRESHOLD:
            intent = 'tighten'
        elif net_change < -OMO_INTENT_THRESHOLD:
            intent = 'ease'
        else:
            intent = 'neutral'
        
        # 规则2: 若6个月内有任何下调，终止上调周期
        if intent == 'tighten':
            window_data = omo_series[omo_series.index <= current_date]
            window_data = window_data[window_data.index >= six_month_ago]
            if len(window_data) >= 2:
                diffs = window_data.diff().dropna()
                if any(diffs < 0):
                    intent = 'neutral'
        
        # 规则3: 延长观察窗
        if intent == 'neutral':
            twelve_month_ago = current_date - pd.DateOffset(months=OMO_INTENT_EXTEND_WINDOW)
            window_12m = omo_series[omo_series.index <= current_date]
            window_12m = window_12m[window_12m.index >= twelve_month_ago]
            
            if len(window_12m) >= 2:
                change_12m = window_12m.iloc[-1] - window_12m.iloc[0]
                two_year_mean = omo_series.tail(24).mean() if len(omo_series) >= 24 else omo_series.mean()
                
                if change_12m > OMO_INTENT_THRESHOLD and current_omo > two_year_mean:
                    intent = 'tighten'
                elif change_12m < -OMO_INTENT_THRESHOLD and current_omo < two_year_mean:
                    intent = 'ease'
        
        return intent
    
    def find_breakpoints(self, daily_series: pd.Series, current_date) -> List[Dict]:
        """
        识别趋势拐点
        
        Returns: [{date, direction}, ...]
        """
        if daily_series is None or len(daily_series) == 0:
            return []
        
        # 只取近12个月的数据
        twelve_month_ago = current_date - pd.DateOffset(months=OMO_INTENT_EXTEND_WINDOW)
        recent_data = daily_series[(daily_series.index >= twelve_month_ago) & (daily_series.index <= current_date)]
        
        if len(recent_data) < SMA_WINDOW + DIFF_SPAN + TREND_CONFIRM_DAYS:
            return []
        
        breakpoints = []
        
        # 计算SMA20
        sma = recent_data.rolling(window=SMA_WINDOW, min_periods=SMA_WINDOW).mean()
        
        # 计算5日差分
        diff = sma.diff(periods=DIFF_SPAN)
        
        # 连续5日同号确认趋势
        for i in range(len(diff) - TREND_CONFIRM_DAYS + 1):
            if i < SMA_WINDOW + DIFF_SPAN - 1:
                continue
            
            window_diff = diff.iloc[i:i+TREND_CONFIRM_DAYS]
            
            # 检查是否连续同号
            if all(window_diff > 0) and window_diff.iloc[0] > 0:
                # 检查是否是趋势形成的第一天（前一日不是同号）
                if i == 0 or not (diff.iloc[i-1] > 0):
                    bp_date = diff.index[i]
                    # OMO突变检查
                    if len(recent_data) > 0:
                        day_data = recent_data.loc[bp_date] if bp_date in recent_data.index else None
                        if day_data is not None:
                            prev_day = recent_data.index[recent_data.index.get_loc(bp_date) - 1] if bp_date in recent_data.index else None
                            if prev_day is not None and prev_day in recent_data.index:
                                day_change = day_data - recent_data.loc[prev_day]
                                if abs(day_change) >= OMO_MUTATION_THRESHOLD:
                                    # 突变跳过SMA确认
                                    breakpoints.append({
                                        'date': bp_date,
                                        'direction': 'up' if day_change > 0 else 'down'
                                    })
                                    continue
                    
                    breakpoints.append({
                        'date': bp_date,
                        'direction': 'up'
                    })
            elif all(window_diff < 0) and window_diff.iloc[0] < 0:
                if i == 0 or not (diff.iloc[i-1] < 0):
                    bp_date = diff.index[i]
                    # OMO突变检查
                    if len(recent_data) > 0:
                        day_data = recent_data.loc[bp_date] if bp_date in recent_data.index else None
                        if day_data is not None:
                            prev_day = recent_data.index[recent_data.index.get_loc(bp_date) - 1] if bp_date in recent_data.index else None
                            if prev_day is not None and prev_day in recent_data.index:
                                day_change = day_data - recent_data.loc[prev_day]
                                if abs(day_change) >= OMO_MUTATION_THRESHOLD:
                                    breakpoints.append({
                                        'date': bp_date,
                                        'direction': 'up' if day_change > 0 else 'down'
                                    })
                                    continue
                    
                    breakpoints.append({
                        'date': bp_date,
                        'direction': 'down'
                    })
        
        return breakpoints
    
    def compare_lead_lag(self, omo_bps: List[Dict], dr007_bps: List[Dict]) -> str:
        """
        比较OMO和DR007的先后关系
        
        Returns: 'omo_lead' | 'dr007_lead' | 'sync' | 'no_trend'
        """
        if not omo_bps and not dr007_bps:
            return 'no_trend'
        
        if not omo_bps:
            return 'dr007_lead'
        
        if not dr007_bps:
            return 'omo_lead'
        
        # 找最近一次同向突破点
        omo_latest = omo_bps[-1]
        dr007_latest = dr007_bps[-1]
        
        # 如果方向相反，传导受阻
        if omo_latest['direction'] != dr007_latest['direction']:
            return 'no_trend'
        
        # 比较日期
        omo_date = pd.Timestamp(omo_latest['date'])
        dr007_date = pd.Timestamp(dr007_latest['date'])
        
        if omo_date < dr007_date - pd.Timedelta(days=LEAD_LAG_TOLERANCE_DAYS):
            return 'omo_lead'
        elif dr007_date < omo_date - pd.Timedelta(days=LEAD_LAG_TOLERANCE_DAYS):
            return 'dr007_lead'
        else:
            return 'sync'
    
    def validate_transmission(self, intent: str, lead_lag: str, dr007_bps: List[Dict]) -> Tuple[str, Optional[str]]:
        """
        传导验证，修正价格方向
        
        Returns: (price_dir, flag)
        """
        # 央行有明确意图时
        if intent == 'tighten':
            if lead_lag == 'no_trend':
                # 传导受阻（方向相反）
                return '→', None
            elif lead_lag == 'dr007_lead':
                # OMO被动追赶（市场先紧，央行跟随）
                return '↓', '央行被动收紧'
            else:
                # OMO主动引导或同步
                return '↓', None
        
        elif intent == 'ease':
            if lead_lag == 'no_trend':
                # 传导受阻（方向相反）
                return '→', None
            elif lead_lag == 'dr007_lead':
                # OMO被动追赶（市场先松，央行跟随）
                return '↑', '央行被动宽松'
            else:
                # OMO主动引导或同步
                return '↑', None
        
        # 央行中性时，看DR007的市场方向
        else:  # intent == 'neutral'
            if dr007_bps:
                latest_bp = dr007_bps[-1]
                if latest_bp['direction'] == 'up':
                    return '↑', '央行未确认'
                else:
                    return '↓', '央行未确认'
            else:
                return '→', None
    
    def compute_quantity_direction(self, m2_dir: str, sfs_dir: str) -> str:
        """
        数量方向合成（M2 + 社融）
        同增长维度合成逻辑
        """
        if sfs_dir == 'N/A' or sfs_dir == '→':
            return m2_dir
        elif m2_dir == sfs_dir:
            return m2_dir
        elif m2_dir == '→':
            return sfs_dir
        else:
            return '→'
    
    def arbitrate_direction(self, price_dir: str, qty_dir: str) -> Tuple[str, Optional[str]]:
        """
        价格方向与数量方向冲突仲裁
        
        Returns: (final_dir, flag)
        """
        if price_dir == '↑':
            if qty_dir == '↓':
                return '↑', '数量价格背离'
            else:
                return '↑', None
        elif price_dir == '↓':
            if qty_dir == '↑':
                return '↓', '数量价格背离'
            else:
                return '↓', None
        else:  # price_dir == '→'
            if qty_dir == '→':
                return '→', None
            else:
                return qty_dir, '短端未确认'
    
    def compute_liquidity_state_v8(self, m2_cycle: float, m2_dir: str,
                                   sfs_cycle: Optional[float], sfs_dir: str,
                                   omo_daily: Optional[pd.Series], 
                                   dr007_daily: Optional[pd.Series],
                                   current_date) -> Tuple[str, str, str, str, str, str, Optional[str], str, str, str]:
        """
        V8流动性维度合成
        
        Returns: (level, direction, state, omo_intent, price_dir, qty_dir, flag, 
                  omo_bp_date, dr007_bp_date, lead_lag)
        """
        # 1. 水平判定（不变）
        m2_level = '货币扩张' if m2_cycle >= 0 else '货币收缩'
        
        if sfs_cycle is None or np.isnan(sfs_cycle):
            sfs_level = None
        else:
            sfs_level = '信用扩张' if sfs_cycle >= 0 else '信用收缩'
        
        if sfs_level is None:
            liq_level = '宽货币紧信用' if m2_level == '货币扩张' else '紧货币宽信用'
        elif m2_level == '货币扩张' and sfs_level == '信用扩张':
            liq_level = '双宽'
        elif m2_level == '货币收缩' and sfs_level == '信用收缩':
            liq_level = '双紧'
        elif m2_level == '货币扩张' and sfs_level == '信用收缩':
            liq_level = '宽货币紧信用'
        else:
            liq_level = '紧货币宽信用'
        
        # 2. 数量方向
        qty_dir = self.compute_quantity_direction(m2_dir, sfs_dir)
        
        # 3. 央行意图识别
        intent = self.detect_omo_intent(omo_daily, current_date) if omo_daily is not None else 'neutral'
        
        # 4. 传导验证
        omo_bps = self.find_breakpoints(omo_daily, current_date) if omo_daily is not None else []
        dr007_bps = self.find_breakpoints(dr007_daily, current_date) if dr007_daily is not None else []
        
        lead_lag = self.compare_lead_lag(omo_bps, dr007_bps)
        price_dir, transmission_flag = self.validate_transmission(intent, lead_lag, dr007_bps)
        
        # 5. 冲突仲裁
        final_dir, arb_flag = self.arbitrate_direction(price_dir, qty_dir)
        
        # 合并标记：传导标记优先
        flag = transmission_flag if transmission_flag else arb_flag
        
        # 6. 状态合成
        dir_map = {'↑': '上行', '↓': '下行', '→': '平稳'}
        liq_state = f"{liq_level}{dir_map[final_dir]}"
        
        # 拐点日期（用于审计）
        omo_bp_date = omo_bps[-1]['date'].strftime('%Y%m%d') if omo_bps else None
        dr007_bp_date = dr007_bps[-1]['date'].strftime('%Y%m%d') if dr007_bps else None
        
        return liq_level, final_dir, liq_state, intent, price_dir, qty_dir, flag, omo_bp_date, dr007_bp_date, lead_lag
    
    def map_regime(self, growth_state: str, inflation_state: str, 
                   liquidity_level: str) -> str:
        """
        10级优先级象限映射
        """
        is_contraction = growth_state.startswith('收缩')
        is_expansion = growth_state.startswith('扩张')
        is_exp_up = growth_state == '扩张上行'
        is_neutral_down = growth_state == '中性下行'
        is_high_inf = inflation_state.startswith('高通胀')
        is_moderate_inf = inflation_state.startswith('温和通胀')
        is_low_inf = inflation_state.startswith('低通胀')
        is_golden_low_inf = is_low_inf and growth_state.endswith('上行')
        is_tight_liq = liquidity_level in ['双紧', '紧货币宽信用']
        is_loose_liq = liquidity_level in ['双宽', '宽货币紧信用']
        
        if is_contraction and is_high_inf and is_tight_liq:
            return '极端滞胀'
        elif (is_contraction or is_neutral_down) and is_high_inf and not is_tight_liq:
            return '典型滞胀'
        elif is_expansion and is_high_inf and not is_tight_liq:
            return '过热期'
        elif is_contraction and is_low_inf and is_tight_liq:
            return '失速衰退'
        elif (is_contraction or is_neutral_down) and is_low_inf and is_loose_liq:
            return '宽衰退'
        elif (is_exp_up or growth_state == '中性上行') and is_low_inf and is_loose_liq:
            return '弱复苏'
        elif is_exp_up and (is_moderate_inf or is_golden_low_inf) and is_loose_liq:
            return '强势复苏'
        elif is_expansion and is_moderate_inf and not is_tight_liq:
            return '完美扩张'
        elif growth_state.startswith('中性') and is_low_inf and liquidity_level == '双紧':
            return '类衰退过渡'
        else:
            return '震荡/观望'
    
    def check_warnings(self, growth_state: str, inflation_state: str, 
                      liquidity_level: str, cost_divergence: bool, 
                      sfs_fiscal_interference: bool,
                      svc_arbitration: bool = False,
                      liquidity_flag: Optional[str] = None) -> List[str]:
        """
        检查4类WARNING
        """
        warnings = []
        
        # 1. 成本传导背离
        if cost_divergence:
            warnings.append('成本传导背离，上下游利润可能重塑')
        
        # 2. 结构性假衰退
        if svc_arbitration:
            warnings.append('触发服务业对冲，衰退确定性下降')
        
        # 3. 流动性价格-数量背离
        if liquidity_flag == '数量价格背离':
            warnings.append('流动性价格-数量背离，短端与长端信号拉锯')
        
        # 4. 社融财政干扰
        if sfs_fiscal_interference:
            warnings.append('社融财政干扰嫌疑，需人工核查是否为政府债集中缴款导致')
        
        return warnings
    
    def synthesize_state(self, date, 
                        pmi_data: Dict, iav_data: Optional[Dict],
                        ccpi_data: Dict, ppi_data: Dict,
                        m2_data: Dict, sfs_data: Optional[Dict],
                        omo_daily: Optional[pd.Series] = None,
                        dr007_daily: Optional[pd.Series] = None,
                        svc_data: Optional[Dict] = None,
                        thresholds: Optional[Dict] = None) -> Dict:
        """
        合成单个月份的宏观状态（V8）
        """
        record = {'date': date}
        
        # 增长维度
        pmi_raw = pmi_data['raw'] if pmi_data else np.nan
        pmi_dir = pmi_data.get('trend_dir', '→') if pmi_data else '→'
        iav_raw = iav_data['raw'] if iav_data else np.nan
        iav_cycle = iav_data['cycle'] if iav_data else np.nan
        iav_dir = iav_data.get('trend_dir', '→') if iav_data else '→'
        svc_raw = svc_data['raw'] if svc_data else None
        
        growth_level, growth_dir, growth_state, svc_arbitration = self.compute_growth_state(
            pmi_raw, pmi_dir, iav_raw, iav_cycle, iav_dir, svc_raw
        )
        
        record['pmi_raw'] = pmi_raw
        record['pmi_z'] = pmi_data.get('z', np.nan) if pmi_data else np.nan
        record['pmi_deviation'] = pmi_data.get('deviation', np.nan) if pmi_data else np.nan
        record['pmi_ma3_z'] = pmi_data.get('ma3_z', np.nan) if pmi_data else np.nan
        record['pmi_threshold'] = pmi_data.get('threshold', np.nan) if pmi_data else np.nan
        record['pmi_raw_dir'] = pmi_data.get('raw_dir', '→') if pmi_data else '→'
        record['pmi_trend_dir'] = pmi_dir
        record['pmi_level'] = '扩张' if pmi_raw >= 50 else '收缩'
        record['iav_raw'] = iav_raw if not np.isnan(iav_raw) else None
        record['iav_cycle'] = iav_cycle if not np.isnan(iav_cycle) else None
        record['iav_trend'] = iav_data.get('trend', np.nan) if iav_data else np.nan
        record['iav_z'] = iav_data.get('z', np.nan) if iav_data else np.nan
        record['iav_deviation'] = iav_data.get('deviation', np.nan) if iav_data else np.nan
        record['iav_ma3_z'] = iav_data.get('ma3_z', np.nan) if iav_data else np.nan
        record['iav_threshold'] = iav_data.get('threshold', np.nan) if iav_data else np.nan
        record['iav_raw_dir'] = iav_data.get('raw_dir', '→') if iav_data else '→'
        record['iav_trend_dir'] = iav_dir
        record['iav_level'] = '扩张' if iav_cycle is not None and iav_cycle >= 0 else '收缩' if iav_cycle is not None else None
        record['growth_level'] = growth_level
        record['growth_direction'] = growth_dir
        record['growth_state'] = growth_state
        
        # 通胀维度
        ccpi_raw = ccpi_data['raw'] if ccpi_data else np.nan
        ccpi_dir = ccpi_data.get('trend_dir', '→') if ccpi_data else '→'
        ppi_dir = ppi_data.get('trend_dir', '→') if ppi_data else '→'
        
        inf_level, inf_dir, inf_state, cost_divergence = self.compute_inflation_state(
            ccpi_raw, ccpi_dir, ppi_dir
        )
        
        record['ccpi_raw'] = ccpi_raw
        record['ccpi_cycle'] = ccpi_data.get('cycle', np.nan) if ccpi_data else np.nan
        record['ccpi_trend'] = ccpi_data.get('trend', np.nan) if ccpi_data else np.nan
        record['ccpi_z'] = ccpi_data.get('z', np.nan) if ccpi_data else np.nan
        record['ccpi_deviation'] = ccpi_data.get('deviation', np.nan) if ccpi_data else np.nan
        record['ccpi_ma3_z'] = ccpi_data.get('ma3_z', np.nan) if ccpi_data else np.nan
        record['ccpi_threshold'] = ccpi_data.get('threshold', np.nan) if ccpi_data else np.nan
        record['ccpi_raw_dir'] = ccpi_data.get('raw_dir', '→') if ccpi_data else '→'
        record['ccpi_trend_dir'] = ccpi_dir
        record['ccpi_level'] = inf_level
        record['ppi_raw'] = ppi_data['raw'] if ppi_data else np.nan
        record['ppi_cycle'] = ppi_data.get('cycle', np.nan) if ppi_data else np.nan
        record['ppi_trend'] = ppi_data.get('trend', np.nan) if ppi_data else np.nan
        record['ppi_z'] = ppi_data.get('z', np.nan) if ppi_data else np.nan
        record['ppi_deviation'] = ppi_data.get('deviation', np.nan) if ppi_data else np.nan
        record['ppi_ma3_z'] = ppi_data.get('ma3_z', np.nan) if ppi_data else np.nan
        record['ppi_threshold'] = ppi_data.get('threshold', np.nan) if ppi_data else np.nan
        record['ppi_raw_dir'] = ppi_data.get('raw_dir', '→') if ppi_data else '→'
        record['ppi_trend_dir'] = ppi_dir
        record['ppi_level'] = '扩张' if ppi_data and ppi_data.get('raw', 0) > 0 else '收缩'
        record['inflation_level'] = inf_level
        record['inflation_direction'] = inf_dir
        record['inflation_state'] = inf_state
        record['cost_divergence'] = cost_divergence
        
        # 流动性维度（V8）
        m2_cycle = m2_data['cycle'] if m2_data else np.nan
        m2_dir = m2_data.get('trend_dir', '→') if m2_data else '→'
        sfs_cycle = sfs_data['cycle'] if sfs_data else None
        sfs_dir = sfs_data.get('trend_dir', '→') if sfs_data else '→'
        
        liq_level, liq_dir, liq_state, omo_intent, price_dir, qty_dir, liq_flag, \
            omo_bp_date, dr007_bp_date, lead_lag = self.compute_liquidity_state_v8(
            m2_cycle, m2_dir, sfs_cycle, sfs_dir,
            omo_daily, dr007_daily, date
        )
        
        record['m2_raw'] = m2_data['raw'] if m2_data else np.nan
        record['m2_cycle'] = m2_cycle if not np.isnan(m2_cycle) else None
        record['m2_trend'] = m2_data.get('trend', np.nan) if m2_data else np.nan
        record['m2_z'] = m2_data.get('z', np.nan) if m2_data else np.nan
        record['m2_deviation'] = m2_data.get('deviation', np.nan) if m2_data else np.nan
        record['m2_ma3_z'] = m2_data.get('ma3_z', np.nan) if m2_data else np.nan
        record['m2_threshold'] = m2_data.get('threshold', np.nan) if m2_data else np.nan
        record['m2_raw_dir'] = m2_data.get('raw_dir', '→') if m2_data else '→'
        record['m2_trend_dir'] = m2_dir
        record['m2_level'] = '货币扩张' if m2_cycle is not None and m2_cycle >= 0 else '货币收缩'
        record['sfs_raw'] = sfs_data['raw'] if sfs_data else None
        record['sfs_cycle'] = sfs_cycle if sfs_cycle is not None else None
        record['sfs_trend'] = sfs_data.get('trend', np.nan) if sfs_data else np.nan
        record['sfs_z'] = sfs_data.get('z', np.nan) if sfs_data else np.nan
        record['sfs_deviation'] = sfs_data.get('deviation', np.nan) if sfs_data else np.nan
        record['sfs_ma3_z'] = sfs_data.get('ma3_z', np.nan) if sfs_data else np.nan
        record['sfs_threshold'] = sfs_data.get('threshold', np.nan) if sfs_data else np.nan
        record['sfs_raw_dir'] = sfs_data.get('raw_dir', '→') if sfs_data else '→'
        record['sfs_trend_dir'] = sfs_dir
        record['sfs_level'] = '信用扩张' if sfs_cycle is not None and sfs_cycle >= 0 else '信用收缩' if sfs_cycle is not None else None
        record['sfs_yoy_change'] = sfs_data.get('yoy_change', np.nan) if sfs_data else np.nan
        record['sfs_cycle_change'] = sfs_data.get('cycle_change', np.nan) if sfs_data else np.nan
        record['sfs_fiscal_interference'] = sfs_data.get('fiscal_interference', False) if sfs_data else False
        record['liquidity_level'] = liq_level
        record['liquidity_direction'] = liq_dir
        record['liquidity_state'] = liq_state
        record['omo_intent'] = omo_intent
        record['price_dir'] = price_dir
        record['qty_dir'] = qty_dir
        record['liquidity_flag'] = liq_flag
        record['omo_breakpoint_date'] = omo_bp_date
        record['dr007_breakpoint_date'] = dr007_bp_date
        record['lead_lag'] = lead_lag
        record['price_veto_triggered'] = False
        record['liquidity_before_veto'] = None
        
        # 计算月度DR007和OMO（用于兼容旧字段）
        dr007_monthly = np.nan
        omo_rate = np.nan
        if dr007_daily is not None and len(dr007_daily) > 0:
            month_data = dr007_daily[(dr007_daily.index.year == date.year) & (dr007_daily.index.month == date.month)]
            if len(month_data) > 0:
                dr007_monthly = month_data.mean()
        if omo_daily is not None and len(omo_daily) > 0:
            month_data = omo_daily[(omo_daily.index.year == date.year) & (omo_daily.index.month == date.month)]
            if len(month_data) > 0:
                omo_rate = month_data.iloc[-1]  # 月末最后一个有效值
        
        record['dr007_monthly'] = dr007_monthly
        record['omo_rate'] = omo_rate
        record['dr007_omo_spread'] = dr007_monthly - omo_rate if not (np.isnan(dr007_monthly) or np.isnan(omo_rate)) else np.nan
        
        # 最终象限
        regime = self.map_regime(growth_state, inf_state, liq_level)
        record['macro_regime'] = regime
        
        # Warnings
        sfs_fiscal = sfs_data.get('fiscal_interference', False) if sfs_data else False
        warnings = self.check_warnings(
            growth_state, inf_state, liq_level,
            cost_divergence, sfs_fiscal,
            svc_arbitration, liq_flag
        )
        record['warnings'] = json.dumps(warnings, ensure_ascii=False) if warnings else None
        record['methodology_version'] = 'V8'
        
        return record
