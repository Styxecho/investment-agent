#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
按一级分类进行双维度聚类分析（v4 - 平衡版本）

参数:
- 聚类阈值: 0.8
- 成分股权重: 60%（中间方案）
- 收益率权重: 40%
- 最小相似度底线: 0.4
"""

import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')

import pandas as pd
import numpy as np
import sqlite3
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
import glob
import os

# 配置
DB_PATH = r'D:\Study\Project\investment-agent\data_external\db\external_data.db'
ETF_UNIVERSE_PATH = r'D:\Study\Project\investment-agent\data_external\reference\etf_universe.csv'
INDEX_DIR = r'D:\Study\Research\ETF\csindex'
CORR_MATRIX_PATH = r'D:\Study\Project\investment-agent\data_runtime\index_correlation_matrix.csv'

# v4参数 - 平衡方案
WEIGHT_COMPONENT = 0.6    # 成分股60%
WEIGHT_RETURN = 0.4       # 收益率40%
DISTANCE_THRESHOLD = 0.8  # 阈值0.8
MIN_AVG_SIMILARITY = 0.4  # 最小相似度0.4


def load_etf_universe():
    df = pd.read_csv(ETF_UNIVERSE_PATH)
    sector_etfs = df[df['asset_class_l2'] == '行业主题'].copy()
    return sector_etfs


def get_index_components(index_code):
    file_pattern = os.path.join(INDEX_DIR, f'{index_code}_*_index_weight.xls')
    files = glob.glob(file_pattern)
    if not files:
        return set()
    try:
        df = pd.read_excel(files[0], skiprows=1)
        components = set(df.iloc[:, 4].astype(str).tolist())
        return components
    except:
        return set()


def calculate_jaccard_similarity(index_codes):
    n = len(index_codes)
    sim_matrix = np.zeros((n, n))
    components = {}
    for code in index_codes:
        components[code] = get_index_components(code)
    
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


def load_return_correlation():
    return pd.read_csv(CORR_MATRIX_PATH, index_col=0)


def align_and_fuse(component_sim, return_corr, index_codes):
    return_codes = return_corr.index.tolist()
    code_mapping = {}
    for rc in return_codes:
        pure_code = rc.split('.')[0]
        code_mapping[pure_code] = rc
    
    common_codes = [code for code in index_codes if code in code_mapping]
    if len(common_codes) == 0:
        return None, []
    
    comp_aligned = component_sim.loc[common_codes, common_codes]
    return_codes_aligned = [code_mapping[code] for code in common_codes]
    ret_aligned = return_corr.loc[return_codes_aligned, return_codes_aligned]
    ret_aligned.index = common_codes
    ret_aligned.columns = common_codes
    
    # 融合: 60%成分股 + 40%收益率
    fused = WEIGHT_COMPONENT * comp_aligned + WEIGHT_RETURN * ret_aligned
    np.fill_diagonal(fused.values, 1.0)
    return fused, common_codes


def hierarchical_clustering(sim_matrix, distance_threshold=0.8):
    distance_matrix = 1 - sim_matrix
    np.fill_diagonal(distance_matrix.values, 0)
    distance_matrix = (distance_matrix + distance_matrix.T) / 2
    distance_condensed = squareform(distance_matrix.values)
    linkage_matrix = linkage(distance_condensed, method='ward')
    clusters = fcluster(linkage_matrix, distance_threshold, criterion='distance')
    return clusters


def check_and_split_clusters(cluster_df, sim_matrix, min_avg_sim=0.4):
    result_clusters = []
    current_max_id = cluster_df['cluster_id'].max()
    
    for cluster_id in sorted(cluster_df['cluster_id'].unique()):
        cluster_indices = cluster_df[cluster_df['cluster_id'] == cluster_id]['index_code'].tolist()
        
        if len(cluster_indices) <= 1:
            for idx in cluster_indices:
                result_clusters.append({'index_code': idx, 'cluster_id': cluster_id})
            continue
        
        sub_matrix = sim_matrix.loc[cluster_indices, cluster_indices]
        mask = np.triu(np.ones_like(sub_matrix, dtype=bool), k=1)
        avg_sim = sub_matrix.where(mask).stack().mean()
        
        if avg_sim >= min_avg_sim:
            for idx in cluster_indices:
                result_clusters.append({'index_code': idx, 'cluster_id': cluster_id})
        else:
            print(f"  类别{cluster_id}平均相似度{avg_sim:.4f} < {min_avg_sim}，拆分为单指数类别")
            for idx in cluster_indices:
                current_max_id += 1
                result_clusters.append({'index_code': idx, 'cluster_id': current_max_id})
    
    return pd.DataFrame(result_clusters)


def select_representative_etf(cluster_etfs):
    if len(cluster_etfs) == 0:
        return None
    cluster_etfs_sorted = cluster_etfs.sort_values('fund_size', ascending=False)
    return cluster_etfs_sorted.iloc[0]


def analyze_sector(sector_name, sector_etfs, return_corr):
    print(f"\n{'='*60}")
    print(f"分析板块: {sector_name}")
    print(f"{'='*60}")
    
    index_codes = sector_etfs['index_code'].dropna().unique().tolist()
    index_codes = [code.split('.')[0] if '.' in str(code) else str(code) for code in index_codes]
    index_codes = list(set(index_codes))
    
    print(f"ETF数量: {len(sector_etfs)}")
    print(f"指数数量: {len(index_codes)}")
    
    if len(index_codes) < 2:
        print("指数数量不足，跳过聚类")
        return None
    
    print("\n计算成分股相似度...")
    component_sim = calculate_jaccard_similarity(index_codes)
    
    print("对齐并融合相似度...")
    fused_sim, common_codes = align_and_fuse(component_sim, return_corr, index_codes)
    
    if fused_sim is None or len(common_codes) < 2:
        print("共同指数不足，跳过聚类")
        return None
    
    print(f"共同指数数量: {len(common_codes)}")
    
    print("进行层次聚类...")
    clusters = hierarchical_clustering(fused_sim, distance_threshold=DISTANCE_THRESHOLD)
    
    cluster_df = pd.DataFrame({
        'index_code': common_codes,
        'cluster_id': clusters
    })
    
    print("\n检查类别相似度...")
    cluster_df = check_and_split_clusters(cluster_df, fused_sim, MIN_AVG_SIMILARITY)
    
    n_clusters = cluster_df['cluster_id'].nunique()
    print(f"\n聚类完成: {n_clusters} 个类别")
    
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
        
        rep_etf = select_representative_etf(cluster_etfs)
        
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


def main():
    print(f"{'='*60}")
    print(f"双维度聚类分析 v4 - 平衡方案")
    print(f"参数: 成分股={WEIGHT_COMPONENT}, 收益率={WEIGHT_RETURN}")
    print(f"阈值: {DISTANCE_THRESHOLD}, 最小相似度: {MIN_AVG_SIMILARITY}")
    print(f"{'='*60}")
    
    etf_df = load_etf_universe()
    return_corr = load_return_correlation()
    
    all_results = []
    for sector_name in sorted(etf_df['sector_l1'].dropna().unique()):
        sector_etfs = etf_df[etf_df['sector_l1'] == sector_name]
        results = analyze_sector(sector_name, sector_etfs, return_corr)
        if results:
            all_results.extend(results)
    
    if all_results:
        results_df = pd.DataFrame(all_results)
        output_path = r'D:\Study\Project\investment-agent\data_runtime\sector_clustering_results_v4.csv'
        results_df.to_csv(output_path, index=False)
        print(f"\n\n结果已保存: {output_path}")
        
        print(f"\n{'='*60}")
        print("汇总")
        print(f"{'='*60}")
        print(f"总类别数: {len(results_df)}")
        print(f"总代表性ETF数: {results_df['representative_etf_code'].notna().sum()}")
        
        for sector in sorted(results_df['sector_l1'].unique()):
            sector_results = results_df[results_df['sector_l1'] == sector]
            print(f"\n{sector}: {len(sector_results)} 个类别")
            for _, row in sector_results.iterrows():
                if row['representative_etf_code']:
                    print(f"  类别{row['cluster_id']}: {row['representative_etf_code']} ({row['representative_etf_size']:.1f}亿) [相似度:{row['avg_similarity']:.3f}]")
    
    print(f"\n{'='*60}")
    print("分析完成!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
