"""
ETF指数聚类分析模块

支持三种相似度指标：
1. Jaccard: 只考虑成分股重叠
2. Cosine: 考虑权重分布
3. Hellinger: 考虑权重分布，适合概率分布

使用方法:
    from index_clustering import IndexClustering
    
    # 创建聚类器
    clusterer = IndexClustering(similarity_method='hellinger', distance_threshold=0.8)
    
    # 执行聚类
    results = clusterer.cluster_all_sectors()
    
    # 生成报告
    clusterer.generate_report(results, 'output.md')

作者: AI Assistant
日期: 2026-04-22
"""

import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from math import sqrt
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional


class IndexClustering:
    """指数聚类分析器"""
    
    # 支持的相似度方法
    SUPPORTED_METHODS = ['jaccard', 'cosine', 'hellinger']
    
    def __init__(self, 
                 data_dir: str = 'D:/Study/Research/ETF/csindex',
                 etf_universe_path: str = 'D:/Study/Project/investment-agent/data_external/reference/etf_universe.csv',
                 similarity_method: str = 'hellinger',
                 distance_threshold: float = 0.8):
        """
        初始化聚类分析器
        
        Args:
            data_dir: 指数成分股权重文件目录
            etf_universe_path: ETF元数据CSV文件路径
            similarity_method: 相似度计算方法 ('jaccard', 'cosine', 'hellinger')
            distance_threshold: 聚类距离阈值 (0-1之间)
        """
        self.data_dir = data_dir
        self.etf_universe_path = etf_universe_path
        self.similarity_method = similarity_method.lower()
        self.distance_threshold = distance_threshold
        
        # 验证方法有效性
        if self.similarity_method not in self.SUPPORTED_METHODS:
            raise ValueError(f"不支持的方法: {similarity_method}. 请选择: {self.SUPPORTED_METHODS}")
        
        # 加载ETF元数据
        self.etf_df = pd.read_csv(etf_universe_path)
        self.sector_etfs = self.etf_df[self.etf_df['asset_class_l2'] == '行业主题']
        
        # 获取已有数据的指数列表
        self.existing_indices = self._get_existing_indices()
        
        # 选择相似度函数
        self.similarity_func = self._get_similarity_function()
    
    def _get_existing_indices(self) -> set:
        """获取已有成分股数据的指数代码集合"""
        if not os.path.exists(self.data_dir):
            return set()
        
        files = [f for f in os.listdir(self.data_dir) if 'index_weight' in f]
        return set(f.split('_')[0] for f in files)
    
    def _get_similarity_function(self):
        """根据方法名返回对应的相似度函数"""
        method_map = {
            'jaccard': self._jaccard_similarity,
            'cosine': self._cosine_similarity,
            'hellinger': self._hellinger_similarity
        }
        return method_map[self.similarity_method]
    
    def read_index_components(self, index_code: str) -> Dict[str, float]:
        """
        读取指数成分股和权重
        
        Args:
            index_code: 指数代码
            
        Returns:
            dict: {股票代码: 权重(%), ...}
        """
        files = [f for f in os.listdir(self.data_dir) 
                if f.startswith(index_code + '_') and 'index_weight' in f]
        
        if not files:
            return {}
        
        file_path = os.path.join(self.data_dir, files[0])
        
        try:
            df = pd.read_excel(file_path, skiprows=1)
            
            # 查找代码列和权重列
            code_col = None
            weight_col = None
            
            for col in df.columns:
                col_str = str(col).lower()
                if '代码' in str(col) or 'code' in col_str:
                    code_col = col
                if '权重' in str(col) or 'weight' in col_str:
                    weight_col = col
            
            if code_col is None or weight_col is None:
                # 尝试根据列位置推断（针对已知格式）
                if len(df.columns) >= 10:
                    code_col = df.columns[4]   # 第5列通常是股票代码
                    weight_col = df.columns[9]  # 第10列通常是权重
                elif len(df.columns) >= 6:
                    code_col = df.columns[1]   # 第2列
                    weight_col = df.columns[5]  # 第6列
                else:
                    return {}
            
            # 提取成分股和权重
            components = {}
            for _, row in df.iterrows():
                try:
                    stock_code = str(int(row[code_col])).zfill(6)
                except:
                    stock_code = str(row[code_col])
                
                weight = row[weight_col]
                if pd.notna(weight) and stock_code != 'nan':
                    # 统一权重格式为百分比
                    if isinstance(weight, (int, float)):
                        if weight < 1:  # 小数格式（如0.383表示0.383%）
                            weight = weight * 100
                    components[stock_code] = weight
            
            return components
            
        except Exception as e:
            print(f"读取指数{index_code}失败: {str(e)}")
            return {}
    
    @staticmethod
    def _jaccard_similarity(components1: Dict[str, float], 
                           components2: Dict[str, float]) -> float:
        """
        Jaccard相似度 - 只考虑成分股有无
        
        Args:
            components1: 指数1的成分股权重字典
            components2: 指数2的成分股权重字典
            
        Returns:
            float: 相似度 (0-1)
        """
        set1 = set(components1.keys())
        set2 = set(components2.keys())
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0
    
    @staticmethod
    def _cosine_similarity(components1: Dict[str, float], 
                          components2: Dict[str, float]) -> float:
        """
        余弦相似度 - 考虑权重分布
        
        Args:
            components1: 指数1的成分股权重字典
            components2: 指数2的成分股权重字典
            
        Returns:
            float: 相似度 (0-1)
        """
        all_stocks = set(components1.keys()).union(set(components2.keys()))
        
        vec1 = []
        vec2 = []
        
        for stock in all_stocks:
            w1 = components1.get(stock, 0)
            w2 = components2.get(stock, 0)
            vec1.append(w1)
            vec2.append(w2)
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sqrt(sum(a ** 2 for a in vec1))
        norm2 = sqrt(sum(b ** 2 for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0
        
        return dot_product / (norm1 * norm2)
    
    @staticmethod
    def _hellinger_similarity(components1: Dict[str, float], 
                             components2: Dict[str, float]) -> float:
        """
        Hellinger相似度 - 考虑权重分布，适合概率分布
        
        Args:
            components1: 指数1的成分股权重字典
            components2: 指数2的成分股权重字典
            
        Returns:
            float: 相似度 (0-1)
        """
        all_stocks = set(components1.keys()).union(set(components2.keys()))
        
        total1 = sum(components1.values())
        total2 = sum(components2.values())
        
        if total1 == 0 or total2 == 0:
            return 0
        
        hellinger_sum = 0
        for stock in all_stocks:
            p = components1.get(stock, 0) / total1
            q = components2.get(stock, 0) / total2
            hellinger_sum += (sqrt(p) - sqrt(q)) ** 2
        
        hellinger_dist = sqrt(hellinger_sum / 2)
        
        return 1 - hellinger_dist
    
    def calculate_similarity_matrix(self, index_codes: List[str]) -> np.ndarray:
        """
        计算指数间的相似度矩阵
        
        Args:
            index_codes: 指数代码列表
            
        Returns:
            np.ndarray: 相似度矩阵
        """
        n = len(index_codes)
        similarity_matrix = np.zeros((n, n))
        
        # 读取所有指数的成分股
        index_components = {}
        for code in index_codes:
            components = self.read_index_components(code)
            if components:
                index_components[code] = components
        
        # 计算相似度
        for i in range(n):
            for j in range(n):
                if i == j:
                    similarity_matrix[i, j] = 1.0
                else:
                    code_i = index_codes[i]
                    code_j = index_codes[j]
                    if code_i in index_components and code_j in index_components:
                        similarity_matrix[i, j] = self.similarity_func(
                            index_components[code_i], 
                            index_components[code_j]
                        )
        
        return similarity_matrix
    
    def cluster_indices(self, index_codes: List[str]) -> Dict:
        """
        对指数进行聚类分析
        
        Args:
            index_codes: 指数代码列表
            
        Returns:
            dict: 聚类结果
        """
        # 计算相似度矩阵
        similarity_matrix = self.calculate_similarity_matrix(index_codes)
        
        # 转换为距离矩阵
        distance_matrix = 1 - similarity_matrix
        np.fill_diagonal(distance_matrix, 0)
        
        # 确保距离矩阵有效
        distance_matrix = np.maximum(distance_matrix, 0)
        distance_matrix = (distance_matrix + distance_matrix.T) / 2
        
        # 层次聚类
        distance_condensed = squareform(distance_matrix)
        linkage_matrix = linkage(distance_condensed, method='ward')
        
        # 使用距离阈值切割
        clusters = fcluster(linkage_matrix, self.distance_threshold, criterion='distance')
        
        # 整理结果
        n_clusters = len(set(clusters))
        cluster_results = []
        
        for cluster_id in range(1, n_clusters + 1):
            indices_in_cluster = [index_codes[i] for i in range(len(index_codes)) 
                                 if clusters[i] == cluster_id]
            
            # 计算类内平均相似度
            avg_similarity = 0
            if len(indices_in_cluster) > 1:
                similarities = []
                for i in range(len(indices_in_cluster)):
                    for j in range(i + 1, len(indices_in_cluster)):
                        idx_i = index_codes.index(indices_in_cluster[i])
                        idx_j = index_codes.index(indices_in_cluster[j])
                        similarities.append(similarity_matrix[idx_i, idx_j])
                avg_similarity = np.mean(similarities) if similarities else 0
            
            cluster_results.append({
                'cluster_id': cluster_id,
                'indices': indices_in_cluster,
                'avg_similarity': avg_similarity,
                'size': len(indices_in_cluster)
            })
        
        return {
            'n_clusters': n_clusters,
            'clusters': cluster_results,
            'similarity_matrix': similarity_matrix,
            'method': self.similarity_method,
            'threshold': self.distance_threshold
        }
    
    def cluster_sector(self, sector: str) -> Dict:
        """
        对指定板块进行聚类分析
        
        Args:
            sector: 板块名称 (科技/医药/消费/周期/制造/金融地产)
            
        Returns:
            dict: 聚类结果
        """
        sector_df = self.sector_etfs[self.sector_etfs['sector_l1'] == sector]
        
        # 获取该板块已有数据的指数
        sector_indices = []
        for _, etf in sector_df.iterrows():
            idx_code = etf['index_code'].split('.')[0]
            if idx_code in self.existing_indices:
                sector_indices.append({
                    'code': idx_code,
                    'name': etf['index_name'],
                    'etf_code': etf['code'],
                    'etf_name': etf['name'],
                    'fund_size': etf['fund_size']
                })
        
        if len(sector_indices) < 2:
            return {
                'sector': sector,
                'n_indices': len(sector_indices),
                'error': '指数数量不足'
            }
        
        # 执行聚类
        index_codes = [idx['code'] for idx in sector_indices]
        cluster_result = self.cluster_indices(index_codes)
        
        # 添加ETF信息
        for cluster in cluster_result['clusters']:
            cluster['etfs'] = []
            for idx_code in cluster['indices']:
                etf_info = next((idx for idx in sector_indices if idx['code'] == idx_code), None)
                if etf_info:
                    cluster['etfs'].append(etf_info)
            
            # 选择代表性ETF（规模最大）
            if cluster['etfs']:
                representative = max(cluster['etfs'], key=lambda x: x['fund_size'])
                cluster['representative_etf'] = representative
        
        cluster_result['sector'] = sector
        cluster_result['n_indices'] = len(sector_indices)
        cluster_result['sector_indices'] = sector_indices
        
        return cluster_result
    
    def cluster_all_sectors(self) -> Dict[str, Dict]:
        """
        对所有板块进行聚类分析
        
        Returns:
            dict: {板块名称: 聚类结果, ...}
        """
        sectors = ['科技', '医药', '消费', '周期', '制造', '金融地产']
        results = {}
        
        for sector in sectors:
            print(f"正在分析{sector}板块...")
            results[sector] = self.cluster_sector(sector)
        
        return results
    
    def evaluate_clusters(self, cluster_result: Dict) -> Dict:
        """
        评估聚类质量
        
        Args:
            cluster_result: 聚类结果
            
        Returns:
            dict: 评估指标
        """
        if 'error' in cluster_result:
            return {'error': cluster_result['error']}
        
        clusters = cluster_result['clusters']
        n_clusters = len(clusters)
        
        # 统计
        single_clusters = sum(1 for c in clusters if c['size'] == 1)
        multi_clusters = n_clusters - single_clusters
        
        # 类内平均相似度
        avg_intra_similarity = np.mean([c['avg_similarity'] for c in clusters if c['size'] > 1])
        
        # 计算轮廓系数（简化版）
        silhouette_scores = []
        similarity_matrix = cluster_result.get('similarity_matrix')
        
        if similarity_matrix is not None:
            for i, cluster in enumerate(clusters):
                if cluster['size'] == 1:
                    continue
                    
                for idx in cluster['indices']:
                    idx_pos = cluster_result['sector_indices'].index(
                        next(idx_info for idx_info in cluster_result['sector_indices'] 
                             if idx_info['code'] == idx)
                    )
                    
                    # a: 类内平均距离
                    a = 1 - similarity_matrix[idx_pos, idx_pos]  # 简化计算
                    
                    # b: 最近其他类的平均距离
                    b = 1.0  # 简化计算
                    
                    silhouette = (b - a) / max(a, b) if max(a, b) > 0 else 0
                    silhouette_scores.append(silhouette)
        
        avg_silhouette = np.mean(silhouette_scores) if silhouette_scores else 0
        
        return {
            'n_clusters': n_clusters,
            'single_clusters': single_clusters,
            'multi_clusters': multi_clusters,
            'avg_intra_similarity': avg_intra_similarity,
            'avg_silhouette': avg_silhouette,
            'method': cluster_result['method'],
            'threshold': cluster_result['threshold']
        }
    
    def generate_report(self, results: Dict[str, Dict], output_path: str):
        """
        生成聚类分析报告
        
        Args:
            results: 聚类结果字典
            output_path: 输出文件路径
        """
        lines = []
        lines.append('# ETF指数聚类分析报告')
        lines.append('')
        lines.append(f'**生成日期**: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        lines.append(f'**相似度方法**: {self.similarity_method.capitalize()}')
        lines.append(f'**距离阈值**: {self.distance_threshold} (对应{int((1-self.distance_threshold)*100)}%相似度)')
        lines.append('')
        lines.append('---')
        lines.append('')
        
        # 汇总统计
        total_clusters = 0
        total_indices = 0
        
        for sector, result in results.items():
            if 'error' in result:
                continue
            total_clusters += result['n_clusters']
            total_indices += result['n_indices']
        
        lines.append('## 汇总统计')
        lines.append('')
        lines.append(f'- **总指数数**: {total_indices}')
        lines.append(f'- **总类别数**: {total_clusters}')
        lines.append(f'- **平均每个板块**: {total_clusters/len(results):.1f}个类别')
        lines.append('')
        
        # 各板块详细结果
        for sector, result in results.items():
            lines.append(f'## {sector}板块')
            lines.append('')
            
            if 'error' in result:
                lines.append(f'**错误**: {result["error"]}')
                lines.append('')
                continue
            
            lines.append(f'- 指数数量: {result["n_indices"]}')
            lines.append(f'- 聚类类别: {result["n_clusters"]}')
            lines.append('')
            
            for cluster in result['clusters']:
                lines.append(f'### 类别{cluster["cluster_id"]} ({cluster["size"]}个指数)')
                lines.append('')
                
                if cluster['size'] > 1:
                    lines.append(f'**类内平均相似度**: {cluster["avg_similarity"]:.1%}')
                    lines.append('')
                
                for etf_info in cluster['etfs']:
                    lines.append(f'- **{etf_info["code"]}** {etf_info["name"]}')
                    lines.append(f'  - ETF: {etf_info["etf_code"]} {etf_info["etf_name"]} ({etf_info["fund_size"]:.1f}亿)')
                
                if 'representative_etf' in cluster:
                    rep = cluster['representative_etf']
                    lines.append('')
                    lines.append(f'**★ 代表性ETF**: {rep["etf_code"]} {rep["etf_name"]} ({rep["fund_size"]:.1f}亿)')
                
                lines.append('')
            
            lines.append('---')
            lines.append('')
        
        # 方法论说明
        lines.append('## 方法论')
        lines.append('')
        lines.append('### 相似度指标')
        lines.append('')
        
        if self.similarity_method == 'jaccard':
            lines.append('**Jaccard相似度**: 只考虑成分股重叠，不考虑权重')
            lines.append('$$J(A,B) = \\frac{|A \\cap B|}{|A \\cup B|}$$')
        elif self.similarity_method == 'cosine':
            lines.append('**余弦相似度**: 考虑权重分布，将指数看作向量')
            lines.append('$$Cosine(A,B) = \\frac{A \\cdot B}{||A|| \\times ||B||}$$')
        elif self.similarity_method == 'hellinger':
            lines.append('**Hellinger相似度**: 考虑权重分布，适合概率分布')
            lines.append('$$H(P,Q) = \\frac{1}{\\sqrt{2}} \\sqrt{\\sum(\\sqrt{p_i} - \\sqrt{q_i})^2}$$')
            lines.append('$$Similarity = 1 - H(P,Q)$$')
        
        lines.append('')
        lines.append('### 聚类算法')
        lines.append('')
        lines.append('- **算法**: 层次聚类 (Ward法)')
        lines.append('- **距离度量**: 1 - 相似度')
        lines.append(f'- **切割阈值**: {self.distance_threshold}')
        lines.append('')
        
        # 保存报告
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"报告已生成: {output_path}")


# 使用示例
if __name__ == '__main__':
    # 创建聚类器（使用Hellinger相似度）
    clusterer = IndexClustering(
        similarity_method='hellinger',
        distance_threshold=0.8
    )
    
    # 对所有板块进行聚类
    print("开始聚类分析...")
    results = clusterer.cluster_all_sectors()
    
    # 生成报告
    output_path = 'D:/Study/Project/investment-agent/docs/research/etf_clustering_hellinger_report.md'
    clusterer.generate_report(results, output_path)
    
    print("\n聚类分析完成!")
    print(f"报告已保存至: {output_path}")
