# Filtered Historical Simulation (FHS) 方法计算股票组合 CVaR

## 1. 概述

本文档详细描述使用 **Filtered Historical Simulation (FHS)** 方法计算股票组合 **CVaR (Conditional Value at Risk)** 的实现步骤。

### 1.1 方法简介

FHS 方法结合了参数化波动率模型（EWMA）与非参数化历史模拟的优势：
- **优点 1**: 通过 EWMA 捕捉波动率时变特性
- **优点 2**: 利用历史残差保留实际收益率的厚尾特征
- **优点 3**: 避免正态分布假设的局限性

### 1.2 核心参数配置

| 参数 | 值 | 说明 |
|------|-----|------|
| 股票数量 | 30 | 组合包含的股票数量 |
| 波动率模型 | EWMA | 指数加权移动平均 |
| 窗口长度 | 60 日 | 波动率计算的历史窗口 |
| 衰减参数 (λ) | 0.96 | EWMA 衰减系数 |
| 默认置信度 | 95% | CVaR 计算置信水平 |
| 组合聚合 | 简单加权 | 基于市值权重的线性组合 |

---

## 2. 输入数据结构

### 2.1 历史收益率数据

假设可通过数据接口或文件获取以下结构的数据：

```
日期, 股票1代码, 股票2代码, ..., 股票30代码
2024-01-01, 0.015, -0.008, ..., 0.003
2024-01-02, -0.012, 0.021, ..., -0.007
...
```

**数据要求**:
- 日收益率序列（建议至少 252 个交易日，即一年数据）
- 收益率计算公式: `r_t = ln(P_t / P_{t-1})` 或 `(P_t - P_{t-1}) / P_{t-1}`
- 数据频率: 日度
- 数据完整性: 处理停牌、缺失值

### 2.2 组合权重数据

```
日期, 股票1权重, 股票2权重, ..., 股票30权重
2024-01-01, 0.035, 0.028, ..., 0.041
2024-01-02, 0.034, 0.029, ..., 0.040
...
```

**数据要求**:
- 权重基于每日市值计算
- 权重之和为 1（或接近 1，允许舍入误差）
- 频率: 日度（与收益率数据对齐）

---

## 3. 详细实现步骤

### Step 1: 数据预处理与加载

**目标**: 读取并验证历史收益率和权重数据

**操作步骤**:
1. **数据加载**: 从文件或接口读取历史收益率矩阵 `R` (T × 30)
2. **权重加载**: 读取每日权重矩阵 `W` (T × 30)
3. **日期对齐**: 确保收益率和权重日期索引一致
4. **缺失值处理**:
   - 对于停牌股票: 使用前一日收益率填充或使用 0 填充
   - 对于缺失权重: 使用前一日权重填充或等权重分配
5. **数据验证**:
   - 检查收益率合理性（范围通常在 [-0.5, 0.5] 内）
   - 验证权重和是否接近 1

**输出**:
- `returns_df`: 清洗后的日收益率 DataFrame (T × 30)
- `weights_df`: 清洗后的日权重 DataFrame (T × 30)

---

### Step 2: EWMA 波动率估计

**目标**: 为每只股票计算时变波动率 σ_t

**EWMA 公式**:

$$
\sigma_t^2 = \lambda \cdot \sigma_{t-1}^2 + (1-\lambda) \cdot r_{t-1}^2
$$

其中:
- σ_t: 第 t 日的条件波动率（标准差）
- λ: 衰减参数 = 0.96
- r_{t-1}: 第 t-1 日的收益率

**初始化**:
- 使用前 60 日收益率的样本标准差作为初始值 σ_0

**操作步骤**:

1. **初始化**:
   ```python
   对于每只股票 i (i = 1 到 30):
       σ_0[i] = std(returns[0:60, i])
   ```

2. **递归计算波动率** (从 t=61 开始):
   ```python
   对于每个时间点 t (从 61 到 T):
       对于每只股票 i (i = 1 到 30):
           variance_t[i] = λ * variance_{t-1}[i] + (1-λ) * (r_{t-1}[i])^2
           σ_t[i] = sqrt(variance_t[i])
   ```

3. **构建波动率矩阵**: `volatility_df` (T × 30)

**输出**:
- `volatility_df`: 每日条件波动率矩阵 (T × 30)
- 波动率应与收益率同维度，前 60 日为初始化期

---

### Step 3: 标准化残差计算

**目标**: 提取收益率中的"纯净"随机成分

**公式**:

$$
z_t = \frac{r_t}{\sigma_t}
$$

其中:
- z_t: 标准化残差
- r_t: 实际日收益率
- σ_t: EWMA 估计的条件波动率

**操作步骤**:

1. **逐元素计算**:
   ```python
   对于每个时间点 t (从 61 到 T):
       对于每只股票 i (i = 1 到 30):
           如果 σ_t[i] > 0:
               z_t[i] = r_t[i] / σ_t[i]
           否则:
               z_t[i] = 0  # 或标记为缺失
   ```

2. **残差矩阵**: `residuals_df` (T × 30)

**验证**:
- 残差序列应近似白噪声（均值接近 0，无明显自相关）
- 残差的标准差应接近 1

**输出**:
- `residuals_df`: 标准化残差矩阵 (T × 30)

---

### Step 4: 计算组合收益率

**目标**: 计算组合层面的实际收益率和波动率

**操作步骤**:

1. **组合日收益率**:
   ```python
   对于每个时间点 t:
       portfolio_return[t] = Σ (w_t[i] * r_t[i])  (i = 1 到 30)
   ```

2. **组合标准化残差**（关键步骤）:
   ```python
   对于每个时间点 t:
       portfolio_residual[t] = Σ (w_t[i] * z_t[i])  (i = 1 到 30)
   ```
   
   *注意*: 这里使用当日的权重对标准化残差进行加权

3. **组合当前波动率**:
   ```python
   对于每个时间点 t:
       portfolio_volatility[t] = Σ (w_t[i] * σ_t[i])  (i = 1 到 30)
   ```

**输出**:
- `portfolio_returns`: 组合实际收益率序列 (T × 1)
- `portfolio_residuals`: 组合标准化残差序列 (T × 1)
- `portfolio_volatility`: 组合条件波动率序列 (T × 1)

---

### Step 5: VaR 计算（历史模拟法）

**目标**: 基于标准化残差的历史分布计算 VaR

**原理**: 
FHS 的核心思想是：用历史标准化残差模拟未来收益率，再用当前波动率进行调整。

$$
\tilde{r}_{t+1} = \sigma_{t+1} \cdot z_{hist}
$$

其中 z_{hist} 从历史残差中抽样。

**操作步骤**:

1. **确定历史残差样本**:
   - 使用过去 N 个交易日的组合标准化残差（建议 N = 252，即一年）
   - 样本: `portfolio_residuals[t-N:t]`

2. **排序与分位数确定**:
   ```python
   将历史残差按从小到大排序
   确定置信水平 α (默认 0.95)
   找到 α 分位数位置: index = floor((1-α) * N)
   z_α = sorted_residuals[index]  # 5% 分位数（左侧尾部）
   ```

3. **计算 VaR**:
   ```python
   VaR_t = portfolio_volatility[t] * z_α
   ```
   
   注意: VaR 为负数表示损失，报告时可取绝对值或使用 -VaR 表示损失金额

**置信度参数化**:
- 默认 α = 0.95（95% 置信度）
- 可配置为 0.99（99% 置信度）等
- 不同置信度对应不同的分位数

**输出**:
- `VaR_series`: 每日 VaR 值序列 (T × 1)

---

### Step 6: CVaR 计算（尾部平均）

**目标**: 计算超过 VaR 阈值的平均损失

**定义**:
CVaR（或 Expected Shortfall, ES）是收益率分布在 VaR 左侧尾部的条件期望：

$$
CVaR_α = E[r \mid r \leq VaR_α]
$$

**操作步骤**:

1. **识别尾部事件**:
   ```python
   对于每个时间点 t:
       确定历史残差中小于 z_α 的所有值: tail_residuals = {z_i | z_i ≤ z_α}
   ```

2. **计算尾部平均残差**:
   ```python
   z_CVaR = mean(tail_residuals)
   ```

3. **计算 CVaR**:
   ```python
   CVaR_t = portfolio_volatility[t] * z_CVaR
   ```

**解释**:
- CVaR ≤ VaR（因为 CVaR 是更极端的平均损失）
- CVaR 始终为负值（表示损失）
- |CVaR| > |VaR|（CVaR 的绝对值大于 VaR）

**输出**:
- `CVaR_series`: 每日 CVaR 值序列 (T × 1)

---

### Step 7: 结果整合与报告

**目标**: 生成 CVaR 分析报告

**输出内容**:

1. **每日风险指标 DataFrame**:
   ```
   日期, 组合收益率, 组合波动率, VaR (95%), CVaR (95%)
   2024-01-01, 0.012, 0.018, -0.028, -0.035
   2024-01-02, -0.008, 0.019, -0.030, -0.038
   ...
   ```

2. **汇总统计**:
   - 平均 VaR 和 CVaR
   - VaR 和 CVaR 的最大/最小值
   - CVaR/VaR 比率（通常在 1.2-1.5 之间）
   - 突破 VaR 的实际次数与理论预期对比（预期约 5%）

3. **可视化** (可选):
   - 组合收益率时间序列与 VaR/CVaR 阈值对比图
   - CVaR 和 VaR 的时序图
   - 残差分布直方图与正态分布对比

---

## 4. 数学公式总结

### 4.1 EWMA 波动率

$$
\sigma_t^2 = 0.96 \cdot \sigma_{t-1}^2 + 0.04 \cdot r_{t-1}^2
$$

### 4.2 标准化残差

$$
z_t = \frac{r_t}{\sigma_t}
$$

### 4.3 组合层面聚合

**组合收益率**:
$$
r_t^p = \sum_{i=1}^{30} w_{t,i} \cdot r_{t,i}
$$

**组合残差**:
$$
z_t^p = \sum_{i=1}^{30} w_{t,i} \cdot z_{t,i}
$$

**组合波动率**:
$$
\sigma_t^p = \sum_{i=1}^{30} w_{t,i} \cdot \sigma_{t,i}
$$

### 4.4 VaR 计算

$$
VaR_{α,t} = \sigma_t^p \cdot z_{α}
$$

其中 z_{α} 是标准化残差的历史 α 分位数。

### 4.5 CVaR 计算

$$
CVaR_{α,t} = \sigma_t^p \cdot \frac{1}{N_{tail}} \sum_{i: z_i \leq z_α} z_i
$$

---

## 5. 后续扩展计划

### 5.1 短期优化

1. **数据接口集成**:
   - 对接实际行情数据 API
   - 实现自动权重计算（基于市值）
   - 添加数据质量检查模块

2. **模型验证**:
   - 回测 VaR/CVaR 的准确性（Kupiec 检验、Christoffersen 检验）
   - 比较不同置信度下的表现
   - 分析 CVaR 的次可加性

3. **性能优化**:
   - 向量化计算（避免循环）
   - 增量更新（只计算最新一日）
   - 并行处理多只股票

### 5.2 中期扩展

1. **多因子模型**:
   - 引入 Fama-French 三因子/五因子
   - 分解组合风险来源

2. **压力测试**:
   - 情景分析（市场危机、流动性冲击）
   - 蒙特卡洛模拟补充历史模拟

3. **报告自动化**:
   - 生成 PDF/Excel 风险报告
   - 定时邮件推送
   - 可视化仪表板

### 5.3 长期规划

1. **Copula 方法**:
   - 考虑股票间非线性相关性
   - 使用 t-Copula 或 Archimedean Copula

2. **高频数据**:
   - 使用日内数据计算日内 CVaR
   - 实现波动率的高频估计（已实现波动率）

3. **期权调整**:
   - 对于含期权的组合，使用 Delta-Gamma 近似
   - 结合蒙特卡洛模拟定价

---

## 6. 注意事项与假设

### 6.1 关键假设

1. **波动率持续性**: 假设当前波动率可由 EWMA 模型良好预测
2. **残差平稳性**: 标准化残差的分布相对稳定
3. **线性组合**: 组合风险为各股票风险的线性加权和（忽略交叉项）
4. **权重准确性**: 假设权重数据准确反映实际持仓

### 6.2 局限性

1. **尾部风险低估**: 历史模拟可能低估未出现过的极端事件
2. **相关性忽略**: 简单加权法忽略了股票间的相关性结构
3. **流动性假设**: 假设可在日度频率无摩擦地调整权重
4. **参数敏感性**: EWMA 参数（λ=0.96）的选择影响结果

### 6.3 建议的改进方向

- **第 4 步替代方案**: 使用协方差矩阵和组合方差公式：
  $$
  (\sigma_t^p)^2 = w_t^T \Sigma_t w_t
  $$
  其中 Σ_t 是 EWMA 估计的协方差矩阵。

- **Bootstrap**: 对历史残差进行 Bootstrap 重抽样以增加样本量

- **极值理论 (EVT)**: 对尾部残差使用 GEV 或 GPD 分布拟合

---

## 7. 代码实现框架（伪代码）

```python
# 参数配置
LAMBDA = 0.96
WINDOW = 60
CONFIDENCE = 0.95
N_STOCKS = 30

# Step 1: 数据加载
def load_data():
    returns_df = load_returns_from_file()
    weights_df = load_weights_from_file()
    return align_dates(returns_df, weights_df)

# Step 2: EWMA 波动率
def calculate_ewma_volatility(returns_df):
    volatility = {}
    for stock in returns_df.columns:
        var_series = []
        # 初始化
        initial_var = returns_df[stock].iloc[:WINDOW].var()
        var_series.append(initial_var)
        
        # EWMA 递归
        for t in range(WINDOW, len(returns_df)):
            new_var = LAMBDA * var_series[-1] + (1-LAMBDA) * returns_df[stock].iloc[t-1]**2
            var_series.append(new_var)
        
        volatility[stock] = np.sqrt(var_series)
    
    return pd.DataFrame(volatility, index=returns_df.index)

# Step 3: 标准化残差
def calculate_residuals(returns_df, volatility_df):
    residuals = returns_df / volatility_df
    return residuals.fillna(0)

# Step 4: 组合聚合
def calculate_portfolio_metrics(weights_df, returns_df, residuals_df, volatility_df):
    portfolio_returns = (weights_df * returns_df).sum(axis=1)
    portfolio_residuals = (weights_df * residuals_df).sum(axis=1)
    portfolio_volatility = (weights_df * volatility_df).sum(axis=1)
    return portfolio_returns, portfolio_residuals, portfolio_volatility

# Step 5 & 6: VaR 和 CVaR 计算
def calculate_var_cvar(portfolio_residuals, portfolio_volatility, confidence=CONFIDENCE):
    var_series = []
    cvar_series = []
    
    for t in range(WINDOW, len(portfolio_residuals)):
        # 获取历史残差（滚动窗口）
        hist_residuals = portfolio_residuals.iloc[t-WINDOW:t]
        
        # 计算分位数
        var_residual = np.percentile(hist_residuals, (1-confidence)*100)
        
        # VaR
        var_t = portfolio_volatility.iloc[t] * var_residual
        var_series.append(var_t)
        
        # CVaR (尾部平均)
        tail_residuals = hist_residuals[hist_residuals <= var_residual]
        cvar_residual = tail_residuals.mean()
        cvar_t = portfolio_volatility.iloc[t] * cvar_residual
        cvar_series.append(cvar_t)
    
    return pd.Series(var_series), pd.Series(cvar_series)

# 主流程
def main():
    returns_df, weights_df = load_data()
    volatility_df = calculate_ewma_volatility(returns_df)
    residuals_df = calculate_residuals(returns_df, volatility_df)
    
    port_ret, port_resid, port_vol = calculate_portfolio_metrics(
        weights_df, returns_df, residuals_df, volatility_df
    )
    
    var_series, cvar_series = calculate_var_cvar(port_resid, port_vol)
    
    # 生成报告
    report = create_risk_report(var_series, cvar_series, port_ret)
    return report
```

---

## 8. 参考文献

1. **Barone-Adesi, G., Giannopoulos, K., & Vosper, L. (1999)**. "VaR without correlations for portfolios of derivative securities." *Journal of Futures Markets*, 19(5), 583-602.

2. **RiskMetrics (1996)**. "RiskMetrics Technical Document." J.P. Morgan/Reuters.

3. **Rockafellar, R. T., & Uryasev, S. (2000)**. "Optimization of conditional value-at-risk." *Journal of Risk*, 2, 21-42.

4. **Engle, R. F. (2001)**. "GARCH 101: The Use of ARCH/GARCH Models in Applied Econometrics." *Journal of Economic Perspectives*, 15(4), 157-168.

---

*文档版本: 1.0*  
*创建日期: 2026-04-12*  
*最后更新: 2026-04-12*
