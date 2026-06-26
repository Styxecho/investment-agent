# Phase 2.3 总结 - 宏观状态诊断体系V7

**最后更新**: 2026-05-08
**状态**: 核心构建完成，待审核
**执行人**: OpenCode + 用户协作

---

## 一、Phase目标

构建基于三维同构框架（增长×通胀×流动性）的宏观状态诊断体系，输出定性状态标签，为行业轮动提供顶层决策依据。

**核心要求**:
- 水平与方向解耦：水平衡量绝对位置，方向衡量边际动态
- 逻辑完全同构：三维度严格遵循相同底层架构
- 输出分层：底层向量保留全信息，策略层映射为象限标签

---

## 二、核心成果

### 2.1 方法论文档

**文件**: `docs/research/macro_analysis/methodology_summary_V7.md`

**核心设计**:
- **增长维度**: PMI（绝对零点法）+ IAV（HP滤波），水平（扩张/中性/收缩），方向（上行/平稳/下行）
- **通胀维度**: 核心CPI（原始同比定水平）+ PPI（HP滤波定方向），水平（高/温和/低通胀）
- **流动性维度**: M2 + 社融（HP滤波定水平/方向）+ DR007价格否决权
- **状态合成**: 水平+方向=9种基础状态/维度
- **象限映射**: 10级优先级规则（P1极端滞胀→P10震荡观望）
- **WARNING系统**: 4类异常检测（成本传导背离/结构性假衰退/价格否决/社融财政干扰）

### 2.2 数据基础设施

**数据库表结构**:

| 表名 | 用途 | 记录数 |
|------|------|--------|
| `macro_indicator_catalog` | 指标目录 | 20个指标 |
| `macro_indicator_value` | 原始数据 | 20,449条 |
| `macro_factor_value` | V7因子值 | 1,693条 |
| `macro_factor_config` | 计算配置 | 保留旧配置 |
| `macro_state` | 简化状态 | 135条 |
| `macro_state_v7_detail` | 详细状态 | 135条 |

**数据覆盖**:
- **月度指标**（18个）: PMI制造/非制造/综合、工业增加值、CPI同比/环比/非食品、核心CPI同比/环比、PPI同比/环比/非食品、M0/M1/M2同比、社融存量同比/当月值、产成品存货同比
- **日度指标**（3个）: DR007、OMO利率、R007（全市场）
- **时间范围**: 2013-12 至 2026-03（月度），1999-12 至 2026-05（日度）

### 2.3 V7计算流水线

**核心算法**:

1. **单向HP滤波**（λ=129600，月度）
   - 输入：原始同比增速序列
   - 输出：周期项 + 趋势项
   - 禁止双向HP滤波（避免未来函数）

2. **PMI绝对零点法**（不HP滤波）
   - Z = (PMI - 50) / rolling_std(PMI - 50, 36)
   - 趋势项固定为50（荣枯线）

3. **滚动Z-score**（36月窗口）
   - Z = (cycle - rolling_mean) / rolling_std

4. **自适应偏离度**
   - deviation = Z - MA3(Z)
   - Threshold = ±1.0 × 滚动标准差

5. **趋势持续性规则**
   - 中性→非中性：单次击发
   - 非中性→中性：双重确认（连续两个月）

**实现脚本**:
- `skills/macro_state/` - V8 Skill模块（核心计算引擎）
- `scripts/reusable/macro_factor_pipeline.py` - 因子计算
- `scripts/reusable/macro_state_statistics.py` - 统计分析
- `scripts/reusable/macro_state_visualization.py` - 可视化

### 2.4 宏观状态输出

**135个月度状态**（2013-12至2026-03）:

| 象限标签 | 月份数 | 占比 | 平均持续 | 典型时期 |
|----------|--------|------|----------|----------|
| **震荡/观望** | 101 | 74.8% | 7.5月 | 2016-2020, 2020-2022 |
| **完美扩张** | 13 | 9.6% | 1.9月 | 2014-05~07, 2020-04~05, 2026-03 |
| **宽衰退** | 13 | 9.6% | 2.2月 | 2022-04~05, 2023-05~08, 2025-08 |
| **失速衰退** | 5 | 3.7% | 2.5月 | 2024-06~08, 2025-04~05 |
| **类衰退过渡** | 3 | 2.2% | 1.5月 | 2024-05, 2024-09~10 |

**最新状态（2026-03）**:
- 增长：扩张↑（PMI=50.4, IAV=5.7%）
- 通胀：温和通胀平稳（CoreCPI=1.1%, PPI=0.5%）
- 流动性：双宽（M2=8.5%, SFS=7.9%）
- **象限：完美扩张**

**WARNING统计**（37次/135月）:
- 成本传导背离：15次
- 流动性价格否决：25次
- 社融财政干扰嫌疑：2次

### 2.5 数据更新机制

**策略**: 以手工上传为主，自动获取为辅

**三层架构**:
1. **L1自动层**: AkShare API（延迟7-30天，仅作fallback）
2. **L2半自动层**: 统计局/央行官网爬虫（发布日触发）
3. **L3手动层**: CSV文件上传（主方案）

**手动上传工具**:
- 模板生成器：`scripts/reusable/generate_upload_template.py`
- 上传脚本：`scripts/reusable/upload_macro_data.py`
  - CSV格式校验（指标代码、日期、数值范围）
  - 环比突变检测
  - 自动触发V7流水线重算

**上传模板**: `docs/research/macro_analysis/templates/macro_upload_template_monthly.csv`

---

## 三、实施过程

### Step 1: 数据层重构（2026-05-08）

1. 清理旧数据：删除V2同名指标的旧记录
2. 导入V2月度CSV：18个指标，4,601条记录
3. 导入V2日度CSV：2个指标（DR007/OMO），5,027条记录
4. 补充R007：从旧CSV导入2,821条记录
5. 更新目录表：20个指标完整元信息

### Step 2: V7因子计算（2026-05-08）

1. 清除旧因子：3,873条旧记录
2. 新计算1,693条V7因子记录
3. 实现单向HP滤波器
4. 实现PMI绝对零点法
5. 实现趋势持续性状态机

### Step 3: 宏观状态判定（2026-05-08）

1. 增长维度合成：PMI + IAV + 结构仲裁
2. 通胀维度合成：核心CPI水平 + PPI/CPI方向
3. 流动性维度合成：M2 + 社融 + 价格否决权
4. 10级象限映射
5. 4类WARNING检测

### Step 4: 输出与审核（2026-05-08）

1. 生成macro_state_detail.csv（含所有中间变量）
2. 生成统计报告和转换矩阵
3. 准备手动上传工具

---

## 四、关键决策记录

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-05-08 | V7方法论取代V6 | 用户重新编写，从数据源到算法全面重构 |
| 2026-05-08 | 全量数据入库 | 无论是否用到，所有指标先初始化到数据库 |
| 2026-05-08 | 社融改为存量同比 | V7要求社融存量同比增速，CN_SFS_YOY_M已符合 |
| 2026-05-08 | M1M2剪刀差→M2单独 | 流动性维度改用M2+社融，不再用M1-M2 |
| 2026-05-08 | 核心CPI替代CPI | 通胀水平以核心CPI为主 |
| 2026-05-08 | PMI绝对零点法 | 避免长期中枢下移导致偏离度失真 |
| 2026-05-08 | 手工上传为主 | 月频数据更新成本低、准确性高，AkShare延迟大 |
| 2026-05-08 | 日期格式YYYYMMDD | Schema明确定义publish_date为String(8) |

---

## 五、技术债务与待优化

### 高优先级
1. **用户审核**: macro_state_detail.csv中间计算结果需人工校验
2. **Skill封装**: 将V7流水线脚本整合为MacroStateSkill
3. **数据更新**: 建立月度更新SOP（模板生成→数据填充→上传→验证）

### 中优先级
4. **AkShare适配器**: 实现自动获取层作为fallback
5. **可视化**: 象限变迁图（需要matplotlib安装）
6. **历史验证**: 用4个历史时期验证V7判定的准确性

### 低优先级
7. **Web界面**: Streamlit上传界面
8. **邮件通知**: 数据发布提醒
9. **数据版本控制**: 修订历史追踪

---

## 六、文件清单

### 方法论与文档
- `docs/research/macro_analysis/methodology_summary_V7.md` - V7方法论
- `docs/research/macro_analysis/data_update_mechanism_design.md` - 更新机制设计

### 数据文件
- `docs/research/macro_analysis/macro_state_detail.csv` - 详细审核数据（含所有中间变量）
- `docs/research/macro_analysis/macro_state_statistics_summary.csv` - 统计报告
- `docs/research/macro_analysis/macro_state_transition_matrix.csv` - 转换矩阵
- `docs/research/macro_analysis/templates/macro_upload_template_monthly.csv` - 上传模板

### 脚本（scripts/reusable/）
- `macro_factor_pipeline.py` - 因子计算
- `skills/macro_state/` - V8 Skill模块（核心引擎）
- `macro_state_statistics.py` - 统计分析
- `macro_state_visualization.py` - 可视化
- `upload_macro_data.py` - 手动上传工具
- `generate_upload_template.py` - 模板生成器
- `import_v2_macro_data.py` - V2数据导入
- `verify_v7_states.py` - 状态验证
- `clear_old_factors.py` - 旧因子清理

### 数据库
- `data_external/db/external_data.db` - SQLite数据库（6张宏观相关表）

---

## 七、下一阶段（Phase 2.4）建议

**目标**: 中观行业比较

**输入**: Phase 2.3输出的宏观象限标签（如"完美扩张"）
**输出**: 行业配置建议（如"增持顺周期/成长"）

**待建设能力**:
1. 行业相对强度计算（行业指数vs宽基指数）
2. 北向资金行业流向追踪
3. 行业盈利预期变化（分析师一致预期）
4. 行业估值分位数（PE/PB历史分位）

---

*本文件为Phase 2.3阶段总结，供后续Phase参考。*
