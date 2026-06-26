# Risk Budget Allocator

基于风险预算（Risk Budgeting）与目标波动率（Target Volatility）的大类资产配置工具。

## 核心思想

与标准风险平价（Risk Parity）要求各资产风险贡献相等不同，风险预算允许投资者为不同资产预设风险贡献比例。本工具进一步引入**目标波动率**作为约束，解决中国资产结构下债券波动过低、无杠杆组合难以达到较高波动目标的问题。

## 方法论

### 三种 Allocator

| Allocator | 用途 | 说明 |
|---|---|---|
| `risk_budget` | 保守 / 均衡组合 | 求解风险预算权重，再用目标波动率缩放 |
| `target_vol` | 可选 | 直接优化权重以满足目标波动率，最大化风险资产使用率 |
| `manual` | 激进组合 | 人工固定权重，如 70% 股 / 20% 债 / 10% 商品 |

### 关键约束

- **不依赖预期收益率**：避免 mean-variance 对收益估计的敏感
- **无杠杆**：风险资产权重之和 <= 1.0，剩余部分为现金
- **目标波动率**：组合年化波动尽量接近但不超过目标值
- **波动率上限**：硬约束，防止风险暴露过高

## 默认配置

### 资产代理

| 资产类别 | 代理指数 | 代码 |
|---|---|---|
| 股票 | 中证全指 | 000985.CSI |
| 债券（主） | 中债-总财富(7-10年)指数 | CBA00351.CS |
| 债券（备选） | 中债-新综合财富(7-10年)指数 | CBA00151.CS |
| 债券（历史备选） | 中债-国债总财富(总值) | CBA00601.CS |
| 商品 | 上海黄金 | AU.SHF |

### 组合配置

| 组合 | Allocator | 股票 | 债券 | 商品 | 目标波动 | 波动上限 |
|---|---|---|---|---|---|---|
| 保守组合 | risk_budget | 15% | 80% | 5% | 3% | 5% |
| 均衡组合 | risk_budget | 40% | 50% | 10% | 5% | 8% |
| 激进组合 | manual | 70% | 20% | 10% | - | - |

> 债券代理采用 `CBA00351.CS`（中债-总财富(7-10年)指数），其久期更接近10年期国债基准利率，波动率高于全期限总财富指数，更适合作为无杠杆组合的风险预算锚。

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 初始化用户配置

```bash
python -m risk_budget_allocator.cli --init
```

这会创建 `config/allocation/user_assets.yaml` 和 `config/allocation/user_portfolios.yaml`。

### 2. 准备价格数据

CSV 宽表格式（至少包含以下代码）：

```csv
date,000985.CSI,CBA00351.CS,AU.SHF
2024-01-01,4500,200,480
...
```

### 3. 生成配置

```bash
python -m risk_budget_allocator.cli --prices data/prices.csv --date 20260624
```

### 4. 程序化调用

```python
from risk_budget_allocator import AssetAllocator
from risk_budget_allocator.config import load_config, validate_config

config = validate_config(load_config("config/allocation"))
allocator = AssetAllocator(config)
report = allocator.allocate(prices, target_date="20260624")
```

## 求解器链路

1. 风险预算解：SLSQP / trust-constr
2. 目标波动率缩放
3. 权重约束裁剪与归一化
4. 现金吸收剩余部分

## 依赖

- pandas
- numpy
- scipy
- pydantic
- pyyaml
- scikit-learn

## 许可

MIT
