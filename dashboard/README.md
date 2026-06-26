# Investment Agent Dashboard

Phase 2.3 宏观状态分析的交互式可视化 Dashboard。

## 功能

### 面板1: 历史走势
- **指标选择器**: 按维度分组（增长/通胀/流动性），支持多选
- **时间范围**: 1年 / 3年 / 5年 / 全部
- **图表模式**:
  - **双轴图**: 左轴原始值 + 右轴Z-score
  - **周期分解**: raw / cycle / trend 堆叠图
  - **Z-score时间线**: 带阈值带和方向着色
- **象限背景**: 10种象限颜色图例

### 面板2: 截面分析
- **象限卡片**: 大卡片展示当前象限（带颜色标识）
- **三维度卡片**: 增长 / 通胀 / 流动性详情
- **因子明细表**: 各指标的原始值、Z-score、偏离度、方向
- **月份选择器**: 查看任意历史月份
- **WARNING提示**: 自动显示风险提示

### 面板3: 语言分析
- **状态综述**: 自动生成当前状态的文字描述
- **维度解读**: 增长/通胀/流动性分别解读
- **风险提示**: 显示WARNING详细信息
- **策略含义**: 基于象限的预设策略建议
- **历史对比**: 查找相似历史时期（预留）

### 面板4: 方法论
- **框架总览**: V7/V8方法论流程说明
- **维度方法论**: 增长/通胀/流动性分别说明
- **象限映射表**: 10级优先级完整表格
- **术语表**: 核心概念解释

## 技术栈

- **前端**: Next.js 14 + React + TypeScript + Tailwind CSS + Plotly.js
- **后端**: FastAPI + SQLAlchemy + Pandas
- **数据库**: SQLite (复用现有 external_data.db)

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+

### 安装

```bash
# 1. 克隆仓库
git clone <repo-url>
cd investment-agent

# 2. 安装 Python 依赖
pip install -r dashboard/requirements.txt

# 3. 安装前端依赖
cd dashboard/frontend && npm install && cd ../..

# 4. 启动 Dashboard
python scripts/start_dashboard.py
```

### 访问

- Dashboard UI: http://127.0.0.1:3011
- API Docs: http://127.0.0.1:8742/docs

## 项目结构

```
dashboard/
├── backend/              # FastAPI 后端
│   ├── main.py          # 应用入口
│   ├── config.py        # 配置管理
│   ├── database.py      # DB 连接（复用现有DB）
│   ├── routers/         # API 路由
│   │   ├── indicators.py   # 指标查询 API
│   │   ├── factors.py      # 因子查询 API
│   │   ├── states.py       # 宏观状态 API
│   │   └── analysis.py     # 分析接口（语言描述）
│   ├── services/        # 业务逻辑
│   │   ├── indicator_service.py
│   │   ├── factor_service.py
│   │   └── state_service.py
│   └── schemas/         # Pydantic 数据模型
│       └── __init__.py
├── frontend/            # Next.js 前端
│   ├── app/            # App Router
│   │   ├── layout.tsx       # 根布局
│   │   ├── page.tsx         # 首页（重定向到截面分析）
│   │   ├── providers.tsx    # React Query Provider
│   │   ├── panel-history/   # 面板1: 历史走势
│   │   ├── panel-snapshot/  # 面板2: 截面分析
│   │   ├── panel-narrative/ # 面板3: 语言分析
│   │   └── panel-methodology/ # 面板4: 方法论
│   ├── components/
│   │   ├── layout/          # Navbar, Footer
│   │   ├── shared/          # PlotlyChart 封装
│   │   └── ui/             # shadcn/ui 组件
│   ├── hooks/            # React Query Hooks
│   │   ├── useStates.ts
│   │   ├── useIndicators.ts
│   │   └── useAnalysis.ts
│   ├── lib/              # 工具函数
│   │   ├── api.ts        # API 客户端
│   │   └── utils.ts      # 格式化/颜色等工具
│   └── stores/           # Zustand 状态管理
└── README.md
```

## API 端点

```
GET  /api/v1/indicators/catalog          # 指标目录
GET  /api/v1/indicators/history          # 指标历史数据
GET  /api/v1/indicators/latest           # 最新指标值
GET  /api/v1/factors/decomposition/{code} # 因子分解
GET  /api/v1/factors/latest              # 最新因子值
GET  /api/v1/states/history              # 宏观状态历史
GET  /api/v1/states/latest               # 最新宏观状态
GET  /api/v1/states/{date}               # 指定日期状态
GET  /api/v1/states/regime-transitions   # 象限转换历史
GET  /api/v1/analysis/narrative/{date}   # 生成语言描述
```

## 开发状态

### 已完成 (Phase A)
- [x] 后端 API (indicators, factors, states, analysis)
- [x] 面板1: 历史走势（双轴图、周期分解、Z-score时间线）
- [x] 面板2: 截面分析（象限卡片、维度卡片、因子表）
- [x] 面板3: 语言分析（规则模板生成）
- [x] 面板4: 方法论（完整文档）
- [x] 统一启动脚本
- [x] 后端服务测试通过

### 待优化 (Phase B)
- [ ] 数据对比功能（与上月/去年同期对比）
- [ ] 历史相似时期搜索
- [ ] 数据导出（CSV/PNG/PDF）
- [ ] 响应式适配优化
- [ ] 性能优化（大数据量采样）
- [ ] 面板间联动（点击跳转）

### 待发布 (Phase C)
- [ ] 代码清理（移除硬编码）
- [ ] README 完善
- [ ] LICENSE 选择
- [ ] GitHub Release

## License

MIT
