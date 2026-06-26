# Phase 2.2 Summary - ETF聚类筛选

**阶段**: Phase 2.2
**名称**: ETF聚类筛选（双维度聚类分析）
**时间**: 2026-04-23
**状态**: 已完成

---

## 1. 完成内容

### 1.1 核心任务
- 基于成分股重叠度和收益率相关性，对122只行业主题ETF进行双维度聚类
- 在6大板块（科技/医药/消费/周期/制造/金融地产）内部分别聚类
- 生成二级分类标签（sector_l2），更新etf_universe.csv

### 1.2 技术实现
- 实现双维度相似度计算（Jaccard + Pearson）
- 层次聚类算法（Ward法）
- 质量管控机制（最小相似度底线0.4）
- 人工修正机制（医药板块细分）

### 1.3 数据工作
- 提取104个指数自2025-12-31以来的历史价格数据（8,030条记录）
- 计算收益率相关性矩阵
- 读取135个指数成分股权重文件

---

## 2. 关键决策与假设

### 2.1 参数选择
- **成分股权重60% + 收益率40%**：平衡本质相似性和市场表现
- **聚类阈值0.8**：避免过度拆分
- **最小相似度0.4**：防止伪聚类

### 2.2 方法论决策
- **先按sector_l1分组，再聚类**：利用先验知识，避免跨板块误判
- **算法+人工结合**：算法提供基础，人工修正符合业务逻辑
- **海外指数保留原标签**：缺少成分股数据，由人工判断

### 2.3 关键假设
- 成分股权重数据反映指数本质特征
- 近期收益率（72个交易日）反映市场联动性
- 规模是代表性ETF的首要筛选标准

---

## 3. 当前缺陷

### 3.1 数据局限
- 成分股数据为静态（最新一期），未考虑历史变化
- 收益率期间较短（72个交易日），可能受短期噪声影响
- 部分指数（港股/海外）缺少成分股数据

### 3.2 算法局限
- 层次聚类对阈值敏感
- 无法自动确定最优类别数
- 单指数类别过多（29个），聚类意义有限

### 3.3 实务局限
- 部分板块分类仍较粗糙（如消费板块）
- 代表性ETF筛选仅考虑规模，未考虑费率、跟踪误差等
- 需要定期更新（建议每半年）

---

## 4. 后续扩展点

### 4.1 短期优化
- 完善代表性ETF筛选标准（加入费率、跟踪误差、历史长度）
- 人工审核每个类别，特别是单指数类别
- 建立动态更新机制

### 4.2 中期优化
- 使用更长时间窗口验证聚类稳定性
- 引入三级分类（更细分）
- 开发自动化更新脚本

### 4.3 长期扩展
- 跨板块分析，识别"跨界"ETF
- 结合宏观信号，动态调整类别权重
- 建立ETF相似度实时监控系统

---

## 5. 关键成果

### 5.1 分类体系
- **一级分类（sector_l1）**: 6大板块（科技/医药/消费/周期/制造/金融地产）
- **二级分类（sector_l2）**: 44个细类
- **代表性ETF**: 44只

### 5.2 文档输出
- 聚类报告: `docs/research/phase2.2_clustering_report.md`
- 更新后的ETF标签: `data_external/reference/etf_universe_v3.csv`

### 5.3 脚本资产与使用说明

#### 核心工具类

| 脚本 | 用途 | 使用场景 | 复用性 |
|------|------|----------|--------|
| `scripts/etf_clustering.py` | ETF聚类工具类 | 双维度聚类分析主入口 | **高** - 可配置参数，支持任意板块 |
| `scripts/sector_based_clustering_v4.py` | v4聚类实现 | 本次Phase 2.2的具体实现 | 中 - 可作为参考实现 |

#### 数据获取脚本

| 脚本 | 用途 | 使用场景 | 复用性 |
|------|------|----------|--------|
| `scripts/fetch_index_prices.py` | 批量提取指数价格 | 从iFinD获取指数历史数据 | **高** - 支持任意指数列表 |
| `scripts/calculate_index_correlation.py` | 计算收益率相关性 | 基于价格数据计算相关性矩阵 | **高** - 支持任意日期范围 |

#### 辅助工具脚本

| 脚本 | 用途 | 使用场景 | 复用性 |
|------|------|----------|--------|
| `scripts/check_index_files.py` | 检查指数文件完整性 | 验证成分股文件是否损坏 | **高** - 定期数据质量检查 |
| `scripts/download_guozheng_indices.py` | 批量下载国证指数 | 从国证官网批量下载成分股 | **高** - 数据更新时使用 |
| `scripts/update_etf_universe_tags.py` | 更新ETF标签 | 根据聚类结果更新sector_l2 | 中 - 需配合聚类结果使用 |

#### 使用示例

```python
# 使用ETFClustering工具类进行聚类
from scripts.etf_clustering import ETFClustering

cluster = ETFClustering(
    weight_component=0.6,      # 成分股权重
    weight_return=0.4,         # 收益率权重
    distance_threshold=0.8,    # 聚类阈值
    min_avg_similarity=0.4     # 最小相似度底线
)

results = cluster.cluster_by_sector(
    etf_universe_path='data_external/reference/etf_universe.csv',
    index_dir='D:/Study/Research/ETF/csindex',
    corr_matrix_path='data_runtime/index_correlation_matrix.csv'
)
```

#### 数据流脚本组合

```
1. 获取指数价格: fetch_index_prices.py
   ↓
2. 计算相关性: calculate_index_correlation.py
   ↓
3. 执行聚类: etf_clustering.py
   ↓
4. 更新标签: update_etf_universe_tags.py
```

---

## 6. 相关文档

- **详细报告**: [phase2.2_clustering_report.md](phase2.2_clustering_report.md)
- **项目路线图**: [roadmap/project_roadmap.md](../roadmap/project_roadmap.md)
- **项目记忆**: [project_memory.md](../../project_memory.md)

---

*本总结为Phase 2.2的阶段性归档，详细数据和分析请参阅完整报告。*
