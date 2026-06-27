# skills/industry_rotation/micro_engine.py
"""
Phase 2.5 微观趋势验证引擎

职责：
1. 对 Phase 2.4 宏观协同后的候选池进行入场确认
2. 模式A（回调买入，优先）vs 模式B（突破买入，补充）
3. 等权仓位分配，单行业上限40%，最多5个行业
4. 行业指数 → ETF 映射（优先 Core 一级映射）

严格遵循 docs/roadmap/Phase_2.4&2.5_Methodology_Summary.md V5.0。
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MicroConfig:
    """微观层参数配置"""
    ma_short: int = 20
    ma_mid: int = 60
    ma_long: int = 120
    
    # 模式A：强势回调容差
    pull_back_tol: float = 0.03
    # 模式A：深度回调条件
    deep_pull_back_tol: float = 0.03
    deep_pull_back_max_5d_drop: float = 0.05
    # 跌幅限制
    max_5d_drop: float = 0.08
    
    # 模式B：突破窗口
    breakout_window: int = 5
    
    # 仓位分配
    max_positions: int = 5
    single_cap: float = 0.40
    
    # ETF 映射
    etf_mapping_path: str = "docs/research/industry_rotation/industry_etf_mapping.csv"
    tie_core_threshold: float = 0.50


class MicroEngine:
    """微观趋势验证引擎"""
    
    def __init__(self, config: Optional[MicroConfig] = None):
        self.cfg = config or MicroConfig()
        self.etf_mapping = self._load_etf_mapping()
    
    def run(
        self,
        final_pool: List[Dict[str, Any]],
        target_date: str,
        df_daily_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """
        执行微观入场确认与仓位分配
        
        Args:
            final_pool: macro_synergy 输出的 final_pool，已按 composite_score_adj 排序
            target_date: 目标日期 YYYYMMDD（月末）
            df_daily_dict: {index_code: df_daily}，包含 close/open/high/low/volume/amount
        
        Returns:
            {
                'target_date': str,
                'selected': List[Dict],  # 入选行业，含权重和入场模式
                'cash_weight': float,
                'summary': str
            }
        """
        if not final_pool:
            return {
                'target_date': target_date,
                'selected': [],
                'cash_weight': 1.0,
                'summary': '候选池为空，卫星仓位空仓'
            }
        
        selected = []
        
        for item in final_pool[:self.cfg.max_positions * 2]:  # 先多取一些做筛选
            index_code = item['index_code']
            df = df_daily_dict.get(index_code)
            if df is None or df.empty:
                logger.warning(f"[{index_code}] 无日频数据，跳过")
                continue
            
            # 只用到 target_date 及之前的数据（避免未来函数）
            df = df[df['trade_date'] <= pd.Timestamp(target_date)].copy()
            if len(df) < self.cfg.ma_long:
                logger.warning(f"[{index_code}] 历史数据不足{self.cfg.ma_long}日，跳过")
                continue
            
            # 计算技术指标
            df = self._add_indicators(df)
            latest = df.iloc[-1]
            
            # 模式A优先
            entry_mode = self._check_pattern_a(df)
            if not entry_mode:
                entry_mode = self._check_pattern_b(df)
            
            if entry_mode:
                selected.append({
                    'index_code': index_code,
                    'index_name': item.get('index_name', index_code),
                    'entry_mode': entry_mode,
                    'composite_score_adj': item.get('composite_score_adj', item.get('composite_score', 0)),
                    'close_price': latest['close'],
                    'ma20': latest['ma20'],
                    'ma60': latest['ma60'],
                    'ma120': latest['ma120'],
                    'macd_dif': latest['macd_dif'],
                    'macd_dea': latest['macd_dea'],
                    'macd_hist': latest['macd_hist'],
                    'distance_to_ma20': latest['distance_to_ma20'],
                    'distance_to_ma60': latest['distance_to_ma60'],
                    'return_5d': latest['return_5d'],
                    'primary_etf_code': item.get('primary_etf_code'),
                    'primary_etf_name': item.get('primary_etf_name'),
                    'etf_mapping_level': item.get('etf_mapping_level')
                })
            else:
                logger.debug(f"[{index_code}] 未通过入场确认")
        
        # 限制最多5个
        selected = selected[:self.cfg.max_positions]
        
        # 仓位分配
        selected, cash_weight = self._allocate_weights(selected)
        
        summary = (
            f"微观确认：候选{len(final_pool)}个，入选{len(selected)}个，"
            f"现金占比{cash_weight:.2%}"
        )
        logger.info(summary)
        
        return {
            'target_date': target_date,
            'selected': selected,
            'cash_weight': cash_weight,
            'summary': summary
        }
    
    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算均线、MACD、价格位置等技术指标"""
        df = df.sort_values('trade_date').copy()
        
        # 统一列名
        if 'close_price' in df.columns:
            df['close'] = df['close_price']
        if 'open_price' in df.columns:
            df['open'] = df['open_price']
        if 'high_price' in df.columns:
            df['high'] = df['high_price']
        if 'low_price' in df.columns:
            df['low'] = df['low_price']
        if 'pre_close_price' in df.columns and 'pre_close' not in df.columns:
            df['pre_close'] = df['pre_close_price']
        
        # 均线
        df['ma20'] = df['close'].rolling(self.cfg.ma_short).mean()
        df['ma60'] = df['close'].rolling(self.cfg.ma_mid).mean()
        df['ma120'] = df['close'].rolling(self.cfg.ma_long).mean()
        
        # MACD
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['macd_dif'] = df['ema12'] - df['ema26']
        df['macd_dea'] = df['macd_dif'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd_dif'] - df['macd_dea']
        
        # 价格位置
        df['distance_to_ma20'] = (df['close'] - df['ma20']) / df['ma20']
        df['distance_to_ma60'] = (df['close'] - df['ma60']) / df['ma60']
        
        # 5日收益/跌幅
        df['return_5d'] = df['close'].pct_change(5)
        
        # MA20 方向（最近5日是否向上）
        df['ma20_slope'] = df['ma20'].diff(5)
        
        # 是否刚上穿 MA20（过去5个交易日内）
        df['above_ma20'] = (df['close'] > df['ma20']).fillna(False)
        df['cross_ma20'] = (df['above_ma20'] & (~df['above_ma20'].shift(1).fillna(False))).astype(int)
        df['days_since_cross_ma20'] = df['cross_ma20'].cumsum()
        
        return df
    
    def _check_pattern_a(self, df: pd.DataFrame) -> Optional[str]:
        """
        模式A：回调买入
        
        条件：
        1. MA20 > MA60 > MA120（多头排列）
        2. MACD DIF > 0
        3. 强势回调：收盘价距MA20在 ±pull_back_tol 以内
        4. 或深度回调：收盘价距MA60在 ±deep_pull_back_tol 以内，MACD绿柱缩短，过去5日跌幅 < deep_pull_back_max_5d_drop
        5. 过去5日累计跌幅 < max_5d_drop
        """
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else latest
        
        # 1. 多头排列
        if not (latest['ma20'] > latest['ma60'] > latest['ma120']):
            return None
        
        # 2. DIF > 0
        if not (latest['macd_dif'] > 0):
            return None
        
        # 5. 跌幅限制
        if latest['return_5d'] < -self.cfg.max_5d_drop:
            return None
        
        # 3. 强势回调
        if abs(latest['distance_to_ma20']) <= self.cfg.pull_back_tol:
            return '模式A-强势回调'
        
        # 4. 深度回调
        if abs(latest['distance_to_ma60']) <= self.cfg.deep_pull_back_tol:
            # MACD绿柱且缩短
            if latest['macd_hist'] < 0 and latest['macd_hist'] > prev['macd_hist']:
                if latest['return_5d'] > -self.cfg.deep_pull_back_max_5d_drop:
                    return '模式A-深度回调'
        
        return None
    
    def _check_pattern_b(self, df: pd.DataFrame) -> Optional[str]:
        """
        模式B：突破买入
        
        条件：
        1. 收盘价首次上穿MA20不超过 breakout_window 个交易日
        2. MA20 > MA60 且 MA20已拐头向上
        3. MACD金叉或零轴附近
        """
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else latest
        
        # 1. 当前在MA20上方，且过去 breakout_window 日内发生过上穿
        if not latest['above_ma20']:
            return None
        recent = df.tail(self.cfg.breakout_window)
        if recent['cross_ma20'].sum() == 0:
            return None
        
        # 2. MA20 > MA60 且 MA20 拐头向上
        if not (latest['ma20'] > latest['ma60']):
            return None
        if not (latest['ma20_slope'] > 0):
            return None
        
        # 3. MACD金叉或零轴附近
        golden_cross = (latest['macd_dif'] > latest['macd_dea']) and (prev['macd_dif'] <= prev['macd_dea'])
        near_zero = abs(latest['macd_dif']) < 0.02 * latest['close']  # 零轴附近：DIF绝对值小于收盘价2%（简化）
        
        if golden_cross or near_zero:
            return '模式B-突破买入'
        
        return None
    
    def _allocate_weights(self, selected: List[Dict]) -> Tuple[List[Dict], float]:
        """
        等权分配卫星资金，单行业上限40%
        
        Returns:
            (selected_with_weight, cash_weight)
        """
        n = len(selected)
        if n == 0:
            return selected, 1.0
        
        equal_weight = 1.0 / n
        cap = self.cfg.single_cap
        
        if n >= 3:
            # 等权自然满足 33.3% < 40%
            target_weight = equal_weight
        else:
            # n=1 或 n=2 时受40%上限约束
            target_weight = min(equal_weight, cap)
        
        total_weight = target_weight * n
        cash_weight = 1.0 - total_weight
        
        for item in selected:
            item['target_weight'] = round(target_weight, 4)
        
        return selected, round(cash_weight, 4)
    
    def _load_etf_mapping(self) -> pd.DataFrame:
        """加载行业-ETF映射表"""
        import os
        path = self.cfg.etf_mapping_path
        if not os.path.exists(path):
            logger.warning(f"ETF映射文件不存在：{path}")
            return pd.DataFrame()
        return pd.read_csv(path)
    
    def map_to_etf(self, selected: List[Dict]) -> List[Dict]:
        """
        将入选行业映射为ETF
        
        规则：
        - 优先一级映射（Core）
        - 无 Core 则放弃该行业
        - 多只 Core ETF 选成交额最大者（此处无ETF成交额数据，暂取第一只）
        
        Args:
            selected: MicroEngine.run 输出的 selected 列表
        
        Returns:
            增加 'trade_code' 字段的 selected 列表
        """
        if self.etf_mapping.empty:
            # 无映射表时直接返回行业指数代码作为交易代码
            for item in selected:
                item['trade_code'] = item['index_code']
                item['trade_name'] = item.get('index_name', item['index_code'])
            return selected
        
        mapping = self.etf_mapping.set_index('sw_code')
        result = []
        
        for item in selected:
            sw_code = item['index_code'].replace('.SI', '')
            if sw_code not in mapping.index:
                logger.warning(f"[{sw_code}] 无ETF映射，放弃")
                continue
            
            row = mapping.loc[sw_code]
            level = row.get('mapping_level', '')
            
            if level != 'core':
                logger.warning(f"[{sw_code}] 非Core映射（{level}），放弃")
                continue
            
            etf_code = row.get('primary_etf_code')
            etf_name = row.get('primary_etf_name', '')
            
            if pd.isna(etf_code):
                logger.warning(f"[{sw_code}] Core映射但ETF代码为空，放弃")
                continue
            
            item['trade_code'] = etf_code
            item['trade_name'] = etf_name
            result.append(item)
        
        # 重新分配权重（因为可能有些行业被放弃）
        if result:
            result, cash_weight = self._allocate_weights(result)
        else:
            cash_weight = 1.0
        
        return result
