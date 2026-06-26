# Phase 2.3 宏观状态分析 Dashboard 实施计划

## 1. 项目概述

### 目标
将现有的 Phase 2.3 宏观状态分析 Skill 升级为具备自动化数据获取和可视化 Dashboard 的独立工具。

### 核心痛点解决
1. **数据获取自动化**：从手动下载 CSV → 自动抓取 → 增量更新
2. **结果可视化**：从 CSV 文件 → 交互式 Web Dashboard
3. **分析直观化**：原始值与因子值历史走势、截面分析、语言描述、方法论展示

### 技术架构（方案 B）
```
┌─────────────────────────────────────────────────────────────┐
│                    Dashboard (Next.js + React)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ 历史走势  │ │ 截面分析  │ │ 语言描述  │ │  方法论展示   │   │
│  │  面板     │ │  面板     │ │  面板     │ │   面板       │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │ REST API / WebSocket
┌────────────────────▼────────────────────────────────────────┐
│              FastAPI Backend (Python)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Data Query  │  │  Analysis    │  │  Data Fetcher    │  │
│  │   APIs       │  │   APIs       │  │   Controller     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│   SQLite DB  │ │ AKShare  │ │ Central Bank │
│ (existing)   │ │  API     │ │   Scraper    │
└──────────────┘ └──────────┘ └──────────────┘
```

---

## 2. 实施阶段

### Phase 1: 数据自动获取模块（优先级：P0）

#### 2.1 数据源分析与映射

| 指标代码 | 指标名称 | 当前来源 | 自动获取方案 | 优先级 |
|----------|----------|----------|--------------|--------|
| CN_PMI_MFG_M | 制造业 PMI | 统计局手动下载 | AKShare: `macro_china_pmi()` | P0 |
| CN_PMI_SVC_M | 非制造业 PMI | 统计局手动下载 | AKShare: `macro_china_non_man_pmi()` | P0 |
| CN_PMI_COMP_M | 综合 PMI | 统计局手动下载 | AKShare: `macro_china_composite_pmi()` | P0 |
| CN_IAV_YOY_M | 工业增加值同比 | 统计局手动下载 | AKShare: `macro_china_industrial_production_yoy()` | P0 |
| CN_CCPI_YOY_M | 核心 CPI 同比 | 统计局手动下载 | AKShare: `macro_china_cpi()` + 计算 | P0 |
| CN_PPI_YOY_M | PPI 同比 | 统计局手动下载 | AKShare: `macro_china_ppi()` | P0 |
| CN_M2_YOY_M | M2 同比 | 央行手动下载 | AKShare: `macro_china_money_supply()` | P0 |
| CN_SFS_YOY_M | 社融存量同比 | 央行手动下载 | AKShare: `macro_china_shrzgm()` | P0 |
| CN_DR007_D | DR007 日频 | 外汇交易中心 | AKShare: `macro_china_dr007()` | P0 |
| CN_OMO_R007_D | OMO 7天利率 | 央行官网 | **自建爬虫**（AKShare 覆盖不全） | P0 |

#### 2.2 模块设计

**新增目录**: `skills/macro_state/data_fetcher/`

```
data_fetcher/
├── __init__.py
├── base.py                    # 抽象基类 BaseDataFetcher
├── akshare_adapter.py         # AKShare 适配器
├── central_bank_scraper.py    # 央行官网爬虫（OMO 利率）
├── sync_manager.py            # 同步管理器（对比 DB 与新数据）
└── scheduler.py               # 调度器（手动/定时触发）
```

**核心流程**:
```
1. 检查 DB 中各指标最新日期
2. 调用对应 Fetcher 获取数据（从最新日期+1天到今日）
3. 数据校验（范围检查、异常值检测）
4. 与现有数据对比（防止重复）
5. 增量写入 macro_indicator_value
6. 触发自动重算（可选）
7. 返回同步报告（新增/更新/异常条数）
```

**OMO 利率爬虫设计**:
- 目标：中国人民银行官网 → 货币政策 → 公开市场业务 → 操作数据
- 技术：`requests` + `BeautifulSoup` 或 `playwright`（如页面动态加载）
- 数据：7 天逆回购利率（操作日期、利率值、操作量）
- 容错：如网站改版，回退到手动上传模式

#### 2.3 与现有 Skill 集成

在 `MacroStateSkill` 中新增模式：
- `mode: "fetch_data"` - 触发数据自动抓取
- `mode: "fetch_status"` - 查看各数据源最新同步状态

---

### Phase 2: Dashboard 后端 API（FastAPI）

#### 2.1 技术选型
- **框架**: FastAPI（异步、自动生成 OpenAPI 文档、类型安全）
- **数据库**: 复用现有 SQLAlchemy engine（SQLite）
- **缓存**: 内存缓存（`functools.lru_cache`）用于不常变的数据（如历史因子序列）

#### 2.2 API 设计

**数据查询 API**:
```python
# 指标原始数据
GET /api/indicators/history?codes=CN_PMI_MFG_M,CN_M2_YOY_M&start=202001&end=202412
GET /api/indicators/latest

# 因子数据（Z-score, cycle, trend）
GET /api/factors/history?codes=CN_PMI_MFG_M&start=202001&end=202412
GET /api/factors/{code}/decomposition  # 返回 raw + cycle + trend

# 宏观状态
GET /api/states/history?start=202001&end=202412
GET /api/states/latest
GET /api/states/{date}
GET /api/states/regime-transitions  # 象限转换历史
```

**分析 API**:
```python
GET /api/analyze/cycle-position       # 当前周期位置分析
GET /api/analyze/dimension-health     # 三维度健康度雷达图数据
POST /api/analyze/narrative           # 生成语言描述（可接入 LLM）
```

**数据管理 API**:
```python
POST /api/data/fetch-latest           # 触发手动抓取
GET /api/data/status                  # 数据时效状态
GET /api/data/completeness            # 数据完整度检查
```

#### 2.3 数据模型（Pydantic）

```python
class IndicatorHistory(BaseModel):
    code: str
    name: str
    category: str
    dates: List[str]
    raw_values: List[float]
    
class FactorDecomposition(BaseModel):
    code: str
    dates: List[str]
    raw: List[float]
    cycle: List[float]
    trend: List[float]
    zscore: List[float]
    deviation: List[float]
    threshold: List[float]
    direction: List[str]
    
class MacroStateSnapshot(BaseModel):
    date: str
    regime: str
    growth_state: str
    inflation_state: str
    liquidity_state: str
    warnings: List[str]
    details: Dict[str, Any]  # 各维度明细
```

---

### Phase 3: Dashboard 前端（Next.js + React）

#### 3.1 技术选型
- **框架**: Next.js 14 (App Router)
- **语言**: TypeScript
- **样式**: Tailwind CSS + shadcn/ui 组件库
- **图表**: Plotly.js（通过 `react-plotly.js`）
- **状态管理**: React Context 或 Zustand（轻量）
- **HTTP 客户端**: TanStack Query（React Query）

#### 3.2 页面结构

```
dashboard/
├── app/                           # Next.js App Router
│   ├── layout.tsx                 # 根布局（导航栏、主题）
│   ├── page.tsx                   # 主页面（默认展示概览）
│   │
│   ├── panel-history/             # 【面板1】历史走势
│   │   ├── page.tsx
│   │   └── components/
│   │       ├── IndicatorSelector.tsx     # 指标选择器（多选）
│   │       ├── DualAxisChart.tsx         # 双轴图：原始值 + 因子值
│   │       ├── CycleDecomposition.tsx    # 周期分解图（raw/cycle/trend）
│   │       ├── ZScoreTimeline.tsx        # Z-score 时间线（含阈值带）
│   │       └── RegimeBackground.tsx      # 象限背景着色
│   │
│   ├── panel-snapshot/            # 【面板2】最新截面
│   │   ├── page.tsx
│   │   └── components/
│   │       ├── RegimeCard.tsx            # 当前象限大卡片
│   │       ├── DimensionCards.tsx        # 三维度详情卡片（增长/通胀/流动性）
│   │       ├── WarningBanner.tsx         # WARNING 横幅
│   │       ├── FactorTable.tsx           # 各指标因子值明细表
│   │       └── BreakdownTree.tsx         # 状态推导分解树
│   │
│   ├── panel-narrative/           # 【面板3】语言分析
│   │   ├── page.tsx
│   │   └── components/
│   │       ├── AutoNarrative.tsx         # 自动生成的文字描述
│   │       ├── StrategyImplication.tsx   # 策略含义解读
│   │       ├── HistoricalContext.tsx     # 历史相似时期对比
│   │       └── KeyMetricsSummary.tsx     # 关键指标摘要
│   │
│   └── panel-methodology/         # 【面板4】方法论
│       ├── page.tsx
│       └── content/
│           ├── framework.md              # V8 框架总览
│           ├── growth-dimension.md       # 增长维度方法论
│           ├── inflation-dimension.md    # 通胀维度方法论
│           ├── liquidity-dimension.md    # 流动性维度方法论
│           ├── regime-mapping.md         # 象限映射规则
│           └── glossary.md               # 术语表
│
├── components/ui/                 # shadcn/ui 组件
├── lib/
│   ├── api.ts                     # API 客户端封装
│   ├── utils.ts                   # 工具函数
│   └── types.ts                   # TypeScript 类型定义
├── public/
│   └── images/                    # 静态图片（如象限示意图）
└── next.config.js
```

#### 3.3 各面板详细设计

**【面板1】历史走势**
- **功能**：展示原始值与因子值的历史走势
- **图表类型**：
  - 主图：双轴折线图（左轴原始值，右轴 Z-score）
  - 副图：周期分解（raw / cycle / trend 堆叠面积图）
  - 背景：根据象限着色（不同象限用不同背景色）
- **交互**：
  - 指标多选（支持同维度/跨维度对比）
  - 时间范围选择（1年/3年/5年/全部）
  - 悬停显示详细数值
  - 点击某月跳转至该月截面分析

**【面板2】最新截面**
- **功能**：展示最新月份（或选定月份）的截面分析
- **布局**：
  - 顶部：当前象限大卡片（带颜色标识）
  - 中部：三维度横向卡片（增长/通胀/流动性）
    - 每个卡片显示：水平状态 + 方向箭头 + 关键指标值
  - 下部：WARNING 横幅（如有）
  - 底部：指标明细表格（可展开查看推导过程）
- **交互**：
  - 月份选择器（历史月份下拉）
  - 推导过程展开/收起（显示从原始值到状态的完整推导链）

**【面板3】语言分析**
- **功能**：自动生成并展示分析描述
- **内容生成**：
  - 基于模板 + 规则生成（无需 LLM）
  - 或接入 LLM API（更自然语言化）
- **展示结构**：
  - 当前状态综述（1-2 段）
  - 三维度分别解读（各 1 段）
  - 关键变化点说明（如有 WARNING）
  - 历史相似时期对比（"当前类似 2019 年 3 月..."）
  - 策略含义提示（基于象限的策略建议）

**【面板4】方法论**
- **功能**：完整的方法论文档展示
- **内容**：
  - V8 框架总览（流程图）
  - 各维度计算逻辑（公式 + 示例）
  - 象限映射表（10 级优先级）
  - WARNING 类型说明
  - 数据处理方法（HP 滤波、Z-score、PMI 绝对零法）
- **形式**：Markdown 渲染 + 交互式图表解释

---

### Phase 4: 独立发布方案

#### 4.1 打包方案对比

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **A. 开发模式** | 无需打包，git clone 即用 | 需要 Python + Node 环境 | ⭐⭐⭐ 适合技术用户 |
| **B. Docker 容器** | 环境隔离，一键启动 | 需要 Docker 知识 | ⭐⭐⭐⭐ 推荐 |
| **C. PyInstaller + 静态前端** | 双击运行，无依赖 | 体积大，更新麻烦 | ⭐⭐ 适合非技术用户 |
| **D. 纯静态导出** | 前端静态托管 | 无后端计算能力 | ⭐ 不推荐 |

#### 4.2 推荐方案：Docker + 开发模式双轨

**Docker 方案**（面向最终用户）：
```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 安装 Node.js（用于 Next.js）
RUN apt-get update && apt-get install -y nodejs npm

# 复制代码
COPY . .

# 构建前端
RUN cd dashboard && npm install && npm run build

# 启动脚本（同时启动 FastAPI 和 Next.js）
COPY start.sh .
CMD ["./start.sh"]
```

**开发模式**（面向开发者/用户自定义）：
```bash
# 1. 克隆仓库
git clone <repo>
cd investment-agent

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 安装前端依赖
cd dashboard && npm install

# 4. 启动后端（终端1）
cd .. && uvicorn dashboard.api.main:app --port 8742

# 5. 启动前端（终端2）
cd dashboard && npm run dev -- -p 3011

# 6. 打开浏览器
open http://localhost:3011
```

#### 4.3 发布 checklist
- [ ] 代码清理（移除项目特定路径硬编码）
- [ ] 配置外部化（数据库路径、API 端口等通过环境变量）
- [ ] README 编写（安装、配置、使用）
- [ ] 开源许可证选择（MIT / Apache-2.0）
- [ ] GitHub Release 打包

---

## 3. 技术细节

### 3.1 AKShare 数据延迟处理

**问题**：AKShare 宏观数据通常延迟 1-2 个月（如 2026 年 1 月数据可能在 2 月中旬发布）。

**方案**：
1. **数据新鲜度检查**：Fetcher 返回数据时标记 `latest_available_date`
2. **部分更新**：只更新已发布的数据，不报错
3. **用户提示**：Dashboard 显示 "数据滞后 X 天，最新可用：2026-01-31"
4. **手动补录**：保留现有 CSV 上传功能作为兜底

### 3.2 数据一致性保障

**同步管理器设计**：
```python
class SyncManager:
    def sync_indicator(self, code: str):
        # 1. 查询 DB 最新日期
        db_latest = self.get_db_latest(code)
        
        # 2. 获取新数据
        fetcher = self.get_fetcher(code)
        new_data = fetcher.fetch(start_date=db_latest + 1 day)
        
        # 3. 校验
        validator = DataValidator(code)
        valid_data = validator.validate(new_data)
        
        # 4. 冲突处理（如有相同日期）
        conflicts = self.find_conflicts(valid_data)
        if conflicts:
            self.resolve_conflicts(conflicts, strategy='replace')  # 或 'skip'
        
        # 5. 写入
        self.import_to_db(valid_data)
        
        # 6. 返回报告
        return SyncReport(added=len(valid_data), updated=len(conflicts))
```

### 3.3 前端性能优化

**大数据量处理**（历史数据可能 10 年+）：
- **后端聚合**：API 支持 `sampling` 参数（如日频数据按周/月聚合）
- **前端虚拟化**：表格使用虚拟滚动
- **图表优化**：Plotly 的 `scattergl`（WebGL 渲染）处理大量数据点
- **缓存策略**：TanStack Query 缓存历史数据，减少重复请求

### 3.4 移动端适配

- 使用 Tailwind CSS 的响应式类（`md:`, `lg:`）
- 复杂图表在移动端切换为简化视图（卡片式摘要）
- 导航栏折叠为汉堡菜单

---

## 4. 实施时间表（预估）

| 阶段 | 内容 | 预估工时 | 依赖 |
|------|------|----------|------|
| **Phase 1** | 数据自动获取模块 | 16h | 无 |
| 1.1 | AKShare 适配器 + 6 个月频指标 | 6h | |
| 1.2 | 央行 OMO 爬虫 | 4h | |
| 1.3 | 同步管理器 + 调度器 | 4h | |
| 1.4 | 集成到 MacroStateSkill | 2h | |
| **Phase 2** | Dashboard 后端 API | 12h | Phase 1 |
| 2.1 | FastAPI 项目搭建 + 数据模型 | 2h | |
| 2.2 | 数据查询 API（指标/因子/状态） | 4h | |
| 2.3 | 分析 API（周期位置/语言描述） | 4h | |
| 2.4 | 数据管理 API（触发抓取/状态检查） | 2h | |
| **Phase 3** | Dashboard 前端 | 24h | Phase 2 |
| 3.1 | 项目搭建 + 布局框架 + 导航 | 4h | |
| 3.2 | 【面板1】历史走势（图表） | 6h | |
| 3.3 | 【面板2】截面分析（卡片+表格） | 5h | |
| 3.4 | 【面板3】语言分析（模板生成） | 4h | |
| 3.5 | 【面板4】方法论（Markdown） | 3h | |
| 3.6 | 响应式适配 + 性能优化 | 2h | |
| **Phase 4** | 独立发布 | 8h | Phase 3 |
| 4.1 | Docker 化 | 3h | |
| 4.2 | 配置外部化 + 文档 | 3h | |
| 4.3 | 测试 + Bug 修复 | 2h | |
| **总计** | | **60h** | |

> 注：此为纯开发时间估算，不含测试数据准备、文档编写、用户反馈迭代。

---

## 5. 关键决策点

在启动实施前，需要确认以下决策：

### 决策 1：OMO 利率获取方式
- **选项 A**：自建央行官网爬虫（推荐，灵活但需维护）
- **选项 B**：使用第三方财经 API（如 Wind、Choice，可能有费用）
- **选项 C**：保留手动上传作为唯一来源（不推荐，违背自动化目标）

### 决策 2：语言描述生成方式
- **选项 A**：基于规则模板生成（简单、可控、无需外部依赖）
- **选项 B**：接入 LLM API（更自然、但需要 API Key 和费用）
- **选项 C**：两者结合（规则生成 + LLM 润色）

### 决策 3：前端图表库
- **选项 A**：Plotly.js（功能强大、3D 支持、与 Python 生态一致）
- **选项 B**：ECharts（性能更好、中文文档完善、适合大数据量）
- **选项 C**：D3.js（最灵活、但学习成本高）

### 决策 4：发布形式
- **选项 A**：仅开发模式（适合技术用户，维护成本低）
- **选项 B**：Docker 容器（推荐，平衡易用性和可维护性）
- **选项 C**：桌面应用打包（对非技术用户最友好，但打包复杂）

### 决策 5：数据更新触发方式
- **选项 A**：手动触发（用户点击 "更新数据" 按钮）
- **选项 B**：启动时自动检查（系统启动时检查是否有新数据）
- **选项 C**：定时任务（后台每月自动抓取，需要常驻进程）

---

## 6. 风险与应对

| 风险 | 影响 | 应对方案 |
|------|------|----------|
| AKShare 接口变更 | 数据抓取失败 | 封装适配器层，隔离变化；保留手动上传兜底 |
| 央行官网改版 | OMO 爬虫失效 | 监控爬虫健康状态；失效时自动降级为手动模式 |
| 大数据量导致前端卡顿 | 用户体验差 | 后端聚合采样；前端虚拟化；WebGL 渲染 |
| 用户无 Node.js 环境 | 无法运行前端 | 提供 Docker 方案；或提供预构建静态文件 |
| 数据延迟导致分析过时 | 决策依据不准确 | 显式标注数据时效；延迟超过阈值时提醒用户 |

---

## 7. 下一步行动

1. **确认关键决策**（上方 5 个决策点）
2. **确认实施范围**：是否分阶段交付（如先 Phase 1+2，再 Phase 3）
3. **启动 Phase 1**：数据自动获取模块开发
4. **并行准备**：前端项目脚手架搭建（不依赖后端）

---

*计划制定时间：2026-05-24*  
*基于 Phase 2.3 V8 方法论*  
*参考架构：options-greeks-monitor (FastAPI + Next.js)*
