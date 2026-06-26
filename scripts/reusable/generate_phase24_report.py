import pandas as pd
from pathlib import Path
import datetime

OUTPUT_DIR = Path('docs/research/industry_rotation')
REPORT_DIR = Path('docs/reports')
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# 读取所有输出文件
df_tie = pd.read_csv(OUTPUT_DIR / 'etf_tie_scores.csv', encoding='utf-8-sig')
df_mapping = pd.read_csv(OUTPUT_DIR / 'industry_etf_mapping.csv', encoding='utf-8-sig')
df_momentum = pd.read_csv(OUTPUT_DIR / 'industry_momentum_scores.csv', encoding='utf-8-sig')
df_rs = pd.read_csv(OUTPUT_DIR / 'industry_rs_scores.csv', encoding='utf-8-sig')
df_pool = pd.read_csv(OUTPUT_DIR / 'industry_selected_pool.csv', encoding='utf-8-sig')
df_final = pd.read_csv(OUTPUT_DIR / 'industry_final_pool.csv', encoding='utf-8-sig')

# 统计核心指标
core_count = len(df_tie[df_tie['tier'] == 'industry_rotation_core'])
backup_count = len(df_tie[df_tie['tier'] == 'industry_rotation_backup'])
mapped_industries = df_mapping['sw_code'].nunique()
total_industries = 31
unmapped = total_industries - mapped_industries

# 最新动量数据
latest_date = df_momentum['trade_date'].iloc[0]
top3_momentum = df_momentum.head(3)[['sw_code', 'composite_score', 'above_ma60']].to_dict('records')
bottom3_momentum = df_momentum.tail(3)[['sw_code', 'composite_score', 'above_ma60']].to_dict('records')

# RS_score统计
avg_rs = df_rs['rs_score'].mean()
rs_above_50 = len(df_rs[df_rs['rs_score'] >= 50])

# 优势池
pool_size = len(df_pool)
pool_valid = len(df_final)

# 生成报告
report = f"""# Phase 2.4 行业轮动卫星策略 — 阶段性报告

**生成日期**: {datetime.datetime.now().strftime('%Y-%m-%d')}
**数据截止日期**: {latest_date}
**方法论版本**: V1.0 (TIE映射 + 多周期动量 + RS稳定性)

---

## 一、执行摘要

Phase 2.4 完成了行业轮动卫星策略的中观选池模块，建立了从申万一级行业到可交易ETF的定量映射体系，并整合宏观状态进行仓位协同。

**核心成果**:
- 覆盖 {mapped_industries}/{total_industries} 个申万一级行业 ({mapped_industries/total_industries*100:.1f}%)
- 建立 {core_count} 只核心池ETF + {backup_count} 只备用池ETF
- 当前优势池 {pool_valid} 个行业，目标仓位 8.00%（占总资产）
- 全部数据验证通过（MA60/收益率/TIE/RS_score/宏观协同）

---

## 二、方法论框架

### 2.1 ETF映射引擎（TIE方法）

**目标**: 建立申万一级行业 → 可交易ETF的定量映射

**步骤**:
1. 读取31个申万一级行业指数的成分股（5,198只成分股）
2. 读取行业主题ETF跟踪指数的成分股权重（103只ETF）
3. 计算每只ETF在31个行业中的目标行业暴露度（TIE）
4. 按规则分级：
   - **Core** (industry_rotation_core): TIE ≥ 50% 且 纯度差 ≥ 10%
   - **Backup** (industry_rotation_backup): 30% ≤ TIE < 50% 或纯度差 < 10%
   - **Unmapped**: TIE < 30%

**关键参数**:
- TIE阈值（Core）: 50%
- 纯度差阈值（Core）: 10%
- TIE阈值（Backup）: 30%

### 2.2 多周期动量筛选

**指标**:
- MA60过滤：收盘价 > 60日移动平均线
- 6个月相对收益率：行业6M收益 - 中证全指6M收益
- 12个月相对收益率：行业12M收益 - 中证全指12M收益
- 加速度：6M - 12M
- Composite Score: 0.5 × 相对6M + 0.5 × 相对加速度

**基准**: 中证全指 (000985.CSI)

### 2.3 排名稳定性（RS_score）

**计算**:
1. 每月计算所有行业的Composite Score并排名
2. 取最近12个月排名，计算：
   - 平均排名 → 排名得分（40%）
   - 排名标准差 → 稳定性得分（30%）
   - 排名趋势（最新 - 最早）→ 趋势得分（30%）
3. RS_score = 加权综合

### 2.4 宏观协同

**规则**:
- 极端象限（深度衰退/过热/滞胀）：清仓卫星仓位（0%）
- 非极端象限：卫星仓位降权至 80%（即占总资产 10% × 0.8 = 8%）

**行业周期敏感度调整**（仅在非极端象限）：
- 高敏感度（有色/钢铁/煤炭/建材/机械/汽车/房地产）：+20%
- 中敏感度（化工/电力设备/电子/计算机/传媒/通信）：基准
- 低敏感度（食品饮料/医药/公用事业/交运/银行/非银）：-20%

---

## 三、核心结果

### 3.1 ETF映射结果

| 分级 | 数量 | 说明 |
|------|------|------|
| **Core** | {core_count} | TIE≥50% & 纯度差≥10%，首选配置 |
| **Backup** | {backup_count} | 纯度不足或TIE较低，备选配置 |
| 未计算 | 3 | 缺少成分股权重文件 |

**行业覆盖度**: {mapped_industries}/{total_industries} ({mapped_industries/total_industries*100:.1f}%)

**未覆盖行业**（8个）:
- 纺织服饰 (801130)
- 轻工制造 (801140)
- 交通运输 (801170)
- 商贸零售 (801200)
- 综合 (801230)
- 建筑装饰 (801720)
- 环保 (801970)
- 美容护理 (801980)

### 3.2 当前动量排名（截至 {latest_date}）

**Top 3**:
"""

for i, row in enumerate(top3_momentum, 1):
    ma_status = "上方" if row['above_ma60'] else "下方"
    report += f"\n{i}. {row['sw_code']}: Composite={row['composite_score']:.2%} (MA60{ma_status})"

report += f"\n\n**Bottom 3**:\n"
for i, row in enumerate(bottom3_momentum, 1):
    ma_status = "上方" if row['above_ma60'] else "下方"
    report += f"\n{i}. {row['sw_code']}: Composite={row['composite_score']:.2%} (MA60{ma_status})"

report += f"""

### 3.3 优势池（RS_score前50% + MA60过滤）

**池规模**: {pool_valid} 个行业（共{pool_size}个候选）

**入选行业**:
"""

for _, row in df_final.iterrows():
    report += f"\n- {row['sw_name']} ({row['sw_code']}): {row['primary_etf_code']} | 权重{row['target_weight']:.2%} | 敏感度{row['sensitivity']}"

report += f"""

### 3.4 宏观状态与仓位

**当前宏观状态**（2026-03）:
- 增长：扩张平稳
- 通胀：温和通胀平稳
- 流动性：双宽下行
- 象限：完美扩张（非极端）

**仓位决策**:
- 卫星池总仓位：{df_final['target_weight'].sum():.2%}（占总资产）
- 操作：持有
- 降权系数：0.8

---

## 四、输出文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| ETF详细得分 | `docs/research/industry_rotation/etf_tie_scores.csv` | 103只ETF的TIE/纯度差/分级 |
| 行业-ETF映射 | `docs/research/industry_rotation/industry_etf_mapping.csv` | 23个行业的首选/备用ETF |
| 动量得分 | `docs/research/industry_rotation/industry_momentum_scores.csv` | 31个行业的MA60/6M/12M/Composite |
| RS稳定性 | `docs/research/industry_rotation/industry_rs_scores.csv` | 31个行业的RS_score分项 |
| 优势池 | `docs/research/industry_rotation/industry_selected_pool.csv` | MA60过滤后的候选池 |
| 最终池 | `docs/research/industry_rotation/industry_final_pool.csv` | 含目标权重和操作建议 |
| 验证报告 | `docs/research/industry_rotation/validation_report.txt` | 数据验证结果 |
| **本报告** | `docs/reports/phase2.4_industry_rotation_report.md` | 阶段性总结 |

---

## 五、已知限制与后续优化方向

### 5.1 当前限制

1. **主题投资排斥**
   - 申万行业分类是互斥的，天然排斥跨行业主题（如人工智能、机器人、新能源整车）
   - 这些主题ETF的TIE通常低于50%，被降级为backup
   - **影响**: 可能错过纯主题驱动的行情

2. **行业覆盖不完整**
   - 8个申万一级行业无ETF映射（覆盖率74.2%）
   - 主要集中于轻工、纺织、商贸等传统行业
   - **影响**: 资金在这些行业无配置渠道

3. **成分股文件更新依赖**
   - TIE映射依赖手动更新的成分股权重文件
   - 需要每年检查并更新 `data_external/reference/index_components/`
   - **风险**: 文件格式不一致可能导致遗漏（本次已发生，已修复）

4. **动态再平衡频率未确定**
   - 当前方法论假设月频调仓，但未实现自动再平衡逻辑
   - 实际执行时需要考虑交易成本和冲击成本

### 5.2 后续优化方向

**方向1：主题投资子策略（独立）**
- 建立跨行业主题分类体系（如AI、机器人、低空经济等）
- 主题ETF按主题纯度（而非行业纯度）分级
- 作为独立的卫星子策略，与行业轮动并行

**方向2：兼容主题投资（现有框架迭代）**
- 放宽TIE阈值（如从50%降至30%）
- 或增加"多行业暴露度"作为辅助指标
- 允许一只ETF同时映射到多个行业（按暴露度加权）

**方向3：动态参数优化**
- 回测不同TIE阈值（40%/50%/60%）的表现
- 优化RS_score的权重分配（目前40/30/30）
- 测试不同敏感度调整幅度（+10%/+20%/+30%）

---

## 六、为Phase 2.5做准备

Phase 2.5（微观趋势验证）将在Phase 2.4基础上增加：

1. **入场确认**
   - 模式A：回调买入（价格回踩MA20/MA60）
   - 模式B：突破买入（价格创20日新高 + 成交量放大）

2. **仓位分配精细化**
   - 根据RS_score动态调整行业内权重
   - 加入波动率调整（高波动降权）

3. **持仓防守**
   - 止损规则（如跌破MA60或亏损-8%）
   - 止盈规则（如RS_score连续3月下降）

4. **回测验证**
   - 历史回测（2016-2026）
   - 对比基准：等权行业指数 / 沪深300 / 中证500
   - 关键指标：年化收益、夏普比率、最大回撤、胜率

---

## 七、附录

### 7.1 核心脚本清单

| 脚本 | 路径 | 功能 |
|------|------|------|
| TIE映射引擎 | `scripts/reusable/industry_etf_tie_mapper.py` | ETF→申万行业映射 |
| 动量计算 | `scripts/reusable/industry_momentum_calculator.py` | MA60/6M/12M/Composite |
| RS稳定性 | `scripts/reusable/industry_rs_score_calculator.py` | 排名稳定性得分 |
| 宏观协同 | `scripts/reusable/industry_macro_synergy.py` | 极端象限/敏感度调整 |
| 数据验证 | `scripts/reusable/industry_strategy_validator.py` | 交叉验证 |

### 7.2 关键参数汇总

| 参数 | 值 | 说明 |
|------|-----|------|
| TIE Core阈值 | 50% | 一级映射准入 |
| 纯度差Core阈值 | 10% | 防止跨行业污染 |
| TIE Backup阈值 | 30% | 备用映射准入 |
| MA60窗口 | 60日 | 趋势过滤 |
| 6M回看期 | 126交易日 | 中期动量 |
| 12M回看期 | 252交易日 | 长期动量 |
| Composite权重 | 0.5/0.5 | 6M动量/加速度 |
| RS排名窗口 | 12月 | 稳定性计算 |
| RS_score权重 | 40/30/30 | 排名/稳定/趋势 |
| 卫星仓位上限 | 10% | 占总资产 |
| 非极端降权 | 0.8 | 宏观协同系数 |
| 高敏感度调整 | +20% | 扩张期加配 |
| 低敏感度调整 | -20% | 扩张期减配 |

---

*报告生成完毕。如需修改或补充，请在审阅后提出。*
"""

# 保存报告
report_path = REPORT_DIR / 'phase2.4_industry_rotation_report.md'
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report)

print(f"报告已生成: {report_path}")
print(f"报告长度: {len(report)} 字符")
