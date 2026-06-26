# Phase 2.3.2 路线图 - 宏观状态交互式Dashboard

**定位**: Phase 2.3 宏观状态诊断体系的交互式可视化扩展  
**最后更新**: 2026-05-24  
**版本**: v1.0  
**状态**: 规划中  

---

## 1. 项目定位

### 1.1 目标
将 Phase 2.3 宏观状态分析的结果从 CSV/命令行输出升级为**交互式 Web Dashboard**，解决以下痛点：

1. **历史走势直观化**: 原始值与因子值（Z-score/cycle/trend）的历史走势可视化，辅助周期判断
2. **截面分析便捷化**: 最新月份（或任意历史月份）的三维度状态一目了然
3. **推导过程透明化**: 从原始指标到最终象限的完整推导链可展开查看
4. **方法论可查阅**: 内置 V7/V8 方法论文档，随时参考

### 1.2 设计原则
- **展示优先**: Dashboard 是纯展示工具，不替代 `MacroStateSkill` 的计算逻辑
- **只读展示**: 不集成 LLM 对话，如需策略建议继续调用已封装的 Skill
- **开发模式**: 面向开发者/研究者，通过 GitHub 开源，本地克隆运行
- **渐进交付**: 先实现核心展示功能，再逐步完善交互体验

### 1.3 与现有系统的关系

```
┌─────────────────────────────────────────────────────────────┐
│                    Investment Agent 项目                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────────┐        ┌──────────────────────┐         │
│   │ MacroState   │        │  Phase 2.3.2         │         │
│   │ Skill        │───────▶│  Dashboard           │         │
│   │ (计算引擎)    │ 读取DB │  (展示层)            │         │
│   └──────────────┘        └──────────────────────┘         │
│          │                           │                     │
│          ▼                           ▼                     │
│   ┌──────────────────────────────────────────┐            │
│   │      data_external/db/external_data.db    │            │
│   │  macro_indicator_value                    │            │
│   │  macro_factor_value                       │            │
│   │  macro_state_detail                       │            │
│   └──────────────────────────────────────────┘            │
│                                                             │
│   工作流:                                                   │
│   1. 用户通过 CSV 上传 / Skill 计算 → 更新 DB              │
│   2. Dashboard 从 DB 读取 → 可视化展示                      │
│   3. 如需策略建议 → 调用 MacroStateSkill (LLM 交互)         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 技术架构

### 2.1 技术栈

| 层级 | 技术组件 | 用途 |
|------|----------|------|
| **前端框架** | Next.js 14 (App Router) | React 服务端组件、路由、API 代理 |
| **前端语言** | TypeScript | 类型安全、IDE 支持 |
| **前端样式** | Tailwind CSS + shadcn/ui | 原子化 CSS、预设组件库 |
| **图表库** | Plotly.js (react-plotly.js) | 金融图表原生支持、与 Python 生态一致 |
| **后端框架** | FastAPI | 异步 API、自动 OpenAPI 文档、类型安全 |
| **后端语言** | Python 3.11+ | 复用现有 DB 模型和查询逻辑 |
| **数据库** | SQLite (现有) | 通过 SQLAlchemy 读取，只读或少量写入 |
| **HTTP 客户端** | TanStack Query (React Query) | 数据获取、缓存、自动刷新 |
| **状态管理** | Zustand | 轻量全局状态（如当前选中月份） |

### 2.2 为什么选择 Plotly.js

1. **金融图表原生支持**: 内置 candlestick、OHLC、volume、技术指标（MA、Bollinger、MACD），后续 Phase 2.4/2.5 可直接复用
2. **Python 生态一致性**: 后端用 pandas/plotly 生成图表配置，前端直接渲染，减少数据转换层
3. **跨 Phase 复用**: 如果 2.3 效果验证成功，2.4（行业轮动）和 2.5（微观趋势）的金融图表需求可直接沿用同一套技术栈
4. **性能足够**: 月频/日频数据（10 年跨度，几千个数据点），Plotly 的 SVG 渲染完全流畅

### 2.3 目录结构

```
dashboard/                          # 根目录下新建
├── README.md                       # Dashboard 使用说明
├── pyproject.toml / requirements.txt # Python 依赖
├── package.json                    # Node.js 依赖
├── next.config.js                  # Next.js 配置
├── tailwind.config.ts              # Tailwind 配置
├── tsconfig.json                   # TypeScript 配置
│
├── backend/                        # FastAPI 后端
│   ├── main.py                     # 应用入口 (uvicorn 启动)
│   ├── config.py                   # 配置（DB 路径、CORS、缓存）
│   ├── database.py                 # SQLAlchemy 连接（复用现有 engine）
│   ├── routers/
│   │   ├── indicators.py           # 指标查询 API
│   │   ├── factors.py              # 因子查询 API
│   │   ├── states.py               # 宏观状态 API
│   │   ├── analysis.py             # 分析接口（语言描述、历史对比）
│   │   └── data_mgmt.py            # 数据管理（触发重算、状态检查）
│   ├── schemas/
│   │   ├── indicator.py            # Pydantic 模型：指标历史数据
│   │   ├── factor.py               # Pydantic 模型：因子分解数据
│   │   ├── state.py                # Pydantic 模型：宏观状态
│   │   └── analysis.py             # Pydantic 模型：分析结果
│   └── services/
│       ├── indicator_service.py    # 指标查询逻辑
│       ├── factor_service.py       # 因子查询逻辑
│       ├── state_service.py        # 状态查询逻辑
│       └── narrative_service.py    # 语言描述生成（基于规则模板）
│
├── frontend/                       # Next.js 前端
│   ├── app/                        # App Router
│   │   ├── layout.tsx              # 根布局（导航栏、主题 Provider）
│   │   ├── page.tsx                # 默认首页：重定向到 /panel-history
│   │   │
│   │   ├── panel-history/          # 【面板1】历史走势
│   │   │   ├── page.tsx
│   │   │   └── components/
│   │   │       ├── IndicatorSelector.tsx     # 指标多选器（按维度分组）
│   │   │       ├── DualAxisChart.tsx         # 双轴图：原始值 + Z-score
│   │   │       ├── CycleDecomposition.tsx    # 周期分解：raw / cycle / trend
│   │   │       ├── ZScoreTimeline.tsx        # Z-score 时间线 + 阈值带
│   │   │       ├── DirectionStrip.tsx        # 方向箭头时间轴
│   │   │       └── RegimeBackground.tsx      # 象限背景色带
│   │   │
│   │   ├── panel-snapshot/         # 【面板2】截面分析
│   │   │   ├── page.tsx
│   │   │   └── components/
│   │   │       ├── DateSelector.tsx          # 月份选择器（下拉/滑块）
│   │   │       ├── RegimeCard.tsx            # 当前象限大卡片（颜色标识）
│   │   │       ├── DimensionCards.tsx        # 三维度横向卡片
│   │   │       ├── WarningBanner.tsx         # WARNING 横幅（如有）
│   │   │       ├── FactorTable.tsx           # 指标因子值明细表
│   │   │       ├── BreakdownTree.tsx         # 状态推导分解树（可展开）
│   │   │       └── ComparisonToggle.tsx      # 与上月/去年同期对比
│   │   │
│   │   ├── panel-narrative/        # 【面板3】语言分析
│   │   │   ├── page.tsx
│   │   │   └── components/
│   │   │       ├── AutoNarrative.tsx         # 自动生成的文字描述
│   │   │       ├── StrategyImplication.tsx   # 策略含义（基于象限的预设建议）
│   │   │       ├── HistoricalContext.tsx     # 历史相似时期对比
│   │   │       └── KeyMetricsSummary.tsx     # 关键指标摘要卡片
│   │   │
│   │   └── panel-methodology/      # 【面板4】方法论
│   │       ├── page.tsx
│   │       └── content/            # Markdown 内容文件
│   │           ├── framework.md            # V7/V8 框架总览
│   │           ├── growth-dimension.md     # 增长维度方法论
│   │           ├── inflation-dimension.md  # 通胀维度方法论
│   │           ├── liquidity-dimension.md  # 流动性维度方法论
│   │           ├── regime-mapping.md       # 象限映射规则表
│   │           └── glossary.md             # 术语表
│   │
│   ├── components/
│   │   ├── ui/                     # shadcn/ui 组件（自动安装）
│   │   ├── layout/
│   │   │   ├── Navbar.tsx          # 顶部导航栏（面板切换）
│   │   │   ├── Sidebar.tsx         # 侧边栏（可选，移动端用）
│   │   │   └── Footer.tsx          # 页脚（数据时效、版本信息）
│   │   └── shared/
│   │       ├── LoadingSpinner.tsx  # 加载动画
│   │       ├── ErrorBoundary.tsx   # 错误边界
│   │       └── DataStatusBadge.tsx # 数据时效状态徽章
│   │
│   ├── lib/
│   │   ├── api.ts                  # API 客户端封装（axios + TanStack Query）
│   │   ├── utils.ts                # 工具函数（日期格式化、数值格式化）
│   │   ├── plotly-config.ts        # Plotly 默认配置（主题、字体、颜色）
│   │   └── types.ts                # TypeScript 类型定义（复用后端 schema）
│   │
│   ├── hooks/
│   │   ├── useIndicators.ts        # 指标数据查询 Hook
│   │   ├── useFactors.ts           # 因子数据查询 Hook
│   │   ├── useStates.ts            # 状态数据查询 Hook
│   │   └── useLatestDate.ts        # 最新数据日期 Hook
│   │
│   └── stores/
│       └── dashboardStore.ts       # Zustand 全局状态（当前选中月份、面板偏好）
│
└── scripts/
    └── start_dashboard.py          # 统一启动脚本（同时启动后端+前端）
```

---

## 3. 后端 API 设计

### 3.1 REST API 路由

```
/api/v1/
│
├── /health                       GET    健康检查
│
├── /indicators
│   ├── /history                  GET    查询指标历史数据
│   │                              Params: codes, start_date, end_date
│   ├── /latest                   GET    获取各指标最新值
│   └── /catalog                  GET    获取指标目录（名称、分类、频率）
│
├── /factors
│   ├── /history                  GET    查询因子历史（Z-score, cycle, trend）
│   │                              Params: codes, start_date, end_date
│   ├── /decomposition/{code}     GET    获取单个指标的完整分解
│   │                              Returns: raw + cycle + trend + zscore + deviation + threshold + direction
│   └── /latest                   GET    获取最新因子值
│
├── /states
│   ├── /history                  GET    查询宏观状态历史序列
│   │                              Params: start_date, end_date
│   ├── /latest                   GET    获取最新状态
│   ├── /{date}                   GET    获取指定日期状态
│   ├── /regime-transitions       GET    获取象限转换历史（用于时间轴着色）
│   └── /dimensions               GET    获取三维度历史（用于雷达图）
│
├── /analysis
│   ├── /narrative/{date}         GET    生成指定日期的语言描述
│   ├── /historical-context/{date} GET   查找历史相似时期
│   └── /cycle-position           GET    当前周期位置分析（如"扩张中期"）
│
└── /data-mgmt
    ├── /status                   GET    数据时效状态（各指标最新日期）
    ├── /completeness             GET    数据完整度检查
    └── /trigger-recalc           POST   触发重新计算（调用现有 Skill）
```

### 3.2 核心数据结构（Pydantic）

```python
# schemas/indicator.py
class IndicatorHistoryItem(BaseModel):
    date: str                # YYYYMMDD
    value: float

class IndicatorHistoryResponse(BaseModel):
    code: str
    name: str
    category: str           # growth / inflation / liquidity
    frequency: str          # monthly / daily
    unit: str               # ABS / PCT / INDEX
    data: List[IndicatorHistoryItem]

# schemas/factor.py
class FactorDecompositionItem(BaseModel):
    date: str
    raw_value: float
    cycle_value: float
    trend_value: float
    zscore: float
    deviation: float
    threshold: float
    raw_direction: str      # ↑ / ↓ / →
    trend_direction: str    # ↑ / ↓ / →

class FactorDecompositionResponse(BaseModel):
    code: str
    name: str
    category: str
    filter_method: str
    filter_params: str
    data: List[FactorDecompositionItem]

# schemas/state.py
class DimensionState(BaseModel):
    level: str              # 如"扩张"
    direction: str          # 如"上行"
    state: str              # 如"扩张上行"
    raw_values: Dict[str, float]   # 原始指标值
    factor_values: Dict[str, float] # 因子值

class MacroStateSnapshot(BaseModel):
    date: str
    regime: str             # 如"完美扩张"
    growth: DimensionState
    inflation: DimensionState
    liquidity: DimensionState
    warnings: List[str]
    methodology_version: str # "V8"
    
class RegimeTransition(BaseModel):
    date: str
    regime: str
    duration_months: int    # 该象限持续月数
```

### 3.3 语言描述生成（无需 LLM）

`narrative_service.py` 基于**规则模板**生成：

```python
# 模板示例
TEMPLATES = {
    "regime_overview": {
        "完美扩张": "当前处于{regime}阶段。增长维度{growth_state}，通胀保持{inflation_state}，流动性{liquidity_state}。这是一个经济景气度较高、企业盈利改善、市场流动性充裕的环境。",
        "宽衰退": "当前处于{regime}阶段...",
        # ... 其他象限
    },
    "dimension_detail": {
        "growth": "增长方面，制造业PMI为{pmi_raw}，处于{pmi_level}区间；工业增加值周期项为{iav_cycle}，显示{iav_level}态势。",
        "inflation": "通胀方面，核心CPI同比{ccpi_raw}%，处于{inf_level}水平；PPI方向{ppi_dir}，{cost_divergence_hint}。",
        "liquidity": "流动性方面，M2周期项{m2_cycle}，社融周期项{sfs_cycle}，整体处于{liq_level}状态。",
    },
    "warning": {
        "成本传导背离": "⚠️ 注意：CPI 与 PPI 方向背离，上下游利润可能重塑，需关注中游企业盈利压力。",
        # ... 其他 warning
    }
}
```

生成逻辑：
1. 根据象限选择总述模板
2. 填充三维度模板
3. 如有 WARNING，追加警告段落
4. 对比历史：查找数据库中相同/相似象限的时期

---

## 4. 前端页面设计

### 4.1 布局框架

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo] 宏观状态分析 Dashboard    [面板1] [面板2] [面板3] [面板4]  │  ← Navbar
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                        主内容区                              │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  数据时效: 2026-03-31 | 版本: V8 | 共135个月 | ©2026         │  ← Footer
└─────────────────────────────────────────────────────────────┘
```

### 4.2 【面板1】历史走势

**功能**: 展示原始值与因子值的历史走势

**布局**:
```
┌─────────────────────────────────────────────────────────────┐
│  [指标选择器]  [时间范围: 1年 ▼]  [对比模式: 单指标/多指标 ▼]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                                                     │   │
│   │          双轴折线图（Plotly）                        │   │
│   │          左轴: 原始值                               │   │
│   │          右轴: Z-score                              │   │
│   │          背景: 象限着色（根据 macro_state_detail）   │   │
│   │                                                     │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                                                     │   │
│   │          周期分解图（堆叠面积图）                     │   │
│   │          raw_value / cycle_value / trend_value       │   │
│   │                                                     │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                                                     │   │
│   │          Z-score 时间线 + 阈值带                     │   │
│   │          绿色: Z > upper_threshold                   │   │
│   │          红色: Z < lower_threshold                   │   │
│   │          灰色: 阈值区间内                            │   │
│   │                                                     │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**交互**:
- 指标选择器：按维度分组（增长/通胀/流动性），支持多选对比
- 时间范围：1年 / 3年 / 5年 / 全部 / 自定义
- 点击图表上的某个月份 → 跳转至【面板2】并定位到该月
- 悬停显示详细数值（原始值、因子值、阈值、方向）

### 4.3 【面板2】截面分析

**功能**: 展示指定月份（默认最新月）的截面状态

**布局**:
```
┌─────────────────────────────────────────────────────────────┐
│  [月份选择器 ▼: 2026-03]  [对比: 上月 ▼]  [导出 ▼]          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                                                     │   │
│   │   🟢 完美扩张                                        │   │
│   │   扩张平稳 + 温和通胀平稳 + 双宽下行                   │   │
│   │   持续: 3个月 | 历史上平均持续1.9个月                  │   │
│   │                                                     │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│   │   📈 增长     │  │   💰 通胀     │  │   💧 流动性   │     │
│   │              │  │              │  │              │     │
│   │  状态: 扩张↑  │  │  状态: 温和通胀平稳│  │  状态: 双宽↓  │     │
│   │              │  │              │  │              │     │
│   │  PMI: 50.4   │  │  CoreCPI: 1.1%│  │  M2: 8.5%    │     │
│   │  IAV: 5.7%   │  │  PPI: 0.5%   │  │  SFS: 7.9%   │     │
│   │              │  │              │  │              │     │
│   │  [展开推导▶] │  │  [展开推导▶] │  │  [展开推导▶] │     │
│   └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  ⚠️ WARNING                                         │   │
│   │  • 成本传导背离，上下游利润可能重塑                    │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  指标因子值明细表（可展开）                            │   │
│   │  ─────────────────────────────────────────────       │   │
│   │  指标 | 原始值 | 周期项 | Z-score | 偏离度 | 阈值 | 方向│   │
│   │  PMI  | 50.4  | +0.4   | +0.2    | +0.1   | 0.5  | →  │   │
│   │  IAV  | 5.7%  | +0.3   | +0.5    | +0.2   | 0.6  | ↑  │   │
│   │  ...                                                      │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**交互**:
- 月份选择器：下拉列表（所有有数据的月份），支持键盘左右箭头切换
- 推导展开：点击"展开推导"显示从原始值到状态的完整计算链
- 对比模式：与上月 / 去年同期 / 自定义月份对比（差异高亮）

### 4.4 【面板3】语言分析

**功能**: 自动生成并展示分析描述

**布局**:
```
┌─────────────────────────────────────────────────────────────┐
│  [月份: 2026-03]  [重新生成 ▶]  [复制文本 📋]                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  📋 当前状态综述                                     │   │
│   │                                                     │   │
│   │  当前处于完美扩张阶段。增长维度扩张上行，通胀保持温和    │   │
│   │  通胀平稳，流动性双宽下行。这是一个经济景气度较高、企   │   │
│   │  业盈利改善、市场流动性充裕的环境。                    │   │
│   │                                                     │   │
│   │  历史上类似时期：2014年5-7月、2020年4-5月。这两个时期 │   │
│   │  后市场表现...                                       │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  📈 增长维度解读                                     │   │
│   │  ...                                                │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  💰 通胀维度解读                                     │   │
│   │  ...                                                │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  💧 流动性维度解读                                   │   │
│   │  ...                                                │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  ⚠️ 风险提示                                         │   │
│   │  • 成本传导背离，上下游利润可能重塑                   │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  🎯 策略含义（基于象限的预设建议）                     │   │
│   │  • 完美扩张期适合配置顺周期板块（消费、金融、周期）    │   │
│   │  • 关注估值修复机会                                   │   │
│   │  • 警惕过热信号（通胀上行 + 流动性收紧）               │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**生成逻辑**:
- 基于规则模板 + 数据填充（无需 LLM API）
- 历史对比：查询数据库中相同象限的时期，计算后续市场表现（可选）
- 策略含义：基于象限标签的预设建议（非投资建议，仅作为分析参考）

### 4.5 【面板4】方法论

**功能**: 完整展示 V7/V8 方法论文档

**布局**:
```
┌─────────────────────────────────────────────────────────────┐
│  [目录树]                                                   │
│  ├─ V7/V8 框架总览                                         │
│  ├─ 增长维度方法论                                         │
│  │   ├─ PMI 绝对零点法                                     │
│  │   ├─ IAV HP 滤波处理                                     │
│  │   └─ 增长维度合成规则                                    │
│  ├─ 通胀维度方法论                                         │
│  ├─ 流动性维度方法论                                       │
│  ├─ 象限映射规则（10级优先级表）                            │
│  └─ 术语表                                                 │
├─────────────────────────────────────────────────────────────┤
│                        Markdown 渲染区                       │
│  （支持数学公式、表格、代码块）                               │
└─────────────────────────────────────────────────────────────┘
```

**内容来源**:
- `docs/research/macro_analysis/methodology_summary_V7.md`
- 拆分为多个 Markdown 文件存放在 `panel-methodology/content/`
- 使用 `react-markdown` + `remark-math` 渲染

---

## 5. 统一启动方式

### 5.1 启动脚本

`scripts/start_dashboard.py`:

```python
#!/usr/bin/env python3
"""
统一启动脚本：同时启动 FastAPI 后端和 Next.js 前端
Usage: python scripts/start_dashboard.py
"""
import subprocess
import sys
import time
import os

# 配置
BACKEND_PORT = 8742
FRONTEND_PORT = 3011
BACKEND_CMD = [
    sys.executable, "-m", "uvicorn", 
    "dashboard.backend.main:app",
    "--host", "127.0.0.1",
    "--port", str(BACKEND_PORT),
    "--reload"
]
FRONTEND_CMD = [
    "npm", "run", "dev", "--", "-p", str(FRONTEND_PORT)
]

def main():
    # 检查 Node.js 环境
    if not shutil.which("npm"):
        print("❌ Error: npm not found. Please install Node.js 18+ first.")
        sys.exit(1)
    
    # 启动后端
    print(f"🚀 Starting FastAPI backend on http://127.0.0.1:{BACKEND_PORT}")
    backend_proc = subprocess.Popen(
        BACKEND_CMD,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    
    # 等待后端启动
    time.sleep(3)
    
    # 启动前端
    print(f"🚀 Starting Next.js frontend on http://127.0.0.1:{FRONTEND_PORT}")
    frontend_proc = subprocess.Popen(
        FRONTEND_CMD,
        cwd=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "frontend")
    )
    
    print("\n✅ Dashboard started!")
    print(f"   Backend:  http://127.0.0.1:{BACKEND_PORT}/docs  (OpenAPI docs)")
    print(f"   Frontend: http://127.0.0.1:{FRONTEND_PORT}")
    print("\nPress Ctrl+C to stop all services.\n")
    
    try:
        # 等待任意进程结束
        while True:
            backend_status = backend_proc.poll()
            frontend_status = frontend_proc.poll()
            if backend_status is not None or frontend_status is not None:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()
        print("✅ All services stopped.")

if __name__ == "__main__":
    main()
```

### 5.2 开发启动流程

```bash
# 1. 克隆仓库
git clone <repo-url>
cd investment-agent

# 2. 安装 Python 依赖
pip install -r requirements.txt
# 或安装 Dashboard 专用依赖
pip install -r dashboard/requirements.txt

# 3. 安装前端依赖
cd dashboard/frontend && npm install && cd ../..

# 4. 统一启动
python scripts/start_dashboard.py

# 5. 打开浏览器
# Backend API docs: http://127.0.0.1:8742/docs
# Dashboard UI:     http://127.0.0.1:3011
```

---

## 6. 数据流

### 6.1 数据读取路径

```
用户打开 Dashboard
    │
    ▼
前端请求 /api/v1/states/latest
    │
    ▼
FastAPI → state_service.py
    │
    ▼
SQLAlchemy → SQLite (external_data.db)
    │
    ▼
读取 macro_state_detail（最新一条）
读取 macro_factor_value（各指标最新因子值）
    │
    ▼
组装 MacroStateSnapshot → JSON 返回
    │
    ▼
前端渲染 → RegimeCard + DimensionCards + FactorTable
```

### 6.2 历史走势数据流

```
用户选择指标 + 时间范围
    │
    ▼
前端请求 /api/v1/factors/decomposition/CN_PMI_MFG_M?start=202001&end=202412
    │
    ▼
FastAPI → factor_service.py
    │
    ▼
SQLAlchemy → SQLite
    │
    ▼
读取 macro_factor_value（指定指标 + 日期范围）
    │
    ▼
组装 FactorDecompositionResponse → JSON 返回
    │
    ▼
前端 Plotly 渲染 → DualAxisChart + CycleDecomposition + ZScoreTimeline
```

---

## 7. 实施阶段

### Phase A: Dashboard 核心功能（P0）

**目标**: 实现4个面板的 MVP，能展示现有数据

| 任务 | 内容 | 预估工时 | 备注 |
|------|------|----------|------|
| A1 | 项目脚手架搭建 | 3h | Next.js + FastAPI + Tailwind + shadcn/ui 初始化 |
| A2 | 后端基础架构 | 2h | FastAPI 入口、DB 连接、CORS、错误处理 |
| A3 | 数据查询 API | 4h | /indicators、/factors、/states 基础查询 |
| A4 | 前端布局框架 | 2h | Navbar、Footer、面板路由、主题 |
| A5 | 【面板1】历史走势 | 6h | 指标选择器、双轴图、周期分解图、Z-score时间线 |
| A6 | 【面板2】截面分析 | 5h | 月份选择器、象限卡片、维度卡片、推导树、因子表 |
| A7 | 【面板3】语言分析 | 4h | 规则模板引擎、自动描述生成、策略含义 |
| A8 | 【面板4】方法论 | 3h | Markdown 渲染、目录树、内容迁移 |
| A9 | 统一启动脚本 | 2h | start_dashboard.py |
| A10 | 联调与 Bug 修复 | 4h | 端到端测试、数据一致性检查 |
| **小计** | | **35h** | |

### Phase B: 完善与优化（P1）

**目标**: 提升用户体验，增加高级功能

| 任务 | 内容 | 预估工时 | 备注 |
|------|------|----------|------|
| B1 | 数据对比功能 | 3h | 面板2支持与上月/去年同期对比 |
| B2 | 历史相似时期搜索 | 3h | 面板3查找相似象限时期 |
| B3 | 数据导出 | 2h | CSV/PNG/PDF 导出功能 |
| B4 | 响应式适配 | 3h | 移动端布局优化 |
| B5 | 性能优化 | 3h | API 响应缓存、大数据量采样、懒加载 |
| B6 | 错误处理与提示 | 2h | 数据缺失提示、API 错误友好展示 |
| B7 | 面板间联动 | 2h | 面板1点击月份 → 面板2/3自动切换 |
| **小计** | | **18h** | |

### Phase C: GitHub 发布准备（P2）

**目标**: 整理代码、编写文档、开源发布

| 任务 | 内容 | 预估工时 | 备注 |
|------|------|----------|------|
| C1 | 代码清理 | 2h | 移除硬编码路径、标准化配置 |
| C2 | README 编写 | 2h | 安装、配置、使用说明、截图 |
| C3 | LICENSE 选择 | 0.5h | MIT / Apache-2.0 |
| C4 | 依赖锁定 | 1h | requirements.txt + package-lock.json |
| C5 | 示例数据 | 2h | 提供脱敏的示例 DB 或 mock 数据 |
| C6 | GitHub Release | 1h | Tag、Release Notes |
| **小计** | | **8.5h** | |

### 总计预估

| 阶段 | 工时 | 说明 |
|------|------|------|
| Phase A (核心) | 35h | 必须完成 |
| Phase B (优化) | 18h | 建议完成 |
| Phase C (发布) | 8.5h | 可选 |
| **总计** | **61.5h** | 纯开发时间 |

> 注：以上为纯开发时间估算，不含测试数据准备、用户反馈迭代、环境配置等。

---

## 8. 关键设计决策

| 决策项 | 选择 | 原因 |
|--------|------|------|
| 图表库 | **Plotly.js** | 金融图表原生支持、Python 生态一致、跨 Phase 复用 |
| 前端框架 | **Next.js 14** | App Router、SSR、API 代理、TypeScript 原生支持 |
| 后端框架 | **FastAPI** | 异步、自动文档、类型安全、与现有 Python 代码兼容 |
| 样式方案 | **Tailwind + shadcn/ui** | 原子化 CSS、预设组件、维护成本低 |
| 状态管理 | **Zustand** | 轻量、无样板代码、适合 Dashboard 场景 |
| 数据获取 | **TanStack Query** | 缓存、自动刷新、错误重试、减少样板代码 |
| 启动方式 | **统一 Python 脚本** | 同时启动后端+前端、适合开发模式 |
| 数据更新 | **手动触发** | 月频数据、保留现有 CSV 上传、避免启动卡顿 |
| 语言描述 | **规则模板** | 无需 LLM API、可控、可解释 |
| 方法论展示 | **Markdown 静态文件** | 简单、版本可控、易于维护 |

---

## 9. 风险与应对

| 风险 | 影响 | 应对方案 |
|------|------|----------|
| Plotly.js 包体积大（~3MB） | 首次加载慢 | 代码分割（dynamic import）、CDN 加载、生产模式 gzip |
| 数据库路径硬编码 | 其他用户无法运行 | 配置文件化（.env 或 config.py）、启动时检查 |
| 前端依赖版本冲突 | 构建失败 | package-lock.json 锁定版本、README 明确 Node.js 版本要求 |
| 数据量大导致 API 慢 | 用户体验差 | 后端分页/采样、前端缓存、懒加载 |
| 跨域问题（前后端分离） | API 请求失败 | Next.js API proxy（/api/* → backend）、CORS 配置 |
| 后续 Phase 需求变化 | 架构需重构 | 模块化设计、松耦合、预留扩展接口 |

---

## 10. 下一步行动

### 立即开始（P0 - Phase A）

1. **创建项目目录结构**
   - 在根目录新建 `dashboard/`
   - 创建 `backend/` 和 `frontend/` 子目录
   - 初始化 `package.json`、`pyproject.toml`

2. **搭建后端基础**
   - FastAPI 入口 (`main.py`)
   - SQLAlchemy 连接（复用现有 `data_external/db/engine.py`）
   - 基础 API 路由（/health、/indicators/catalog）

3. **搭建前端基础**
   - Next.js 初始化（`create-next-app`）
   - Tailwind CSS + shadcn/ui 配置
   - 基础布局（Navbar、Footer、路由）

4. **实现第一个可用面板**
   - 推荐先实现【面板2】截面分析（数据查询最简单，展示价值最高）
   - 验证端到端数据流（DB → API → 前端渲染）

### 并行任务

- **方法论文档拆分**：将 `methodology_summary_V7.md` 拆分为 `panel-methodology/content/` 下的多个文件
- **数据验证**：确认 `macro_state_detail` 表中所有字段都可用，无缺失
- **设计稿确认**：是否需要先画线框图（wireframe）再开发？（建议直接开发，快速迭代）

---

## 11. 相关文档索引

### 本项目文档
- `docs/roadmap/project_context.md` - 项目目标与技术栈
- `docs/roadmap/project_roadmap.md` - Phase 框架与规划
- `docs/roadmap/phase2.3_summary.md` - Phase 2.3 详细总结
- `docs/schema/DATABASE_SCHEMA.md` - 数据库结构说明
- `docs/research/macro_analysis/methodology_summary_V7.md` - V7 方法论

### 外部参考
- [options-greeks-monitor](https://github.com/rhozero-div/options-greeks-monitor) - 参考架构（FastAPI + Next.js）
- [Plotly.js 文档](https://plotly.com/javascript/) - 图表库文档
- [shadcn/ui 文档](https://ui.shadcn.com/) - 组件库文档
- [TanStack Query 文档](https://tanstack.com/query/latest) - 数据获取库文档

---

## 12. 变更日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-05-24 | v1.0 | 初始版本，基于用户反馈确定技术选型与实施计划 |

---

*本文件为 Phase 2.3.2 实施路线图，随项目进展持续更新。*
