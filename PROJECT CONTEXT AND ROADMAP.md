Investment Agent: Project Context & Roadmap
最后更新时间: 2026-03-19
版本: v2.3 (OpenCLAW 架构融合版)
状态: 🟢 阶段一 (内核重构) 进行中
设计哲学: 功能优先，架构简化，智能驱动。融合 OpenCLAW 模块化思想，实现“代码计算 + LLM 解读”的双引擎模式。

1. 项目核心目标 (Core Objectives)
构建一个功能丰富、本地运行、架构简洁且高度智能的个人投资组合管理智能体。
功能优先 (Feature First)：首要目标是快速迭代并扩展 Agent 的实用功能（如自动记账、归因分析、自然语言问答）。
精度适度 (Practical Precision)：兼顾计算精度，确保金额误差控制在 小数点后两位 (0.01) 以内，满足个人记账与复盘需求。
架构简化 (Simplified Architecture)：去除复杂的分布式组件，采用适合个人本地部署的单机架构。保证系统易于维护、易于启动、易于备份。
数据沉淀 (Data Accumulation)：自动归档每日数据，形成个人专属的投资历史数据库，为长期分析提供燃料。
智能辅助 (Intelligent Assistance)：[核心特色] 汲取 OpenCLAW 理念，为每个业务技能配备专属 Prompt 模板。让 LLM 不仅能调用工具，还能理解工具的输出语境，生成专业、连贯的投资建议与复盘报告。

2. 技术栈 (Tech Stack - Practical Edition)
| 层级 | 技术组件 | 用途与简化策略 |
| :--- | :--- | :--- |
| 核心框架 | LangGraph | 编排对话状态机。利用其成熟生态快速实现多轮对话与工具调用。 |
| 大模型 | Ollama | 本地运行 (如 Qwen2.5-7B)。零 API 费用，数据隐私安全。 |
| 数据存储 | SQLite + SQLAlchemy | 单文件数据库。无需安装数据库服务，备份只需拷贝 `.db` 文件。 |
| 数值计算 | Python `float` + `round()` | 使用标准浮点数计算，关键输出时使用 `round(value, 2)` 截断，确保误差 < 0.01。 |
| 数据处理 | Pandas | 高效处理 CSV/Excel 及行情数据清洗。 |
| 数据验证 | Pydantic | 定义数据结构。用于确保输入输出的格式一致。 |
| 技能架构 | Modular Skills + Prompts | [OpenCLAW 风格] 每个 Skill 包含 `.py` (逻辑) 和 `.txt/.md` (Prompt 模板)，实现逻辑与提示词解耦。 |
| 数据源 | iFinD API | 主要行情源。封装简单的重试逻辑。 |
| 任务调度 | OS Cron / Task Scheduler | 利用操作系统原生定时任务，无需常驻后台进程。 |
| 日志与监控 | Logging (StdLib) | 记录运行日志，方便排查问题。 |



3. 项目目录结构（Project Structure）
investment_agent/
│
├── .venv/                  # [忽略] 虚拟环境
├── archive/                # [归档] 旧版本或废弃代码
├── data_runtime/           # [临时] 运行时生成的临时文件 (CSV/JSON)
├── tests/                  # [测试] 单元测试用例 (按阶段划分)
│   ├── test_stage1.py      # 阶段 1: 内核与模型测试
│   ├── test_stage3.py      # 阶段 3: 持久化与调度测试
│   ├── test_stage2.py      # 阶段 2: 归因分析测试
│   └── ...
│
├── config/                 # [配置] 全局配置管理
│   ├── settings.py         # 单例配置 (DB 路径, Model 名称, API 端点)
│   └── enums.py            # 枚举定义 (市场类型, 数据源类型)
│
├── utils/                  # [工具] 通用辅助函数
│   └── logger.py           # 统一日志记录
│
├── data_external/          # [数据层] 外部数据持久化 (SQLAlchemy)
│   ├── engine.py           # DB 引擎初始化
│   ├── models.py           # ORM 模型 (DailySnapshot, AssetPosition)
│   └── repositories.py     # 数据访问层 (CRUD 操作)
│
├── market/                 # [市场] 市场行情参考 (预留)
│   └── reference/
│
├── skills/                 # [核心] 业务技能层 (无状态纯函数库)
│   ├── base.py             # 基础 Skill 类定义
│   ├── data_fetch.py       # 数据获取技能 (封装 iFinD, 含重试逻辑)
│   ├── portfolio_calculator.py # [重构重点] 核心计算引擎 (PnL, 权重)
│   ├── market_data/        # 子技能：市场数据查询扩展
│   └── portfolio/          # 子技能：持仓分析 (归因、趋势等)
│
├── agents/                 # [核心] Agent 编排层 (LangGraph)
│   ├── state.py            # 定义 AgentState (TypedDict, 包含结构化数据)
│   ├── nodes.py            # 节点逻辑 (调用 Skills, 更新 State)
│   └── workflow.py         # 构建 StateGraph (编译工作流)
│
├── scripts/                # [脚本] 辅助运维脚本
│   └── daily_job.py        # (规划中) 定时任务入口
│
├── .env                    # [敏感] 环境变量 (API Keys, DB URLs)
├── holdings_template.csv   # [数据] 持仓模板文件
└── PROJECT CONTEXT AND ROADMAP.md # [文档] 本项目路线图


. 演进路线图 (Roadmap - 1-3-2-4 Strategy with OpenCLAW Pattern)
本路线图深度融合 OpenCLAW 模块化思想，每个阶段的交付物不仅包含代码逻辑，还包含对应的 Prompt 资产。
🟢 阶段一：内核重构与技能模块化 (Core & Modular Skills)
🎯 阶段一核心目标（最终版）
稳定性 (Robustness)：建立“本地缓存优先 + 异常重试”机制，杜绝因网络/API问题导致的崩溃。
功能性 (Functionality)：扩展计算维度（日度损益、权重、贡献度），为分析提供数据支撑。
架构性 (Architecture)：实现“代码逻辑纯函数化 + Prompt 模板独立化”的 OpenCLAW 风格技能。
可靠性 (Reliability)：[新增] 通过严格的单元测试，确保计算逻辑零误差（<0.01），且缓存机制行为符合预期。
🗺️ 阶段一详细执行路线图 (Step-by-Step with Testing & Caching)
第 1 步：架构基石 —— 定义 BaseSkill 与 Result 契约
目标：确立标准，让所有技能有章可循。
动作：
创建 skills/base.py，定义 BaseSkill 抽象基类。
定义 SkillResult 数据模型（Pydantic），包含：
data: 核心计算/获取结果（Dict）。
meta: 元数据（如 source: 'cache' 或 'api', status: 'success'/'failed', timestamp）。
message: 给 LLM 的自然语言提示（如“已从本地加载今日数据”）。
设计 execute(context) 抽象方法，强制子类实现纯函数逻辑。
实现自动加载同目录下 prompt.txt 的机制。
第 2 步：数据层升级 —— MarketDataSkill (缓存优先 + 重试)
目标：实现“本地数据库优先，API 兜底，自动回填”的稳健数据获取流程。
动作：
缓存逻辑：
请求数据时，先查 SQLite 本地库（按 date + asset_code 索引）。
若命中且未过期（如当日数据），直接返回，标记 source: 'cache'。
若未命中，调用 iFinD API。
重试机制：API 调用失败时，指数退避重试 3 次。
回填逻辑：API 成功后，立即写入 SQLite，再返回结果，标记 source: 'api'。
异常处理：若 API 彻底失败，返回 status: 'failed' 及错误原因，不抛异常，让上游决定如何处理（如使用昨日数据或告知用户）。
Mock 支持：增加配置开关，测试时可强制返回预设数据。
测试重点 (Unit Tests)：
测试“缓存命中”场景：验证是否未调用 API。
测试“缓存未命中”场景：验证是否调用 API 并写入数据库。
测试“API 失败”场景：验证重试机制是否触发，以及最终是否返回友好的错误结果。
测试“数据完整性”：验证返回字段是否符合预期。
第 3 步：计算层进化 —— PortfolioSkill (纯函数 + 多维计算)
目标：实现无副作用、功能丰富的计算引擎。
动作：
纯函数重构：calculate(holdings_df, market_data_df) 不读写文件，不依赖全局状态。输入输出完全确定。
功能扩充：
计算 Total_Market_Value, Total_Cost, Total_PnL (累计损益)。
计算 Daily_PnL (需利用市场数据中的昨日收盘价)。
计算 Weights (各资产权重)。
计算 Contributions (各资产对总损益的贡献额及比例)。
精度控制：中间过程使用 float，最终输出数值字段统一 round(, 2)。
测试重点 (Unit Tests) —— 核心环节：
构造测试用例：准备一组已知输入的 holdings 和 market_data（包含今日/昨日价格）。
预期结果验证：手动计算或使用 Excel 验证预期结果，断言代码输出与预期值的误差 < 0.001。
边界测试：测试空持仓、价格为 0、负收益等极端情况。
精度测试：专门构造易产生浮点误差的数据（如 1/3 相关计算），验证 round(, 2) 后的结果是否正确。
第 4 步：Prompt 工程 —— 为技能注入“灵魂”
目标：让 LLM 能准确解读数据，并优雅地处理异常情况。
动作：
编写 market_data/prompt.txt：教导 LLM 识别 meta.source 和 meta.status。例如：“如果数据来自缓存，告诉用户‘已加载本地保存的最新数据’；如果获取失败，请委婉告知用户并建议检查网络。”
编写 portfolio/prompt.txt：定义金融术语解释口径。例如：“当解释‘收益贡献’时，请使用公式：贡献额 = 持仓市值 * 个股涨跌幅。如果某股权重高但贡献低，请提示用户注意该股表现拖累了组合。”
风格调优：设定 Agent 的语气（专业、客观、略带鼓励）。
第 5 步：集成联调与端到端测试
目标：验证全流程打通，Agent 能像真人一样工作。
动作：
在 LangGraph 中编排 MarketDataSkill -> PortfolioSkill -> LLM Node。
场景测试：
正常交易日：模拟首次运行（无缓存）和二次运行（有缓存），观察 Agent 回答差异。
非交易日/断网：模拟 API 失败，观察 Agent 是否能优雅降级或报错。
复杂问答：询问“今天哪个股票贡献最大？”，验证 LLM 是否能正确读取 Contributions 数据并回答。
性能检查：确认缓存机制是否显著减少了 API 调用次数。

🔵 阶段二：记忆系统与自动化归档 (Memory & Automation)
目标: 自动积累数据，让 Prompt 有“历史”可依。
2.1 快照存储技能:
开发 save_snapshot 技能，将每日计算结果存入 SQLite。
配套 prompt.txt：指导 LLM 在用户询问“上个月表现如何”时，知道去查哪个表。
2.2 自动化脚本: 编写 scripts/daily_job.py，串联 fetch -> calculate -> save。
2.3 系统调度: 配置 OS 定时任务，每日自动运行。
2.4 日报生成技能:
开发 generate_daily_report 技能，从 DB 读取当日数据。
重点编写 Prompt：设计一套专业的“投资日报”语调，让 LLM 自动总结今日盈亏、亮点与风险。
🟠 阶段三：分析能力深化与智能解读 (Deep Analysis & Smart Interpretation)
目标: 利用 Prompt 工程释放 LLM 的分析潜力，不仅仅是报数字。
3.1 归因分析技能:
开发 analysis/attribution.py (计算板块/个股贡献度)。
核心 Prompt 设计：编写复杂的 Prompt，教导 LLM 识别“是选股赚了钱”还是“仓位赌对了”，并生成归因结论。
3.2 趋势与风险技能:
开发计算波动率、最大回撤的逻辑。
配套 Prompt：让 LLM 能根据回撤数据，给出温和的风险提示（如“当前波动率高于过去 30 天均值”）。
3.3 多技能协同: 在 LangGraph 中优化路由，让 Agent 能根据用户问题，自动组合调用“查询 + 计算 + 归因”多个技能，并串联它们的 Prompt 上下文。
🟣 阶段四：交互升级与人机协作 (UI & Collaboration)
目标: 可视化展示，人工介入修正。
4.1 简易看板 (可选): Streamlit 展示核心指标。
4.2 交互式修正技能:
开发允许用户通过自然语言修正持仓成本的技能。
配套 Prompt：让 LLM 确认用户的修正意图（“您确定要将 A 股票的成本价改为 10.5 元吗？”），确保操作安全。
4.3 个性化 Prompt 调优: 根据长期使用习惯，微调各个技能的 Prompt，使 Agent 的回答风格更符合个人偏好。


5. 关键设计原则 (Design Principles)
功能驱动: 优先实现用户最需要的功能。
精度务实: 接受 float 微小误差，输出 round(2)。
双驱动技能 (Dual-Drive Skills): 每个业务能力 = 确定性代码 (Python) + 不确定性解读 (Prompt)。代码负责算对，Prompt 负责说好。
架构可用: 个人本地轻松运行，Prompt 文件独立管理，便于单独优化话术而不改动代码。