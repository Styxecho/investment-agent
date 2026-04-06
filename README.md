# Investment Agent 项目总览

## 📊 项目简介

基于 LangGraph 的智能投资组合分析 Agent，支持股票、ETF 和公募基金的组合跟踪、损益分析和时序分析。

**核心功能**：
- ✅ 实时市场数据获取（iFinD/AkShare）
- ✅ 投资组合损益计算
- ✅ 公募基金净值跟踪
- ✅ 交易日历支持
- ✅ 自然语言对话交互

---

## 📁 目录结构

```
investment-agent/
│
├── agents/                # Agent 工作流（LangGraph）
│   ├── workflow.py        # 状态图构建
│   ├── nodes.py           # 节点逻辑
│   ├── state.py           # 状态定义
│   └── tools.py           # 工具封装
│
├── skills/                # 业务技能层
│   ├── base.py            # Skill 基类
│   ├── market_data/       # 市场数据技能
│   │   ├── skill.py
│   │   ├── service.py
│   │   └── provider/      # 数据源实现
│   └── portfolio/         # 组合分析技能
│       ├── skill.py
│       ├── calculator.py
│       └── schema.py
│
├── config/                # 配置管理
│   ├── settings.py        # 全局配置
│   ├── enums.py           # 枚举定义
│   └── types.py           # 类型定义
│
├── utils/                 # 工具函数
│   ├── logger.py          # 日志系统
│   └── trade_calendar.py  # 交易日历服务
│
├── data_external/         # 外部数据层
│   ├── db/                # 数据库
│   │   ├── engine.py      # DB 引擎
│   │   ├── models.py      # ORM 模型
│   │   └── repositories.py# 数据仓储
│   └── reference/         # 静态参考数据
│       └── trade_calendar.csv
│
├── tests/                 # 测试用例
│   ├── conftest.py
│   ├── test_trade_calendar.py
│   ├── test_market_data_fund.py
│   └── ...
│
├── docs/                  # 项目文档
│   ├── PROJECT_CONTEXT_AND_ROADMAP.md
│   ├── P0_IMPLEMENTATION_REPORT.md
│   ├── FUND_IMPLEMENTATION_REPORT.md
│   └── HOLDINGS_README.md
│
├── scripts/               # 运维脚本
│   └── (待添加)
│
├── data_runtime/          # 运行时数据
│   ├── db/
│   ├── cache/
│   ├── logs/
│   └── reports/
│
├── archive/               # 归档代码
│
├── .env                   # 环境变量（敏感）
├── .gitignore
├── requirements.txt
├── holdings_template.csv  # 持仓模板
├── holdings.csv           # 实际持仓（不上传 Git）
└── pytest.ini
```

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 使用 Anaconda 创建环境
conda create -n investment_agent python=3.9
conda activate investment_agent

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件：
```env
# Qwen API 配置
QWEN_API_KEY=your_api_key_here
QWEN_MODEL=qwen-plus
USE_QWEN=true

# iFinD 配置（可选）
IFIND_USERNAME=your_username
IFIND_PIN=your_pin
```

### 3. 准备持仓文件

编辑 `holdings.csv`：
```csv
code,name,volume,cost_price,asset_type
600159.SH,贵州茅台，100,1500,stock
003956.OF,易方达蓝筹精选，1000,1.5000,fund
```

### 4. 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_trade_calendar.py -v
pytest tests/test_market_data_fund.py -v
```

### 5. 启动应用

```bash
# Streamlit 界面
streamlit run app.py
```

---

## 📖 文档索引

| 文档 | 说明 |
|------|------|
| [PROJECT CONTEXT AND ROADMAP.md](docs/PROJECT%20CONTEXT%20AND%20ROADMAP.md) | 项目蓝图和路线图 |
| [P0_IMPLEMENTATION_REPORT.md](docs/P0_IMPLEMENTATION_REPORT.md) | P0 阶段实施报告（Qwen 集成） |
| [FUND_IMPLEMENTATION_REPORT.md](docs/FUND_IMPLEMENTATION_REPORT.md) | 公募基金支持实施报告 |
| [HOLDINGS_README.md](docs/HOLDINGS_README.md) | 持仓文件使用说明 |

---

## 📊 核心功能

### 1. 市场数据获取

支持股票、ETF、公募基金：
- 股票/ETF：收盘价、昨收价、涨跌幅
- 基金：单位净值、累计净值、复权净值

```python
from skills.market_data.skill import get_market_data_skill
from skills.base import SkillContext

context = SkillContext(target_date="20260403")
result = get_market_data_skill.execute(
    context=context,
    symbol="600519.SH",
    asset_type="stock"
)
```

### 2. 组合分析

自动计算：
- 总市值、总成本、总盈亏
- 当日盈亏、收益率
- 个股权重、贡献度

```python
from skills.portfolio.skill import PortfolioSkill

skill = PortfolioSkill()
context = SkillContext(
    target_date="20260403",
    extra_params={"holdings": [...]}
)
result = skill.execute(context)
```

### 3. 交易日历

支持中国 A 股交易日历：
- 节假日判断
- T-1 日自动计算
- 每年手工维护一次

```python
from utils.trade_calendar import TradeCalendarService

calendar = TradeCalendarService(calendar_year=2026)
prev_date = calendar.get_previous_trading_date("20260407")
# 返回："20260404"（周五）
```

---

## 🧪 测试覆盖

| 模块 | 测试文件 | 状态 |
|------|----------|------|
| 交易日历 | `test_trade_calendar.py` | ✅ 9/9 通过 |
| 基金数据 | `test_market_data_fund.py` | ✅ 11/11 通过 |
| 市场数据 | `test_market_data_skill.py` | ✅ 通过 |
| Agent 工作流 | `test_stage4_agent_workflow.py` | ✅ 通过 |

---

## 📝 维护说明

### 每年一次：更新交易日历

编辑 `data_external/reference/trade_calendar.csv`，添加新年节假日。

### 按需：更新持仓

编辑 `holdings.csv`，更新你的实际持仓。

### 定期：运行测试

```bash
pytest -v
```

---

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证。

---

**最后更新**: 2026-04-05  
**维护者**: Investment Agent Team
