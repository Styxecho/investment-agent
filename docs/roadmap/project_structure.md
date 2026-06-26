# Project Structure - Investment Agent

**最后更新**: 2026-04-23
**版本**: v1.0

---

## 根目录

```
investment-agent/
├── project_memory.md       # 项目记忆（当前状态+记忆索引）
├── docs/                   # 文档中心
├── config/                 # 全局配置
├── utils/                  # 通用工具
├── data_external/          # 外部数据层
├── skills/                 # 业务技能层
├── agents/                 # Agent编排层
├── scripts/                # 运维脚本
├── data_runtime/           # 运行时临时文件
├── tests/                  # 测试
├── .env                    # 环境变量
├── requirements.txt        # 依赖
└── holdings.csv            # 实际持仓（用户数据）
```

---

## docs/ 文档中心

```
docs/
├── README.md                    # 文档中心索引与规范
├── roadmap/                     # 项目规划
│   ├── project_context.md       # 项目目标与技术栈
│   ├── project_roadmap.md       # Phase框架与规划
│   ├── project_structure.md     # 目录结构说明
│   ├── phase01_summary.md       # Phase 1 总结
│   ├── phase02_summary.md       # Phase 2 总结（完成后）
│   └── phase02_progress.md      # Phase 2 当前进度
├── reports/                     # 综合报告
├── research/                    # 研究报告
├── guides/                      # 使用指南
├── schema/                      # 数据库结构
└── fixes/                       # 问题修复记录
```

---

## skills/ 业务技能层

```
skills/
├── base.py                      # Skill基类
├── market_data/                 # 市场数据技能
│   ├── skill.py
│   ├── schema.py
│   ├── prompt.txt
│   └── providers/
│       ├── base.py
│       ├── ifind_provider.py    # iFinD数据源（主力）
│       └── akshare_provider.py  # AkShare数据源（降级）
├── portfolio/                   # 组合研究技能
│   ├── calculator.py            # 盈亏计算引擎
│   ├── schema.py
│   ├── skill.py
│   ├── prompt.txt
│   ├── backtest/                # 回测引擎
│   │   ├── engine.py
│   │   ├── performance.py
│   │   └── risk_parity.py
│   └── snapshot/                # 快照持久化
│       ├── snapshot_skill.py
│       └── prompt.txt
└── macro_factor/                # 宏观因子与状态技能
    ├── skill.py                 # MacroFactorSkill（计算/查询）
    ├── service.py               # 因子计算服务
    ├── schema.py                # 数据模型
    ├── pipeline.py              # 计算流水线
    └── filters/                 # 滤波器实现
        ├── base_filter.py
        └── hp_filter.py
```

---

## data_external/ 数据层

```
data_external/
├── db/                          # SQLite数据库
│   ├── external_data.db         # 数据库文件
│   ├── engine.py                # DB引擎
│   ├── models.py                # ORM模型
│   └── repositories.py          # 数据访问层
└── reference/                   # 静态参考数据
    ├── trade_calendar.csv       # 交易日历
    ├── etf_universe.csv         # ETF列表与标签
    └── index_universe.csv       # 指数映射表
```

---

## 宏观数据分析目录

```
docs/research/macro_analysis/
├── methodology_summary_V7.md          # V7方法论
├── data_update_mechanism_design.md    # 数据更新机制设计
├── macro_state_detail.csv            # 详细审核数据（含所有中间变量）
├── v7_statistics_summary.csv          # 统计报告
├── v7_transition_matrix.csv           # 象限转换矩阵
├── raw_data/                          # 原始数据CSV
│   ├── marco_indicators_history_series_monthly_v2.csv
│   └── macro_indicators_history_series_daily_v2.csv
└── templates/                         # 上传模板
    └── macro_upload_template_monthly.csv
```

---

## 关键数据文件

| 文件 | 用途 | 维护方式 |
|------|------|----------|
| `data_external/reference/etf_universe.csv` | 249只ETF元数据 | 手工维护 |
| `data_external/reference/index_universe.csv` | 指数映射 | 手工维护 |
| `data_external/reference/trade_calendar.csv` | 交易日历 | 手工维护 |
| `D:\Study\Research\ETF\csindex\` | 指数成分股权重 | 批量下载+手工补齐 |
| `data_external/db/external_data.db` | 行情缓存+宏观数据 | 自动写入/手工上传 |
| `docs/research/macro_analysis/templates/*.csv` | 宏观数据上传模板 | 自动生成+手工填充 |
