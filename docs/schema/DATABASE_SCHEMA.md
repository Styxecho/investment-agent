# 数据库结构说明 (Database Schema)

**最后更新时间**: 2026-06-26（导入7-10年期中债指数后）  
**数据库类型**: SQLite 3  
**数据库文件**: `data_external/db/external_data.db`  
**ORM 框架**: SQLAlchemy 2.x  
**维护约定**: 任何模型变更必须在当天同步更新本文档。

---

## 1. 数据库概述

本项目使用 SQLite 作为本地轻量级数据存储，主要用于：
- **行情缓存**: 存储股票、ETF、公募基金的日终行情，减少对外部 API（iFinD）的重复调用。
- **实时快照**: 存储盘中实时行情的快照记录。
- **组合归档**: 存储每日投资组合的计算结果（总市值、盈亏、收益率、持仓明细等），为历史回溯和趋势分析提供数据基础。

---

## 2. ER 关系图

当前所有表之间**无显式外键关联**，通过业务逻辑（如 `symbol + trade_date`、`portfolio_id + trade_date`）进行关联查询。

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│   stock_daily   │     │   stock_realtime    │     │   index_daily   │
│  (行情缓存)      │     │   (实时快照)         │     │  (指数缓存)      │
└─────────────────┘     └─────────────────────┘     └─────────────────┘
         │                                                    │
         │ 关联字段: symbol + trade_date                      │ 关联字段: index_code + trade_date
         ▼                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│         portfolio_snapshot                                                  │
│           (组合每日计算结果)                                                 │
│  数据来源: holdings.csv -> PortfolioSkill                                   │
└─────────────────────────────────────────────────────────────────────────────┘
         ▲
         │ 关联字段: fund_code + trade_date
┌─────────────────┐
│    fund_daily   │
│  (基金净值缓存)  │
└─────────────────┘

┌──────────────────────────────┐     ┌──────────────────────────────┐
│ macro_indicator_catalog      │     │  macro_indicator_value       │
│     (宏观指标目录)            │────▶│      (宏观指标数值)           │
│  关联字段: indicator_code    │     │  关联字段: indicator_code    │
└──────────────────────────────┘     └──────────────────────────────┘
```

---

## 3. 表结构详表

### 3.1 stock_daily

**用途**: 股票/ETF 日终行情缓存表。优先从本地读取，缺失时调用 iFinD API 获取。

| 字段名 | 类型 | 可空 | 默认值 | 备注 |
|--------|------|------|--------|------|
| `id` | `Integer` | 否 | `AUTO_INCREMENT` | 主键，自增 |
| `symbol` | `String(20)` | 否 | - | 资产代码，如 `600519.SH` |
| `trade_date` | `Date` | 否 | - | 交易日期，内部统一使用 `datetime.date` 存储，输入输出格式为 `YYYYMMDD` |
| `open_price` | `Float` | 是 | `NULL` | 开盘价 |
| `high_price` | `Float` | 是 | `NULL` | 最高价 |
| `low_price` | `Float` | 是 | `NULL` | 最低价 |
| `close_price` | `Float` | 是 | `NULL` | 收盘价/单位净值（T 日） |
| `pre_close_price` | `Float` | 是 | `NULL` | 昨收价（T-1 日收盘价），用于计算日涨跌 |
| `volume` | `Integer` | 是 | `NULL` | 成交量（股） |
| `amount` | `Float` | 是 | `NULL` | 成交额（元） |

**唯一约束**: `uix_symbol_date` (`symbol`, `trade_date`)

---

### 3.2 stock_realtime

**用途**: 股票实时行情快照表。保留多条历史记录，用于盘中波动分析。

| 字段名 | 类型 | 可空 | 默认值 | 备注 |
|--------|------|------|--------|------|
| `id` | `Integer` | 否 | `AUTO_INCREMENT` | 主键，自增 |
| `symbol` | `String(20)` | 否 | - | 资产代码 |
| `update_time` | `String(20)` | 否 | - | 数据更新时间，格式 `YYYY-MM-DD HH:MM:SS` |
| `current_price` | `Float` | 是 | `NULL` | 当前价格 |
| `change_percent` | `Float` | 是 | `NULL` | 涨跌幅（%） |
| `volume` | `Integer` | 是 | `NULL` | 成交量 |

**索引**: `symbol`

---

### 3.3 fund_daily

**用途**: 公募基金日终净值缓存表。存储基金三种净值，用于组合计算和净值查询。

| 字段名 | 类型 | 可空 | 默认值 | 备注 |
|--------|------|------|--------|------|
| `id` | `Integer` | 否 | `AUTO_INCREMENT` | 主键，自增 |
| `fund_code` | `String(20)` | 否 | - | 基金代码，如 `003956.OF` |
| `trade_date` | `Date` | 否 | - | 交易日期，格式固定为 `YYYYMMDD` |
| `unit_nav` | `Float` | 是 | `NULL` | 单位净值（每日公布） |
| `accumulated_nav` | `Float` | 是 | `NULL` | 累计单位净值（考虑分红） |
| `adjusted_nav` | `Float` | 是 | `NULL` | 复权单位净值（考虑分红和拆分） |
| `data_source` | `String(10)` | 是 | `'ifind'` | 数据来源标识（如 `ifind`、`akshare`） |
| `created_at` | `String(20)` | 是 | `NULL` | 记录创建时间，格式 `YYYYMMDD HH:MM:SS` |

**唯一约束**: `uix_fund_code_date` (`fund_code`, `trade_date`)

**特别说明**:
- `close`（T 日净值）和 `pre_close`（T-1 日净值）不在表中存储，由查询时动态计算。
- 当 `jsonIndicator` 包含多个指标时，`jsonparam` 必须与指标数量匹配（如 3 个指标对应 `';;'`）。

---

### 3.4 index_daily

**用途**: 指数日终行情缓存表。存储各类指数（宽基、行业、主题、债券、商品等）的日频行情数据，支持ETF上市前的历史数据替代、行业轮动策略计算及回测引擎。

| 字段名 | 类型 | 可空 | 默认值 | 备注 |
|--------|------|------|--------|------|
| `id` | `Integer` | 否 | `AUTO_INCREMENT` | 主键，自增 |
| `index_code` | `String(20)` | 否 | - | 指数代码，如 `801010.SI`（申万行业）、`000985.CSI`（中证全指） |
| `trade_date` | `Date` | 否 | - | 交易日期，格式固定为 `YYYYMMDD` |
| `pre_close_price` | `Float` | 是 | `NULL` | 昨收价（前收盘价） |
| `open_price` | `Float` | 是 | `NULL` | 开盘价 |
| `high_price` | `Float` | 是 | `NULL` | 最高价 |
| `low_price` | `Float` | 是 | `NULL` | 最低价 |
| `close_price` | `Float` | 是 | `NULL` | 收盘价 |
| `volume` | `Integer` | 是 | `NULL` | 成交量（股/手，申万指数为股） |
| `amount` | `Float` | 是 | `NULL` | 成交额（**元**，已从亿元转换） |

**唯一约束**: `uix_index_date` (`index_code`, `trade_date`)

**数据来源**: Wind终端手工提取
**映射关系**: 通过 `data_external/reference/index_universe.csv` 将ETF代码映射到全收益指数代码
**费率扣除**: 回测时从指数收益率中扣除对应ETF的年化费率（见 `etf_universe.csv` 的 `total_fee` 列）
**单位说明**: 
- 所有指数**成交额**统一为**元**
- 历史批次：申万行业指数和中证全指早期导入时，原始单位为亿元，已乘以 1e8 转换
- 2026-05-22批次：170个指数批量导入时，Wind导出已选择**元**为单位，**无需转换**
- 所有指数**成交量**统一为**股**（或手，视Wind导出格式而定）

---

### 3.5 portfolio_snapshot

**用途**: 投资组合每日计算结果归档表。由 `PortfolioSkill` 计算生成，`SnapshotSkill` 负责持久化。为历史趋势分析、周度/月度复盘提供数据基础。

| 字段名 | 类型 | 可空 | 默认值 | 备注 |
|--------|------|------|--------|------|
| `id` | `Integer` | 否 | `AUTO_INCREMENT` | 主键，自增 |
| `portfolio_id` | `String(50)` | 否 | `'default'` | 组合唯一标识。MVP 阶段固定为 `default`，未来支持多组合时扩展。已建立索引。 |
| `trade_date` | `Date` | 否 | - | 快照日期，格式固定为 `YYYYMMDD` |
| `total_market_value` | `Float` | 是 | `NULL` | 组合总市值（元） |
| `total_cost_value` | `Float` | 是 | `NULL` | 组合总成本（元） |
| `total_pnl_cumulated` | `Float` | 是 | `NULL` | 累计总盈亏（元） |
| `daily_pnl` | `Float` | 是 | `NULL` | 当日盈亏（元） |
| `daily_return` | `Float` | 是 | `NULL` | 当日收益率（%） |
| `net_value` | `Float` | 是 | `NULL` | 组合净值（以初始成本为 1.0 计算） |
| `position_count` | `Integer` | 是 | `0` | 持仓标的数量 |
| `positions_json` | `Text` | 是 | `NULL` | 个股明细的 JSON 序列化字符串，存储 `List[AssetMetrics]` 的完整计算结果。未来如需 SQL 级分析可拆分为独立明细表。 |
| `created_at` | `String(20)` | 是 | `NULL` | 记录创建时间，格式 `YYYYMMDD HH:MM:SS` |

**唯一约束**: `uix_portfolio_date` (`portfolio_id`, `trade_date`)

**多组合扩展说明**:
- 当前 MVP 阶段，系统默认只有一个组合，`portfolio_id` 硬编码为 `default`。
- 未来支持多组合时，无需修改表结构，只需在 `holdings.csv` 或交易流水中增加 `portfolio_id` 字段，并在 `SnapshotSkill` 中读取即可。

---

### 3.6 macro_indicator_catalog

**用途**: 宏观指标目录表。存储所有宏观经济指标的定义、分类和元信息，为宏观状态判断和因子体系提供指标管理。

| 字段名 | 类型 | 可空 | 默认值 | 备注 |
|--------|------|------|--------|------|
| `id` | `Integer` | 否 | `AUTO_INCREMENT` | 主键，自增 |
| `indicator_code` | `String(50)` | 否 | - | 指标唯一代码，如 `CN_PMI_MFG_M` |
| `indicator_name` | `String(100)` | 否 | - | 指标中文名称，如 `中国-制造业PMI` |
| `category` | `String(30)` | 否 | - | 指标分类：`growth`（经济增长）、`inflation`（通胀）、`liquidity`（流动性）、`rates`（利率）、`risk`（风险）、`inventory`（库存） |
| `country` | `String(20)` | 否 | - | 国家/地区：`CN`（中国）、`US`（美国） |
| `frequency` | `String(10)` | 否 | - | 更新频率：`daily`（日频）、`monthly`（月频）、`quarterly`（季频） |
| `unit` | `String(20)` | 是 | `NULL` | 单位：`ABS`（绝对值）、`PCT`（百分比）、`INDEX`（指数点）、`BILLION`（亿元） |
| `data_source` | `String(20)` | 是 | `'wind'` | 数据来源标识（如 `wind`、`akshare`） |
| `description` | `Text` | 是 | `NULL` | 指标详细说明 |
| `is_active` | `Boolean` | 是 | `1` | 是否启用该指标 |
| `created_at` | `Timestamp` | 是 | `CURRENT_TIMESTAMP` | 记录创建时间 |
| `updated_at` | `Timestamp` | 是 | `CURRENT_TIMESTAMP` | 记录更新时间 |

**唯一约束**: `indicator_code`

**数据来源**: Wind终端手工提取，或AkShare API（因AkShare延迟7个月，目前采用手工维护CSV作为保底方案）
**指标清单**: 详见 `docs/research/macro_analysis/macro_indicators.csv`

---

### 3.7 macro_indicator_value

**用途**: 宏观指标数值表。存储各指标的历史观测值，支持时间序列分析和宏观状态判断。

| 字段名 | 类型 | 可空 | 默认值 | 备注 |
|--------|------|------|--------|------|
| `id` | `Integer` | 否 | `AUTO_INCREMENT` | 主键，自增 |
| `indicator_code` | `String(50)` | 否 | - | 指标代码，关联 `macro_indicator_catalog.indicator_code` |
| `publish_date` | `String(8)` | 否 | - | 发布日期，格式固定为 `YYYYMMDD` |
| `value` | `Decimal(18,4)` | 是 | `NULL` | 指标数值 |
| `frequency` | `String(10)` | 否 | - | 频率：`daily`、`monthly`、`quarterly` |
| `period_type` | `String(10)` | 是 | `NULL` | 统计口径：`yoy`（同比）、`mom`（环比）、`cumulative`（累计）、`absolute`（绝对值） |
| `data_source` | `String(20)` | 是 | `'wind'` | 数据来源标识 |
| `is_revised` | `Boolean` | 是 | `0` | 是否为修订值 |
| `revision_note` | `String(200)` | 是 | `NULL` | 修订说明 |
| `created_at` | `Timestamp` | 是 | `CURRENT_TIMESTAMP` | 记录创建时间 |
| `updated_at` | `Timestamp` | 是 | `CURRENT_TIMESTAMP` | 记录更新时间 |

**唯一约束**: (`indicator_code`, `publish_date`, `frequency`, `period_type`)

**当前数据量**: 
- 日频：4个指标，约11,146条记录（2014-12-31至今）
- 月频：6个指标，约1,722条记录
- 覆盖指标：PMI、CPI、PPI、M0/M1/M2、社融、国债收益率、人民币汇率、南华商品指数、DR007等

**数据文件**: 
- 日频：`docs/research/macro_analysis/macro_indicators_history_series_daily.csv`
- 月频：`docs/research/macro_analysis/marco_indicators_history_series_monthly.csv`

---

### 3.8 macro_factor_value

**用途**: 宏观因子数值表。存储计算后的标准化因子值（Z-score），与原始数据表完全隔离。为宏观状态判断和行业轮动提供可直接使用的信号。

| 字段名 | 类型 | 可空 | 默认值 | 备注 |
|--------|------|------|--------|------|
| `id` | `Integer` | 否 | `AUTO_INCREMENT` | 主键，自增 |
| `indicator_code` | `String(50)` | 否 | - | 指标代码，关联 `macro_indicator_catalog` |
| `publish_date` | `String(8)` | 否 | - | 发布日期，格式 `YYYYMMDD` |
| `factor_type` | `String(20)` | 否 | - | 因子类型：`level`（水平Z-score）、`change`（变化率Z-score） |
| `factor_value` | `Decimal(10,4)` | 是 | `NULL` | 因子值（Z-score），已Winsorize截断到[-3, 3] |
| `raw_value` | `Decimal(18,4)` | 是 | `NULL` | 原始值（可选，用于追溯） |
| `cycle_value` | `Decimal(18,4)` | 是 | `NULL` | HP滤波后的周期项 |
| `trend_value` | `Decimal(18,4)` | 是 | `NULL` | HP滤波后的趋势项 |
| `zscore_window` | `Integer` | 是 | `NULL` | Z-score计算窗口：36（level）或48（change） |
| `filter_method` | `String(30)` | 是 | `NULL` | 滤波方法：`one_sided_hp` |
| `filter_params` | `String(100)` | 是 | `NULL` | 滤波参数，如 `{"lamb": 14400}` |
| `is_winsorized` | `Boolean` | 是 | `0` | 是否被截断 |
| `data_source` | `String(20)` | 是 | `'computed'` | 数据来源：计算生成 |
| `created_at` | `Timestamp` | 是 | `CURRENT_TIMESTAMP` | 记录创建时间 |
| `updated_at` | `Timestamp` | 是 | `CURRENT_TIMESTAMP` | 记录更新时间 |

**唯一约束**: (`indicator_code`, `publish_date`, `factor_type`)

**索引**: `idx_factor_date`, `idx_factor_code`, `idx_factor_type`

**当前数据量**: 
- 16个指标，3,164条记录（2016-07至2024-12）
- 每个指标约102条level + 101条change

---

### 3.9 macro_factor_config

**用途**: 宏观因子计算配置表。每个指标独立配置滤波参数和计算窗口，支持未来灵活调整。

| 字段名 | 类型 | 可空 | 默认值 | 备注 |
|--------|------|------|--------|------|
| `indicator_code` | `String(50)` | 否 | - | 指标代码，主键 |
| `filter_type` | `String(30)` | 是 | `'one_sided_hp'` | 滤波器类型 |
| `filter_params` | `String(100)` | 是 | `'{"lamb": 14400}'` | 滤波参数（JSON字符串） |
| `level_window` | `Integer` | 是 | `36` | 水平因子Z-score窗口（月） |
| `change_window` | `Integer` | 是 | `48` | 变化率因子Z-score窗口（月） |
| `winsorize_threshold` | `Decimal(4,2)` | 是 | `3.0` | 截断阈值（标准差倍数） |
| `min_periods_for_zscore` | `Integer` | 是 | `12` | 计算Z-score的最小样本数 |
| `hp_warmup_months` | `Integer` | 是 | `18` | HP滤波预热期（月） |
| `is_active` | `Boolean` | 是 | `1` | 是否启用 |
| `created_at` | `Timestamp` | 是 | `CURRENT_TIMESTAMP` | 记录创建时间 |
| `updated_at` | `Timestamp` | 是 | `CURRENT_TIMESTAMP` | 记录更新时间 |

**配置示例**: 详见 `scripts/init_macro_factor_tables.py`

---

### 3.10 industry_rotation_pool

**用途**: 行业轮动卫星策略中观选池结果表（Phase 2.4）。存储每月经过TIE映射、多周期动量、排名稳定性和宏观协同筛选后的行业候选池，为Phase 2.5微观趋势验证提供输入。

| 字段名 | 类型 | 可空 | 默认值 | 备注 |
|--------|------|------|--------|------|
| `id` | `Integer` | 否 | `AUTO_INCREMENT` | 主键，自增 |
| `date` | `String(8)` | 否 | - | 候选池日期，格式固定为 `YYYYMMDD`，通常取月末最后一个交易日 |
| `pool_type` | `String(20)` | 是 | `'final'` | 池类型：`final`（最终候选池，经宏观协同降权后）、`selected`（优势池，降权前） |
| `industries` | `Text` | 是 | `NULL` | 候选池行业的JSON序列化字符串，存储 `List[Dict]` 结构，包含字段：`index_code`、`sw_name`、`rs_score`、`rank`、`rank_std`、`stability_score`、`composite_score`、`composite_score_adj`、`sensitivity`、`primary_etf_code`、`primary_etf_name`、`tier`、`action`、`downside_reason` |
| `macro_regime` | `String(50)` | 是 | `NULL` | 生成候选池时的宏观象限，如 `完美扩张（扩张平稳+温和通胀平稳+双宽下行）` |
| `created_at` | `Timestamp` | 是 | `CURRENT_TIMESTAMP` | 记录创建时间 |

**唯一约束**: (`date`, `pool_type`)

**数据来源**: `IndustryRotationSkill` 运行完整pipeline后自动写入

**关联表**:
- 读取 `index_daily` 计算动量得分
- 读取 `macro_state_detail` 获取宏观象限
- 读取 `etf_universe.csv` + `index_components/` 进行TIE映射

**使用场景**:
- Phase 2.4 中观选池结果持久化
- Phase 2.5 微观趋势验证的输入数据源
- 历史回测时读取历史候选池

---

## 4. 表间关联逻辑

| 业务场景 | 关联方式 | 说明 |
|----------|----------|------|
| 计算某日组合快照 | `portfolio_snapshot.portfolio_id` + `trade_date` | 直接读取归档结果 |
| 获取某日股票行情 | `stock_daily.symbol` + `trade_date` | 缓存优先，缺失时调 iFinD |
| 获取某日基金净值 | `fund_daily.fund_code` + `trade_date` | 缓存优先，缺失时调 iFinD |
| 获取某日指数行情 | `index_daily.index_code` + `trade_date` | 用于ETF缺失时的数据替代 |
| 绘制组合收益曲线 | `portfolio_snapshot` 按 `trade_date` 排序 | 读取区间内的每日快照序列 |
| 查询宏观指标定义 | `macro_indicator_catalog.indicator_code` | 获取指标元信息（名称、分类、频率等） |
| 查询宏观指标历史值 | `macro_indicator_value.indicator_code` + `publish_date` | 获取特定时间序列数据，用于宏观状态判断 |
| 宏观因子分析 | `macro_indicator_catalog` JOIN `macro_indicator_value` | 按category分组，构建高维宏观因子体系 |
| 计算宏观因子 | `macro_indicator_value` → `macro_factor_pipeline` → `macro_factor_value` | 原始数据经滤波、Z-score计算后存入factor表 |
| 查询宏观因子 | `macro_factor_value` 按 `indicator_code` + `publish_date` | 获取标准化的Z-score因子值 |
| 因子配置管理 | `macro_factor_config` 按 `indicator_code` | 每个指标独立配置滤波参数和窗口 |
| 行业轮动候选池归档 | `industry_rotation_pool` 按 `date` + `pool_type` | Phase 2.4 中观选池结果，供 Phase 2.5 微观验证使用 |
| 读取候选池行业明细 | `industry_rotation_pool.industries` JSON | 解析 JSON 获取行业代码、ETF、得分等详细信息 |

---

## 5. 变更日志 (Changelog)

| 日期 | 变更内容 | 影响表 | 变更人 |
|------|----------|--------|--------|
| 2026-06-26 | 导入中债-总财富(7-10年) `CBA00351.CS` 和中债-新综合财富(7-10年) `CBA00151.CS` 的OHLCV数据（2015-01-06至2026-06-26，5,574条），用于风险预算 allocator 债券代理基准的久期匹配 | `index_daily` | OpenCode |
| 2026-05-22 | **重新导入170个指数完整OHLCV数据**（2014-12-31至2026-05-22，450,399条），统一日期格式为`YYYYMMDD`；删除错误格式记录（45,350条`YYYY-MM-DD`）；全部字段重新导入；验证数据完整性 | `index_daily` | OpenCode |
| 2026-05-22 | **批量导入170个指数完整OHLCV数据**（2014-12-31至2026-05-22，495,749条），覆盖宽基/行业/债券/商品/主题/恒生全部指数；含pre_close/open/high/low/close/volume/amount；UPSERT更新策略（更新已有+插入新记录）；清理重复旧代码；**amt字段单位为元** | `index_daily` | OpenCode |
| 2026-05-22 | 导入中证全指(000985.CSI)完整OHLCV数据（2014-12-31至2026-05-22，2,765条），含open/high/low/close/pre_close/volume/amount；补充open/high/low字段；成交额从亿元转换为元（×1e8） | `index_daily` | OpenCode |
| 2026-05-22 | 扩展 `index_daily` 表结构，新增 `open_price`、`high_price`、`low_price`、`volume`、`amount` 字段；导入申万31行业指数OHLCV全历史数据（2014-12-31至2026-05-22，85,715条）；成交额单位从亿元转换为元（×1e8） | `index_daily` | OpenCode |
| 2026-05-20 | 新增 `industry_rotation_pool` 表，存储Phase 2.4行业轮动中观选池结果；支持候选池持久化（`date`+`pool_type`唯一键）；JSON格式存储行业明细（含RS_score、Composite_score、ETF映射、宏观协同降权标记）；封装 IndustryRotationSkill（8种操作模式） | `industry_rotation_pool` | OpenCode |
| 2026-04-28 | 新增 `macro_factor_value` 和 `macro_factor_config` 表，实现宏观因子计算与存储；支持单边HP滤波、滚动Z-score、Winsorize截断；当前16个指标，3,164条因子记录（2016-07至2024-12）；封装 MacroFactorSkill（compute/query双模式） | `macro_factor_value`, `macro_factor_config` | OpenCode |
| 2026-04-27 | 新增 `macro_indicator_catalog` 和 `macro_indicator_value` 表，构建高维宏观因子体系；支持经济增长、通胀、流动性、利率、风险、库存六大类指标存储；当前覆盖16个指标，日频约14,000条、月频约3,000条历史数据 | `macro_indicator_catalog`, `macro_indicator_value` | OpenCode |
| 2026-04-20 | 新增 `index_daily` 表，存储全收益指数历史数据，支持ETF回测时的指数替代逻辑；新增 `uix_index_date` 唯一约束 | `index_daily` | OpenCode |
| 2026-04-14 | 新增 `portfolio_snapshot` 表，预留 `portfolio_id` 字段以支持未来多组合扩展 | `portfolio_snapshot` | OpenCode |
| 2026-04-05 | 新增 `fund_daily` 表，支持公募基金三种净值存储；新增 `uix_fund_code_date` 唯一约束 | `fund_daily` | OpenCode |
| 2026-04-04 | 新增 `stock_daily`、`stock_realtime` 表，构建市场行情缓存基础 | `stock_daily`, `stock_realtime` | OpenCode |

---

## 6. 维护 checklist

当进行以下操作时，请同步更新本文档：
- [ ] 新增/删除数据表
- [ ] 新增/删除/修改字段
- [ ] 新增/删除索引或唯一约束
- [ ] 修改字段类型、长度、可空性
- [ ] 调整表的业务用途或关联逻辑
