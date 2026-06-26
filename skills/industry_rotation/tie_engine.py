# skills/industry_rotation/tie_engine.py
"""
TIE映射引擎

基于目标行业暴露度(TIE)建立申万一级行业与行业主题ETF的定量映射。
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import logging

logger = logging.getLogger(__name__)

# TIE分级阈值
TIE_THRESHOLD_CORE = 0.50
PURITY_GAP_CORE = 0.10
TIE_THRESHOLD_BACKUP = 0.30


class TIEEngine:
    """目标行业暴露度(TIE)映射引擎"""
    
    def __init__(self, data_manager):
        self.dm = data_manager
    
    def run(self) -> Dict[str, Any]:
        """
        执行TIE映射完整流程
        
        Returns:
            {
                'tier_distribution': {'core': N, 'backup': N, 'unmapped': N},
                'industry_mapping': List[Dict],  # 行业→首选ETF映射
                'etf_tie_scores': List[Dict],    # 每只ETF的TIE详情
                'coverage': {
                    'total_industries': 31,
                    'mapped_industries': N,
                    'unmapped_industries': List[str]
                }
            }
        """
        # Step 1: 读取申万行业成分股
        sw_industries = self._load_sw_industries()
        logger.info(f"成功读取 {len(sw_industries)} 个申万行业")
        
        # Step 2: 读取ETF列表
        df_etf = self.dm.load_etf_universe()
        industry_etfs = df_etf[df_etf['asset_class_l2'] == '行业主题'].copy()
        
        # 排除跨境ETF
        a_share_etfs = industry_etfs[
            ~industry_etfs['index_code'].astype(str).str.contains(r'\.(HK|NQI|GI)$', regex=True, na=False)
        ].copy()
        
        logger.info(f"行业主题ETF: {len(industry_etfs)}，A股ETF: {len(a_share_etfs)}")
        
        # Step 3: 读取ETF成分股权重
        etf_components = self._load_etf_components(a_share_etfs)
        logger.info(f"成功读取 {len(etf_components)} 只ETF成分股权重")
        
        # Step 4: 计算TIE
        tie_results = self._calculate_tie(etf_components, sw_industries)
        logger.info(f"TIE计算完成，共 {len(tie_results)} 只ETF")
        
        # Step 5: 构建行业映射表（含流动性筛选）
        industry_mapping = self._build_industry_mapping(tie_results, sw_industries, df_etf)
        
        # Step 6: 覆盖度统计
        all_sw = set(sw_industries.keys())
        mapped_sw = set(m['sw_code'] for m in industry_mapping)
        uncovered = sorted(all_sw - mapped_sw)
        
        # Step 7: 分级统计
        df_tie = pd.DataFrame(tie_results)
        tier_dist = {
            'core': int((df_tie['tier'] == 'industry_rotation_core').sum()),
            'backup': int((df_tie['tier'] == 'industry_rotation_backup').sum()),
            'unmapped': int((df_tie['tier'] == 'unmapped').sum())
        }
        
        return {
            'tier_distribution': tier_dist,
            'industry_mapping': industry_mapping,
            'etf_tie_scores': tie_results,
            'coverage': {
                'total_industries': len(all_sw),
                'mapped_industries': len(mapped_sw),
                'unmapped_industries': uncovered
            }
        }
    
    def _load_sw_industries(self) -> Dict[str, Dict]:
        """读取所有申万行业成分股，建立股票→行业映射"""
        components_dir = self.dm.components_dir
        sw_files = sorted(components_dir.glob('sw_*.xls'))
        
        sw_industries = {}
        
        for f in sw_files:
            sw_code = f.name.replace('sw_', '').replace('.xls', '')
            df = pd.read_excel(f, dtype=str)
            
            # 列: 日期, 指数代码, 指数名称, 成分股代码, 成分股简称, 权重%
            if len(df.columns) < 4:
                logger.warning(f"{f.name} 列数不足，跳过")
                continue
            
            stocks = df.iloc[:, 3].astype(str).str.strip().tolist()
            industry_name = str(df.iloc[:, 2].iloc[0]) if len(df.columns) > 2 else sw_code
            
            sw_industries[sw_code] = {
                'name': industry_name,
                'stock_count': len(stocks),
                'stocks': set(stocks)
            }
        
        return sw_industries
    
    def _load_etf_components(self, a_share_etfs: pd.DataFrame) -> Dict[str, Dict]:
        """读取每只ETF的跟踪指数成分股权重"""
        components_dir = self.dm.components_dir
        
        # 建立 index_code -> 文件名 映射
        idx_file_map = {}
        for f in components_dir.glob('*'):
            if f.name.startswith('sw_') or f.name.startswith('000985'):
                continue
            parts = f.name.split('_')
            if len(parts) >= 1:
                idx_code = parts[0]
                idx_file_map[idx_code] = f
        
        etf_components = {}
        
        for _, etf in a_share_etfs.iterrows():
            etf_code = etf['code']
            idx_code = str(etf['index_code'])
            base_code = idx_code.split('.')[0] if '.' in idx_code else idx_code
            
            if base_code not in idx_file_map:
                logger.debug(f"缺失成分股权重文件: {etf_code} ({idx_code})")
                continue
            
            file_path = idx_file_map[base_code]
            try:
                df_comp = pd.read_excel(file_path, dtype=str)
                
                # 自动识别列
                code_col = None
                weight_col = None
                
                for col in df_comp.columns:
                    col_str = str(col).lower()
                    if any(kw in col_str for kw in ['constituent code', '成分券代码', '成分股代码', 'stock code', '证券代码']):
                        code_col = col
                    if any(kw in col_str for kw in ['weight', '权重']):
                        weight_col = col
                
                if code_col is None or weight_col is None:
                    if len(df_comp.columns) >= 6:
                        code_col = df_comp.columns[1]
                        weight_col = df_comp.columns[-1]
                    else:
                        logger.warning(f"{file_path.name} 无法识别代码/权重列")
                        continue
                
                df_comp = df_comp[[code_col, weight_col]].copy()
                df_comp.columns = ['stock_code', 'weight']
                df_comp['stock_code'] = df_comp['stock_code'].astype(str).str.strip().str.zfill(6)
                df_comp['weight'] = pd.to_numeric(df_comp['weight'], errors='coerce')
                df_comp = df_comp.dropna()
                
                # 权重归一化
                if df_comp['weight'].max() > 50:
                    df_comp['weight'] = df_comp['weight'] / 100.0
                elif df_comp['weight'].max() >= 1.0:
                    df_comp['weight'] = df_comp['weight'] / 100.0
                
                etf_components[etf_code] = {
                    'index_code': idx_code,
                    'name': etf['name'],
                    'file': file_path.name,
                    'components': df_comp
                }
                
            except Exception as e:
                logger.warning(f"读取 {file_path.name} 失败: {e}")
        
        return etf_components
    
    def _calculate_tie(self, etf_components: Dict, sw_industries: Dict) -> List[Dict]:
        """计算每只ETF的TIE得分"""
        tie_results = []
        
        for etf_code, info in etf_components.items():
            df_comp = info['components']
            
            # 计算在每个申万行业的暴露度
            sw_exposure = {}
            for sw_code, sw_info in sw_industries.items():
                industry_stocks = sw_info['stocks']
                matched = df_comp[df_comp['stock_code'].isin(industry_stocks)]
                
                if len(matched) > 0:
                    exposure = matched['weight'].sum()
                    sw_exposure[sw_code] = exposure
            
            if not sw_exposure:
                continue
            
            # 排序，找出TIE最高的行业
            sorted_exposure = sorted(sw_exposure.items(), key=lambda x: x[1], reverse=True)
            primary_sw = sorted_exposure[0][0]
            primary_tie = sorted_exposure[0][1]
            
            # 纯度差
            secondary_tie = sorted_exposure[1][1] if len(sorted_exposure) > 1 else 0.0
            purity_gap = primary_tie - secondary_tie
            
            # 分级
            if primary_tie >= TIE_THRESHOLD_CORE and purity_gap >= PURITY_GAP_CORE:
                tier = 'industry_rotation_core'
            elif primary_tie >= TIE_THRESHOLD_BACKUP:
                tier = 'industry_rotation_backup'
            else:
                tier = 'unmapped'
            
            tie_results.append({
                'etf_code': etf_code,
                'etf_name': info['name'],
                'index_code': info['index_code'],
                'primary_sw_code': primary_sw,
                'primary_sw_name': sw_industries.get(primary_sw, {}).get('name', primary_sw),
                'primary_tie': round(primary_tie, 4),
                'secondary_tie': round(secondary_tie, 4),
                'purity_gap': round(purity_gap, 4),
                'tier': tier,
                'total_matched_weight': round(sum(sw_exposure.values()), 4),
                'num_industries': len(sw_exposure)
            })
        
        return tie_results
    
    def _build_industry_mapping(self, tie_results: List[Dict], 
                               sw_industries: Dict,
                               df_etf_full: pd.DataFrame) -> List[Dict]:
        """构建行业→ETF映射表，同一行业多只ETF时选成交额最大的"""
        df_tie = pd.DataFrame(tie_results)
        
        if df_tie.empty:
            return []
        
        # 合并成交额
        df_turnover = df_etf_full[['code', 'daily_turnover']].copy()
        df_turnover['daily_turnover'] = pd.to_numeric(df_turnover['daily_turnover'], errors='coerce')
        df_tie = df_tie.merge(df_turnover, left_on='etf_code', right_on='code', how='left')
        
        # 只考虑有映射的（core + backup）
        mapped = df_tie[df_tie['tier'].isin(['industry_rotation_core', 'industry_rotation_backup'])].copy()
        covered_sw = set(mapped['primary_sw_code'].unique())
        
        industry_mapping = []
        
        for sw_code in sorted(covered_sw):
            sw_name = sw_industries.get(sw_code, {}).get('name', sw_code)
            sw_etfs = mapped[mapped['primary_sw_code'] == sw_code].sort_values('primary_tie', ascending=False)
            
            core_candidates = sw_etfs[sw_etfs['tier'] == 'industry_rotation_core']
            backup_candidates = sw_etfs[sw_etfs['tier'] == 'industry_rotation_backup']
            
            if len(core_candidates) > 0:
                primary_etf = core_candidates.sort_values('daily_turnover', ascending=False).iloc[0]
                backup_etfs = core_candidates[core_candidates['etf_code'] != primary_etf['etf_code']]
                tier = 'core'
            elif len(backup_candidates) > 0:
                primary_etf = backup_candidates.iloc[0]
                backup_etfs = backup_candidates[backup_candidates['etf_code'] != primary_etf['etf_code']]
                tier = 'backup'
            else:
                continue
            
            industry_mapping.append({
                'sw_code': sw_code,
                'sw_name': sw_name,
                'primary_etf_code': primary_etf['etf_code'],
                'primary_etf_name': primary_etf['etf_name'],
                'primary_tie': round(primary_etf['primary_tie'], 4),
                'primary_purity_gap': round(primary_etf['purity_gap'], 4),
                'primary_turnover': round(primary_etf['daily_turnover'], 2) if pd.notna(primary_etf['daily_turnover']) else None,
                'backup_etfs': ';'.join(backup_etfs['etf_code'].tolist()) if len(backup_etfs) > 0 else '',
                'has_backup': len(backup_etfs) > 0,
                'tier': tier
            })
        
        return industry_mapping
