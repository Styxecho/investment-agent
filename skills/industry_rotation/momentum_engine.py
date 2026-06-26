# skills/industry_rotation/momentum_engine.py
"""
多周期动量引擎

计算申万行业指数的多周期超额收益、加速度及RS_score。
严格遵循Phase 2.4/2.5方法论V5.0。
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class MomentumEngine:
    """多周期动量计算引擎"""
    
    def __init__(self, data_manager):
        self.dm = data_manager
    
    def run(self, target_date: str) -> Dict[str, Any]:
        """
        执行动量计算完整流程
        
        Args:
            target_date: 目标日期 YYYYMMDD，用于确定最新月份
        
        Returns:
            {
                'latest_monthly_scores': List[Dict],  # 最新月份各行业RS_score
                'monthly_history': pd.DataFrame,       # 全历史月度数据（给stability_engine）
                'ma60_status': List[Dict],             # 最新MA60状态
                'latest_ym': str                      # 最新月份 (YYYY-MM)
            }
        """
        # Step 1: 读取数据
        df_sw = self.dm.load_sw_index_daily()
        df_bench = self.dm.load_benchmark_daily()
        
        logger.info(f"申万数据: {df_sw['trade_date'].min().date()} ~ {df_sw['trade_date'].max().date()}")
        logger.info(f"行业数量: {df_sw['index_code'].nunique()}")
        
        # Step 2: 计算月度收益率和超额收益
        df_all = self._calculate_monthly_returns(df_sw, df_bench)
        
        # Step 3: 每月截面计算RS_score
        monthly_results = self._calculate_cross_sectional_scores(df_all)
        
        if monthly_results.empty:
            return {
                'latest_monthly_scores': [],
                'monthly_history': pd.DataFrame(),
                'ma60_status': [],
                'latest_ym': ''
            }
        
        # Step 4: 计算MA60
        ma60_results = self._calculate_ma60(df_sw)
        
        # Step 5: 合并最新结果
        latest_ym = monthly_results['year_month'].max()
        latest_monthly = monthly_results[monthly_results['year_month'] == latest_ym].copy()
        
        # 合并MA60
        df_momentum = latest_monthly.merge(
            pd.DataFrame(ma60_results), on='index_code', how='left'
        )
        
        # 添加行业名称
        df_momentum = self._add_industry_names(df_momentum)
        
        # 格式化输出
        latest_scores = self._format_latest_scores(df_momentum)
        ma60_status = self._format_ma60_status(ma60_results)
        
        logger.info(f"动量计算完成，最新月份: {latest_ym}")
        logger.info(f"MA60上方: {sum(1 for m in ma60_status if m['above_ma60'])}/{len(ma60_status)}")
        
        return {
            'latest_monthly_scores': latest_scores,
            'monthly_history': monthly_results,
            'ma60_status': ma60_status,
            'latest_ym': str(latest_ym)
        }
    
    def _calculate_monthly_returns(self, df_sw: pd.DataFrame, df_bench: pd.DataFrame) -> pd.DataFrame:
        """计算月度收益率和超额收益"""
        # 取每月最后一个交易日
        df_sw_m = df_sw.sort_values(['index_code', 'trade_date']).copy()
        df_sw_m['year_month'] = df_sw_m['trade_date'].dt.to_period('M')
        df_sw_m = df_sw_m.groupby(['index_code', 'year_month']).last().reset_index()
        
        df_bench_m = df_bench.sort_values('trade_date').copy()
        df_bench_m['year_month'] = df_bench_m['trade_date'].dt.to_period('M')
        df_bench_m = df_bench_m.groupby('year_month').last().reset_index()
        
        # 合并基准
        df_all = df_sw_m.merge(
            df_bench_m[['year_month', 'close_price']],
            on='year_month',
            how='left',
            suffixes=('_ind', '_bench')
        )
        
        # 计算收益率
        df_all = df_all.sort_values(['index_code', 'year_month'])
        df_all['ret_1m'] = df_all.groupby('index_code')['close_price_ind'].pct_change(1)
        df_all['ret_3m'] = df_all.groupby('index_code')['close_price_ind'].pct_change(3)
        df_all['ret_6m'] = df_all.groupby('index_code')['close_price_ind'].pct_change(6)
        df_all['ret_12m'] = df_all.groupby('index_code')['close_price_ind'].pct_change(12)
        
        # 基准收益率
        df_bench_m = df_bench_m.sort_values('year_month')
        df_bench_m['bench_ret_1m'] = df_bench_m['close_price'].pct_change(1)
        df_bench_m['bench_ret_3m'] = df_bench_m['close_price'].pct_change(3)
        df_bench_m['bench_ret_6m'] = df_bench_m['close_price'].pct_change(6)
        df_bench_m['bench_ret_12m'] = df_bench_m['close_price'].pct_change(12)
        
        df_all = df_all.merge(
            df_bench_m[['year_month', 'bench_ret_1m', 'bench_ret_3m', 'bench_ret_6m', 'bench_ret_12m']],
            on='year_month',
            how='left'
        )
        
        # 超额收益
        df_all['excess_1m'] = df_all['ret_1m'] - df_all['bench_ret_1m']
        df_all['excess_3m'] = df_all['ret_3m'] - df_all['bench_ret_3m']
        df_all['excess_6m'] = df_all['ret_6m'] - df_all['bench_ret_6m']
        df_all['excess_12m'] = df_all['ret_12m'] - df_all['bench_ret_12m']
        
        return df_all
    
    def _calculate_cross_sectional_scores(self, df_all: pd.DataFrame) -> pd.DataFrame:
        """每月截面计算RS_score"""
        monthly_results = []
        
        for ym, group in df_all.groupby('year_month'):
            valid = group[
                group['excess_1m'].notna() &
                group['excess_3m'].notna() &
                group['excess_6m'].notna() &
                group['excess_12m'].notna()
            ].copy()
            
            if len(valid) < 5:
                continue
            
            # 截面Z-score（总体标准差 ddof=0，clip到±3）
            def safe_zscore(x):
                z = stats.zscore(x, nan_policy='omit', ddof=0)
                return np.clip(z, -3, 3)
            
            valid['z_6m'] = safe_zscore(valid['excess_6m'])
            valid['z_12m'] = safe_zscore(valid['excess_12m'])
            valid['z_1m'] = safe_zscore(valid['excess_1m'])
            valid['z_3m'] = safe_zscore(valid['excess_3m'])
            
            # 加速度 = Z(1M) - Z(3M)，再Z-score
            valid['acceleration_raw'] = valid['z_1m'] - valid['z_3m']
            valid['z_acceleration'] = safe_zscore(valid['acceleration_raw'])
            
            # RS_score = 0.4*Z(6M) + 0.3*Z(12M) + 0.3*Z(加速度)
            valid['rs_score'] = (
                0.4 * valid['z_6m'] +
                0.3 * valid['z_12m'] +
                0.3 * valid['z_acceleration']
            )
            
            # 截面排名（1=最好）
            valid['rank'] = valid['rs_score'].rank(ascending=False, method='min')
            
            monthly_results.append(valid[[
                'index_code', 'year_month', 'rs_score', 'rank',
                'excess_1m', 'excess_3m', 'excess_6m', 'excess_12m',
                'z_1m', 'z_3m', 'z_6m', 'z_12m',
                'acceleration_raw', 'z_acceleration',
                'close_price_ind'
            ]])
        
        if not monthly_results:
            return pd.DataFrame()
        
        return pd.concat(monthly_results, ignore_index=True)
    
    def _calculate_ma60(self, df_sw: pd.DataFrame) -> List[Dict]:
        """计算最新MA60状态"""
        results = []
        
        for sw_code in df_sw['index_code'].unique():
            df_ind = df_sw[df_sw['index_code'] == sw_code].sort_values('trade_date')
            if len(df_ind) >= 60:
                latest = df_ind.iloc[-1]
                ma60 = df_ind['close_price'].tail(60).mean()
                results.append({
                    'index_code': sw_code,
                    'trade_date': latest['trade_date'],
                    'close_price': latest['close_price'],
                    'ma60': ma60,
                    'above_ma60': bool(latest['close_price'] > ma60)
                })
        
        return results
    
    def _add_industry_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加申万行业名称"""
        df_names = self.dm.load_sw_industry_mapping()
        if df_names.empty:
            return df
        
        df_names['sw_code_clean'] = df_names['sw_code'].astype(str).str.replace('.SI', '', regex=False)
        df['sw_code_clean'] = df['index_code'].astype(str).str.replace('.SI', '', regex=False)
        name_map = dict(zip(df_names['sw_code_clean'], df_names['sw_name']))
        df['sw_name'] = df['sw_code_clean'].map(name_map)
        
        return df
    
    def _format_latest_scores(self, df: pd.DataFrame) -> List[Dict]:
        """格式化最新月份得分为List[Dict]"""
        df = df.sort_values('rs_score', ascending=False)
        records = []
        
        for _, row in df.iterrows():
            records.append({
                'index_code': row['index_code'],
                'sw_name': row.get('sw_name', ''),
                'rs_score': round(row['rs_score'], 4),
                'rank': int(row['rank']),
                'excess_6m': round(row['excess_6m'], 4),
                'excess_12m': round(row['excess_12m'], 4),
                'acceleration_raw': round(row['acceleration_raw'], 4),
                'above_ma60': bool(row.get('above_ma60', False))
            })
        
        return records
    
    def _format_ma60_status(self, ma60_results: List[Dict]) -> List[Dict]:
        """格式化MA60状态"""
        return [
            {
                'index_code': r['index_code'],
                'trade_date': r['trade_date'].strftime('%Y%m%d') if hasattr(r['trade_date'], 'strftime') else str(r['trade_date']),
                'close_price': round(r['close_price'], 4),
                'ma60': round(r['ma60'], 4),
                'above_ma60': r['above_ma60']
            }
            for r in ma60_results
        ]
