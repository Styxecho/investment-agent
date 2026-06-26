# 项目文档中心

本文档中心存放 `investment-agent` 项目的所有说明、报告、规范与研究资料。

---

## 目录结构说明

```
docs/
├── roadmap/          # 项目规划与路线图
├── reports/          # 阶段性实施完成报告
├── fixes/            # 单个问题/Bug 的修复记录
├── guides/           # 用户操作指南与使用说明
├── research/         # 技术研究、算法探索与原型验证
├── schema/           # 数据库结构、数据字典与接口契约
└── README.md         # 本文档（目录索引与规范说明）
```

### 各子目录用途

| 目录 | 用途 | 示例文件 |
|------|------|----------|
| `roadmap/` | 记录项目长期目标、技术选型、阶段划分与演进路线 | `PROJECT_CONTEXT_AND_ROADMAP.md` |
| `reports/` | 每个阶段或大功能交付后撰写的实施总结报告 | `P0_IMPLEMENTATION_REPORT.md` |
| `fixes/` | 针对特定 Bug 或问题的根因分析、修复方案与验证记录 | `QWEN_TOOL_CALL_FIX.md` |
| `guides/` | 面向使用者（含开发者自己）的操作手册、配置说明、文件模板 | `HOLDINGS_README.md` |
| `research/` | 对新技术、新算法、新数据源的预研与可行性分析 | `CVaR_FHS_IMPLEMENTATION.md` |
| `schema/` | 数据库表结构设计、字段说明、变更日志、ER 关系图 | `DATABASE_SCHEMA.md` |

---

## 文档命名规范

1. **使用英文或拼音 + 下划线命名**
   - 正确：`FUND_IMPLEMENTATION_REPORT.md`
   - 错误：`基金实施报告.md`、`PROJECT CONTEXT.md`

2. **文件后缀统一为 `.md`**
   - 所有文档使用 Markdown 格式，便于版本管理与阅读。

3. **报告类文件命名格式**
   - `{阶段/模块}_IMPLEMENTATION_REPORT.md`
   - `{模块/功能}_FIX.md`

4. **Schema 文档命名格式**
   - `DATABASE_SCHEMA.md`
   - `API_SCHEMA.md`（如有）

---

## 文档维护约定

1. **新增文档必须先归入对应子目录**
   - 不确定分类时，优先选择最贴近的目录，不可直接堆放在 `docs/` 根目录。

2. **数据库模型变更必须同步更新 `schema/DATABASE_SCHEMA.md`**
   - 新增表、修改字段、删除索引等操作，需在变更当天更新数据字典和变更日志。

3. **修复记录必须包含三要素**
   - 问题现象
   - 根因分析
   - 修复方案与验证结果

4. **报告类文档必须标注时间与版本**
   - 在文档头部明确标注生成日期、对应代码分支或 Commit 范围。

---

## 快速索引

### 必读文档
- [项目路线图](roadmap/PROJECT_CONTEXT_AND_ROADMAP.md)
- [P0 实施报告](reports/P0_IMPLEMENTATION_REPORT.md)
- [持仓文件使用说明](guides/HOLDINGS_README.md)
- [数据库结构说明](schema/DATABASE_SCHEMA.md)

### 最新变更
- 2026-04-14：`portfolio_snapshot` 表设计定稿，文档中心目录结构重构完成。
- 2026-04-06：基金净值日期范围查询修复完成。
- 2026-04-05：交易日历服务与公募基金数据支持上线。
- 2026-04-04：Qwen 云端大模型集成与 MVP 工具调用链路跑通。
