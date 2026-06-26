# skills/industry_rotation/stability_engine.py
"""
排名稳定性引擎 + 优势池构建

基于月度RS_score历史，计算排名稳定性并构建优势池。
严格遵循Phase 2.4/2.5方法论V5.0。
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class StabilityEngine:
    """排名稳定性与优势池构建引擎"""
    
    def __init__(self, data_manager):
        self.dm = data_manager
    
    def run(self, monthly_history: pd.DataFrame,
            industry_mapping: List[Dict]) -> Dict[str, Any]:
        """
        执行稳定性计算与优势池构建
        
        Args:
            monthly_history: momentum_engine输出的月度历史DataFrame
            industry_mapping: tie_engine输出的行业-ETF映射表
        
        Returns:
            {
                'all_scores': List[Dict],      # 全部31行业Composite_score
                'selected_pool': List[Dict],   # 优势池行业
                'pool_stats': {
                    'total': N,
                    'selected': N,
                    'with_etf': N,
                    'without_etf': N
                }
            }
        """
        if monthly_history.empty:
            return {
                'all_scores': [],
                'selected_pool': [],
                'pool_stats': {'total': 0, 'selected': 0, 'with_etf': 0, 'without_etf': 0}
            }
        
        # Step 1: 计算排名稳定性
        df_stability = self._calculate_stability(monthly_history)
        
        if df_stability.empty:
            return {
                'all_scores': [],
                'selected_pool': [],
                'pool_stats': {'total': 0, 'selected': 0, 'with_etf': 0, 'without_etf': 0}
            }
        
        # Step 2: 计算Composite_score
        df_stability = self._calculate_composite_score(df_stability)
        
        # Step 3: 构建优势池
        df_selected = self._build_advantage_pool(df_stability)
        
        # Step 4: 合并行业名称和ETF信息
        df_stability = self._enrich_with_metadata(df_stability, industry_mapping)
        df_selected = self._enrich_with_metadata(df_selected, industry_mapping)
        
        # Step 5: 格式化输出
        all_scores = self._format_scores(df_stability)
        selected_pool = self._format_scores(df_selected)
        
        pool_stats = {
            'total': len(df_stability),
            'selected': len(df_selected),
            'with_etf': df_selected['primary_etf_code'].notna().sum(),
            'without_etf': df_selected['primary_etf_code'].isna().sum()
        }
        
        logger.info(
            f"优势池构建完成: {pool_stats['selected']}/{pool_stats['total']} "
            f"(有ETF: {pool_stats['with_etf']})"
        )
        
        return {
            'all_scores': all_scores,
            'selected_pool': selected_pool,
            'pool_stats': pool_stats
        }
    
    def _calculate_stability(self, monthly_history: pd.DataFrame) -> pd.DataFrame:
        """计算每个行业的排名稳定性（回溯6个月）"""
        # 统计每月通过MA60的行业总数（用于缺失值惩罚）
        monthly_counts = monthly_history.groupby('year_month').size().reset_index(name='n_passed')
        
        stability_results = []
        
        for sw_code in monthly_history['index_code'].unique():
            df_ind = monthly_history[monthly_history['index_code'] == sw_code].sort_values('year_month')
            
            if len(df_ind) < 6:
                continue
            
            # 取最近6个月
            recent = df_ind.tail(6).copy()
            n_months = len(recent)
            recent_ym = recent['year_month'].tolist()
            
            # 获取这些月份的行业总数N
            n_data = monthly_counts[monthly_counts['year_month'].isin(recent_ym)]
            
            # 实际排名
            ranks = recent['rank'].tolist()
            
            # 缺失值惩罚：如果某月没有记录（未通过MA60），排名 = N+1
            penalty_ranks = []
            for _, row_n in n_data.iterrows():
                ym = row_n['year_month']
                if ym not in recent_ym:
                    penalty_ranks.append(row_n['n_passed'] + 1)
            
            all_ranks = ranks + penalty_ranks
            n_missing = len(penalty_ranks)
            
            if len(all_ranks) < 3:
                continue
            
            # 排名标准差（样本标准差 ddof=1）
            rank_std = np.std(all_ranks, ddof=1) if len(all_ranks) > 1 else 0
            
            latest = recent.iloc[-1]
            
            stability_results.append({
                'index_code': sw_code,
                'year_month': latest['year_month'],
                'rs_score': latest['rs_score'],
                'rank': latest['rank'],
                'rank_std': rank_std,
                'n_months': n_months,
                'n_missing': n_missing,
                'excess_6m': latest['excess_6m'],
                'excess_12m': latest['excess_12m'],
                'z_acceleration': latest['z_acceleration']
            })
        
        return pd.DataFrame(stability_results)
    
    def _calculate_composite_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算Stability_score和Composite_score"""
        # Stability_score = Z(-σ_rank)
        df['stability_raw'] = -df['rank_std']
        df['stability_score'] = stats.zscore(df['stability_raw'], nan_policy='omit')
        
        # Composite_score = 0.6*RS_score + 0.4*Stability_score
        df['composite_score'] = 0.6 * df['rs_score'] + 0.4 * df['stability_score']
        
        # 排序
        df = df.sort_values('composite_score', ascending=False).reset_index(drop=True)
        
        return df
    
    def _build_advantage_pool(self, df: pd.DataFrame) -> pd.DataFrame:
        """构建优势池（条件A或条件B）"""
        n_total = len(df)
        
        # 条件A: Composite_score > 0
        condition_a = df['composite_score'] > 0
        
        # 条件B: 排名前1/3 且 Composite_score > -0.5
        top_third = int(n_total / 3)
        condition_b = (df.index < top_third) & (df['composite_score'] > -0.5)
        
        # 并集
        df_selected = df[condition_a | condition_b].copy()
        
        logger.info(
            f"条件A(Composite>0): {condition_a.sum()}, "
            f"条件B(前1/3且>-0.5): {condition_b.sum()}, "
            f"优势池: {len(df_selected)}"
        )
        
        return df_selected
    
    def _enrich_with_metadata(self, df: pd.DataFrame,
                             industry_mapping: List[Dict]) -> pd.DataFrame:
        """添加行业名称和ETF映射信息"""
        # 添加行业名称
        df_names = self.dm.load_sw_industry_mapping()
        if not df_names.empty:
            df_names['sw_code_clean'] = df_names['sw_code'].astype(str).str.replace('.SI', '', regex=False)
            df['sw_code_clean'] = df['index_code'].astype(str).str.replace('.SI', '', regex=False)
            name_map = dict(zip(df_names['sw_code_clean'], df_names['sw_name']))
            df['sw_name'] = df['sw_code_clean'].map(name_map)
        
        # 添加ETF映射
        if industry_mapping:
            df_map = pd.DataFrame(industry_mapping)
            df['sw_code_clean'] = df['index_code'].astype(str).str.replace('.SI', '', regex=False)
            df_map['sw_code_clean'] = df_map['sw_code'].astype(str).str.replace('.SI', '', regex=False)
            df = df.merge(
                df_map[['sw_code_clean', 'primary_etf_code', 'primary_etf_name', 'tier']],
                on='sw_code_clean',
                how='left'
            )
        
        return df
    
    def _format_scores(self, df: pd.DataFrame) -> List[Dict]:
        """格式化得分为List[Dict]"""
        records = []
        
        for _, row in df.iterrows():
            records.append({
                'index_code': row['index_code'],
                'sw_name': row.get('sw_name', ''),
                'rs_score': round(row['rs_score'], 4),
                'rank': int(row['rank']),
                'rank_std': round(row['rank_std'], 4),
                'stability_score': round(row['stability_score'], 4),
                'composite_score': round(row['composite_score'], 4),
                'primary_etf_code': row.get('primary_etf_code', '') if pd.notna(row.get('primary_etf_code')) else '',
                'primary_etf_name': row.get('primary_etf_name', '') if pd.notna(row.get('primary_etf_name')) else '',
                'tier': row.get('tier', '') if pd.notna(row.get('tier')) else ''
            })
        
        return records
