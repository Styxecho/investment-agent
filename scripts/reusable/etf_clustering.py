#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ETF聚类分析工具类

可复用的聚类分析框架，支持：
1. 双维度相似度计算（成分股+收益率）
2. 层次聚类
3. 质量管控（最小相似度底线）
4. 代表性ETF筛选

使用示例:
    from scripts.etf_clustering import ETFClustering
    
    cluster = ETFClustering(
        weight_component=0.6,
        weight_return=0.4,
        distance_threshold=0.8,
        min_avg_similarity=0.4
    )
    
    results = cluster.cluster_by_sector(
        etf_universe_path='data_external/reference/etf_universe.csv',
        index_dir='D:/Study/Research/ETF/csindex',
        corr_matrix_path='data_runtime/index_correlation_matrix.csv'
    )
"""

import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
import glob
import os
from typing import Dict, List, Tuple, Optional


class ETFClustering:
    """
    ETF聚类分析工具类
    
    支持基于成分股和收益率的双维度聚类分析
    """
    
    def __init__(
        self,
        weight_component: float = 0.6,
        weight_return: float = 0.4,
        distance_threshold: float = 0.8,
        min_avg_similarity: float = 0.4
    ):
        """
        初始化聚类参数
        
        :param weight_component: 成分股权重（0-1）
        :param weight_return: 收益率权重（0-1）
        :param distance_threshold: 聚类距离阈值
        :param min_avg_similarity: 最小平均相似度底线
        """
        self.weight_component = weight_component
        self.weight_return = weight_return
        self.distance_threshold = distance_threshold
        self.min_avg_similarity = min_avg_similarity
        
    def load_etf_universe(self, path: str) -> pd.DataFrame:
        """加载ETF元数据"""
        df = pd.read_csv(path)
        return df[df['asset_class_l2'] == '行业主题'].copy()
    
    def get_index_components(self, index_code: str, index_dir: str) -> set:
        """获取指数成分股"""
        file_pattern = os.path.join(index_dir, f'{index_code}_*_index_weight.xls')
        files = glob.glob(file_pattern)
        
        if not files:
            return set()
        
        try:
            df = pd.read_excel(files[0], skiprows=1)
            return set(df.iloc[:, 4].astype(str).tolist())
        except:
            return set()
    
    def calculate_jaccard_similarity(self, index_codes: List[str], index_dir: str) -> pd.DataFrame:
        """计算Jaccard相似度矩阵"""
        n = len(index_codes)
        sim_matrix = np.zeros((n, n))
        
        # 预加载成分股
        components = {}
        for code in index_codes:
            components[code] = self.get_index_components(code, index_dir)
        
        # 计算相似度
        for i in range(n):
            for j in range(n):
                if i == j:
                    sim_matrix[i, j] = 1.0
                else:
                    set1 = components.get(index_codes[i], set())
                    set2 = components.get(index_codes[j], set())
                    intersection = len(set1.intersection(set2))
                    union = len(set1.union(set2))
                    if union > 0:
                        sim_matrix[i, j] = intersection / union
        
        return pd.DataFrame(sim_matrix, index=index_codes, columns=index_codes)
    
    def load_return_correlation(self, path: str) -> pd.DataFrame:
        """加载收益率相关性矩阵"""
        return pd.read_csv(path, index_col=0)
    
    def align_and_fuse(
        self,
        component_sim: pd.DataFrame,
        return_corr: pd.DataFrame,
        index_codes: List[str]
    ) -> Tuple[Optional[pd.DataFrame], List[str]]:
        """对齐并融合两种相似度"""
        # 创建映射
        return_codes = return_corr.index.tolist()
        code_mapping = {}
        for rc in return_codes:
            pure_code = rc.split('.')[0]
            code_mapping[pure_code] = rc
        
        # 找到共同代码
        common_codes = [code for code in index_codes if code in code_mapping]
        
        if len(common_codes) == 0:
            return None, []
        
        # 对齐矩阵
        comp_aligned = component_sim.loc[common_codes, common_codes]
        return_codes_aligned = [code_mapping[code] for code in common_codes]
        ret_aligned = return_corr.loc[return_codes_aligned, return_codes_aligned]
        ret_aligned.index = common_codes
        ret_aligned.columns = common_codes
        
        # 融合
        fused = self.weight_component * comp_aligned + self.weight_return * ret_aligned
        np.fill_diagonal(fused.values, 1.0)
        
        return fused, common_codes
    
    def hierarchical_clustering(self, sim_matrix: pd.DataFrame) -> np.ndarray:
        """层次聚类"""
        distance_matrix = 1 - sim_matrix
        np.fill_diagonal(distance_matrix.values, 0)
        distance_matrix = (distance_matrix + distance_matrix.T) / 2
        distance_condensed = squareform(distance_matrix.values)
        linkage_matrix = linkage(distance_condensed, method='ward')
        clusters = fcluster(linkage_matrix, self.distance_threshold, criterion='distance')
        return clusters
    
    def check_and_split_clusters(
        self,
        cluster_df: pd.DataFrame,
        sim_matrix: pd.DataFrame
    ) -> pd.DataFrame:
        """检查并拆分低相似度类别"""
        result_clusters = []
        current_max_id = cluster_df['cluster_id'].max()
        
        for cluster_id in sorted(cluster_df['cluster_id'].unique()):
            cluster_indices = cluster_df[cluster_df['cluster_id'] == cluster_id]['index_code'].tolist()
            
            if len(cluster_indices) <= 1:
                for idx in cluster_indices:
                    result_clusters.append({'index_code': idx, 'cluster_id': cluster_id})
                continue
            
            # 计算类内平均相似度
            sub_matrix = sim_matrix.loc[cluster_indices, cluster_indices]
            mask = np.triu(np.ones_like(sub_matrix, dtype=bool), k=1)
            avg_sim = sub_matrix.where(mask).stack().mean()
            
            if avg_sim >= self.min_avg_similarity:
                for idx in cluster_indices:
                    result_clusters.append({'index_code': idx, 'cluster_id': cluster_id})
            else:
                print(f"  类别{cluster_id}平均相似度{avg_sim:.4f} < {self.min_avg_similarity}，拆分为单指数类别")
                for idx in cluster_indices:
                    current_max_id += 1
                    result_clusters.append({'index_code': idx, 'cluster_id': current_max_id})
        
        return pd.DataFrame(result_clusters)
    
    def select_representative_etf(self, cluster_etfs: pd.DataFrame) -> Optional[pd.Series]:
        """选择代表性ETF（按规模）"""
        if len(cluster_etfs) == 0:
            return None
        return cluster_etfs.sort_values('fund_size', ascending=False).iloc[0]
    
    def analyze_sector(
        self,
        sector_name: str,
        sector_etfs: pd.DataFrame,
        return_corr: pd.DataFrame,
        index_dir: str
    ) -> List[Dict]:
        """分析单个板块"""
        print(f"\n{'='*60}")
        print(f"分析板块: {sector_name}")
        print(f"{'='*60}")
        
        # 获取指数代码
        index_codes = sector_etfs['index_code'].dropna().unique().tolist()
        index_codes = [code.split('.')[0] if '.' in str(code) else str(code) for code in index_codes]
        index_codes = list(set(index_codes))
        
        print(f"ETF数量: {len(sector_etfs)}")
        print(f"指数数量: {len(index_codes)}")
        
        if len(index_codes) < 2:
            print("指数数量不足，跳过聚类")
            return []
        
        # 计算相似度
        print("\n计算成分股相似度...")
        component_sim = self.calculate_jaccard_similarity(index_codes, index_dir)
        
        print("对齐并融合相似度...")
        fused_sim, common_codes = self.align_and_fuse(component_sim, return_corr, index_codes)
        
        if fused_sim is None or len(common_codes) < 2:
            print("共同指数不足，跳过聚类")
            return []
        
        print(f"共同指数数量: {len(common_codes)}")
        
        # 聚类
        print("进行层次聚类...")
        clusters = self.hierarchical_clustering(fused_sim)
        
        cluster_df = pd.DataFrame({
            'index_code': common_codes,
            'cluster_id': clusters
        })
        
        # 检查并拆分
        print("\n检查类别相似度...")
        cluster_df = self.check_and_split_clusters(cluster_df, fused_sim)
        
        n_clusters = cluster_df['cluster_id'].nunique()
        print(f"\n聚类完成: {n_clusters} 个类别")
        
        # 分析每个类别
        results = []
        for cluster_id in sorted(cluster_df['cluster_id'].unique()):
            cluster_indices = cluster_df[cluster_df['cluster_id'] == cluster_id]['index_code'].tolist()
            cluster_etfs = sector_etfs[sector_etfs['index_code'].str.split('.').str[0].isin(cluster_indices)]
            
            if len(cluster_indices) > 1:
                sub_matrix = fused_sim.loc[cluster_indices, cluster_indices]
                mask = np.triu(np.ones_like(sub_matrix, dtype=bool), k=1)
                avg_sim = sub_matrix.where(mask).stack().mean()
            else:
                avg_sim = 1.0
            
            rep_etf = self.select_representative_etf(cluster_etfs)
            
            result = {
                'sector_l1': sector_name,
                'cluster_id': cluster_id,
                'n_indices': len(cluster_indices),
                'n_etfs': len(cluster_etfs),
                'avg_similarity': avg_sim,
                'index_codes': cluster_indices,
                'etf_codes': cluster_etfs['code'].tolist() if len(cluster_etfs) > 0 else [],
                'representative_etf_code': rep_etf['code'] if rep_etf is not None else None,
                'representative_etf_name': rep_etf['name'] if rep_etf is not None else None,
                'representative_etf_size': rep_etf['fund_size'] if rep_etf is not None else None
            }
            results.append(result)
            
            print(f"\n类别 {cluster_id}:")
            print(f"  指数数量: {len(cluster_indices)}")
            print(f"  ETF数量: {len(cluster_etfs)}")
            print(f"  平均相似度: {avg_sim:.4f}")
            if rep_etf is not None:
                print(f"  代表性ETF: {rep_etf['code']} {rep_etf['name']} ({rep_etf['fund_size']:.1f}亿)")
        
        return results
    
    def cluster_by_sector(
        self,
        etf_universe_path: str,
        index_dir: str,
        corr_matrix_path: str
    ) -> pd.DataFrame:
        """
        按板块进行聚类分析
        
        :param etf_universe_path: ETF元数据文件路径
        :param index_dir: 指数成分股文件目录
        :param corr_matrix_path: 收益率相关性矩阵路径
        :return: 聚类结果DataFrame
        """
        print(f"{'='*60}")
        print(f"ETF聚类分析")
        print(f"参数: 成分股={self.weight_component}, 收益率={self.weight_return}")
        print(f"阈值: {self.distance_threshold}, 最小相似度: {self.min_avg_similarity}")
        print(f"{'='*60}")
        
        # 加载数据
        etf_df = self.load_etf_universe(etf_universe_path)
        return_corr = self.load_return_correlation(corr_matrix_path)
        
        # 按板块分析
        all_results = []
        for sector_name in sorted(etf_df['sector_l1'].dropna().unique()):
            sector_etfs = etf_df[etf_df['sector_l1'] == sector_name]
            results = self.analyze_sector(sector_name, sector_etfs, return_corr, index_dir)
            if results:
                all_results.extend(results)
        
        return pd.DataFrame(all_results)


# 便捷函数
def run_clustering(
    etf_universe_path: str = 'data_external/reference/etf_universe.csv',
    index_dir: str = 'D:/Study/Research/ETF/csindex',
    corr_matrix_path: str = 'data_runtime/index_correlation_matrix.csv',
    output_path: str = 'data_runtime/clustering_results.csv',
    **kwargs
) -> pd.DataFrame:
    """
    运行聚类分析的便捷函数
    
    :param etf_universe_path: ETF元数据路径
    :param index_dir: 指数成分股目录
    :param corr_matrix_path: 相关性矩阵路径
    :param output_path: 输出路径
    :param kwargs: 聚类参数（weight_component, weight_return等）
    :return: 聚类结果
    """
    cluster = ETFClustering(**kwargs)
    results = cluster.cluster_by_sector(etf_universe_path, index_dir, corr_matrix_path)
    results.to_csv(output_path, index=False)
    print(f"\n结果已保存: {output_path}")
    return results


if __name__ == '__main__':
    # 示例用法
    results = run_clustering()
    print(f"\n总类别数: {len(results)}")
