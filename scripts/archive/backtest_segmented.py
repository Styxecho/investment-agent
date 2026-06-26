"""
分段回测分析：验证低波动异象在不同市场环境下的稳健性

分段方案：
1. 2019-2021: 疫情前后（震荡+复苏）
2. 2022-2023: 加息熊市（股债双杀）  
3. 2024-2026: 震荡下行（红利占优）
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from skills.portfolio.backtest.engine import BacktestEngine
from skills.portfolio.backtest.schema import BacktestRequest, BacktestAsset
from datetime import datetime
import pandas as pd
import json

# 组合 A：多元化（13只）
PORTFOLIO_A = [
    {"code": "510300.SH", "name": "沪深300ETF华泰柏瑞"},
    {"code": "510500.SH", "name": "中证500ETF南方"},
    {"code": "512100.SH", "name": "中证1000ETF南方"},
    {"code": "159531.SZ", "name": "中证2000ETF南方"},
    {"code": "588000.SH", "name": "科创50ETF华夏"},
    {"code": "159920.SZ", "name": "恒生ETF华夏"},
    {"code": "513010.SH", "name": "恒生科技ETF易方达"},
    {"code": "513100.SH", "name": "纳指ETF国泰"},
    {"code": "513500.SH", "name": "标普500ETF博时"},
    {"code": "518880.SH", "name": "黄金ETF华安"},
    {"code": "511260.SH", "name": "十年国债ETF国泰"},
    {"code": "159972.SZ", "name": "5年地方债ETF鹏华"},
    {"code": "511360.SH", "name": "短融ETF海富通"},
]

# 组合 B：低波动（10只）
PORTFOLIO_B = [
    {"code": "510880.SH", "name": "红利ETF华泰柏瑞"},
    {"code": "512890.SH", "name": "红利低波ETF华泰柏瑞"},
    {"code": "159201.SZ", "name": "自由现金流ETF华夏"},
    {"code": "561580.SH", "name": "央企红利ETF华泰柏瑞"},
    {"code": "513920.SH", "name": "港股通央企红利ETF华安"},
    {"code": "159545.SZ", "name": "恒生红利低波ETF易方达"},
    {"code": "511260.SH", "name": "十年国债ETF国泰"},
    {"code": "159972.SZ", "name": "5年地方债ETF鹏华"},
    {"code": "511360.SH", "name": "短融ETF海富通"},
    {"code": "518880.SH", "name": "黄金ETF华安"},
]

# 分段定义
SEGMENTS = [
    {"name": "2019-2021: 疫情前后", "start": "20190401", "end": "20211231"},
    {"name": "2022-2023: 加息熊市", "start": "20220104", "end": "20231229"},
    {"name": "2024-2026: 震荡下行", "start": "20240102", "end": "20260417"},
]


def run_segment_backtest(portfolio, portfolio_name, segment):
    """执行单分段回测"""
    print(f"\n{'='*60}")
    print(f"回测区间: {segment['name']}")
    print(f"组合: {portfolio_name}")
    print(f"{'='*60}")
    
    assets = [BacktestAsset(code=a["code"]) for a in portfolio]
    
    request = BacktestRequest(
        assets=assets,
        start_date=segment["start"],
        end_date=segment["end"],
        method="risk_parity",
        rebalance_freq="monthly",
        lookback_days=60,
        initial_nav=1.0,
    )
    
    engine = BacktestEngine()
    result = engine.run(request)
    
    if result.error_message:
        print(f"回测失败: {result.error_message}")
        return None
    
    print(f"交易日数: {len(result.daily_records)}")
    print(f"再平衡次数: {len(result.rebalance_events)}")
    print(f"\n绩效指标:")
    print(f"  累计收益率: {result.metrics.cumulative_return:.2%}")
    print(f"  年化收益率: {result.metrics.annualized_return:.2%}")
    print(f"  年化波动率: {result.metrics.annualized_volatility:.2%}")
    print(f"  最大回撤: {result.metrics.max_drawdown:.2%}")
    print(f"  夏普比率: {result.metrics.sharpe_ratio:.4f}")
    print(f"  卡玛比率: {result.metrics.calmar_ratio:.4f}")
    print(f"  月度胜率: {result.metrics.win_rate_monthly:.2%}")
    
    return result


def generate_segmented_report(results, output_path="docs/research/backtest_segmented_report.md"):
    """生成分段回测对比报告"""
    
    report = """# 分段回测分析报告

## 实验设计

**目标**: 验证低波动策略是否在不同宏观环境下均优于多元化策略，还是仅在特定时期（如加息熊市）表现优异。

**分段方案**:
1. **2019-2021**: 疫情前后（贸易战尾声 + 疫情冲击 + 后疫情复苏）
2. **2022-2023**: 加息熊市（美联储激进加息 + 全球股债双杀）
3. **2024-2026**: 震荡下行（降息预期 + 红利策略持续占优）

**组合配置**:
- 组合 A：多元化分散（13只ETF，涵盖宽基、策略、债券、商品）
- 组合 B：低波动集中（10只ETF，以红利策略 + 债券为主）

**方法论**: 月度再平衡，风险平价，60日滚动协方差，支持指数替代和费率扣除。

## 分段结果对比

"""
    
    for i, segment in enumerate(SEGMENTS):
        seg_name = segment["name"]
        result_a = results[i]["A"]
        result_b = results[i]["B"]
        
        if result_a is None or result_b is None:
            report += f"\n### {seg_name}\n\n回测失败，数据不足。\n\n"
            continue
        
        report += f"""### {seg_name}

| 指标 | 组合 A（多元化） | 组合 B（低波动） | 差异 |
|------|-----------------|-----------------|------|
| 累计收益率 | {result_a.metrics.cumulative_return:.2%} | {result_b.metrics.cumulative_return:.2%} | {result_b.metrics.cumulative_return - result_a.metrics.cumulative_return:+.2%} |
| 年化收益率 | {result_a.metrics.annualized_return:.2%} | {result_b.metrics.annualized_return:.2%} | {result_b.metrics.annualized_return - result_a.metrics.annualized_return:+.2%} |
| 年化波动率 | {result_a.metrics.annualized_volatility:.2%} | {result_b.metrics.annualized_volatility:.2%} | {result_b.metrics.annualized_volatility - result_a.metrics.annualized_volatility:+.2%} |
| 最大回撤 | {result_a.metrics.max_drawdown:.2%} | {result_b.metrics.max_drawdown:.2%} | {abs(result_b.metrics.max_drawdown) - abs(result_a.metrics.max_drawdown):+.2%} |
| 夏普比率 | {result_a.metrics.sharpe_ratio:.4f} | {result_b.metrics.sharpe_ratio:.4f} | {result_b.metrics.sharpe_ratio - result_a.metrics.sharpe_ratio:+.4f} |
| 卡玛比率 | {result_a.metrics.calmar_ratio:.4f} | {result_b.metrics.calmar_ratio:.4f} | {result_b.metrics.calmar_ratio - result_a.metrics.calmar_ratio:+.4f} |
| 月度胜率 | {result_a.metrics.win_rate_monthly:.2%} | {result_b.metrics.win_rate_monthly:.2%} | {result_b.metrics.win_rate_monthly - result_a.metrics.win_rate_monthly:+.2%} |

**关键发现**:
- {"**组合 B 显著占优**" if result_b.metrics.sharpe_ratio > result_a.metrics.sharpe_ratio else "**组合 A 更优**" if result_a.metrics.sharpe_ratio > result_b.metrics.sharpe_ratio else "**两者接近**"}
- 收益差异: {result_b.metrics.annualized_return - result_a.metrics.annualized_return:+.2%}
- 回撤控制: 组合 B 最大回撤 {result_b.metrics.max_drawdown:.2%} vs 组合 A {result_a.metrics.max_drawdown:.2%}

"""
    
    # 汇总分析
    report += """## 综合分析

### 低波动异象的稳健性

"""
    
    # 统计各分段中哪个组合更优
    sharpe_winners = []
    return_winners = []
    
    for i in range(len(SEGMENTS)):
        result_a = results[i]["A"]
        result_b = results[i]["B"]
        if result_a and result_b:
            sharpe_winners.append("B" if result_b.metrics.sharpe_ratio > result_a.metrics.sharpe_ratio else "A")
            return_winners.append("B" if result_b.metrics.annualized_return > result_a.metrics.annualized_return else "A")
    
    b_sharpe_wins = sharpe_winners.count("B")
    b_return_wins = return_winners.count("B")
    
    report += f"""- **夏普比率**: 组合 B 在 {b_sharpe_wins}/{len(sharpe_winners)} 个分段中占优
- **年化收益**: 组合 B 在 {b_return_wins}/{len(return_winners)} 个分段中占优

### 市场环境的影响

"""
    
    if b_sharpe_wins >= 2:
        report += """结果表明，**低波动策略在大多数市场环境下均表现更优**，不仅仅是加息熊市或下行周期的产物。

"""
    else:
        report += """结果表明，低波动策略的优势**主要集中在特定市场环境**（如加息周期或下行趋势），在普涨行情中可能跑输多元化策略。

"""
    
    # 各分段具体分析
    for i in range(len(SEGMENTS)):
        result_a = results[i]["A"]
        result_b = results[i]["B"]
        if result_a and result_b:
            seg_name = SEGMENTS[i]["name"]
            report += f"**{seg_name}**: "
            if result_b.metrics.sharpe_ratio > result_a.metrics.sharpe_ratio:
                report += f"组合 B 占优（夏普 {result_b.metrics.sharpe_ratio:.2f} vs {result_a.metrics.sharpe_ratio:.2f}）"
            else:
                report += f"组合 A 占优（夏普 {result_a.metrics.sharpe_ratio:.2f} vs {result_b.metrics.sharpe_ratio:.2f}）"
            report += f"，收益差 {result_b.metrics.annualized_return - result_a.metrics.annualized_return:+.2%}\n\n"
    
    report += f"""## 结论

"""
    
    if b_sharpe_wins == len(SEGMENTS):
        report += """**低波动策略在测试的所有市场环境中均表现出更优的风险调整后收益**，支持将其作为核心配置的结论。"""
    elif b_sharpe_wins >= len(SEGMENTS) // 2 + 1:
        report += """**低波动策略在多数市场环境中占优**，但在普涨行情中可能跑输。建议根据宏观环境动态调整权重。"""
    else:
        report += """**低波动策略的优势并不稳健**，仅在特定市场环境（如加息周期）中显著。多元化策略在牛市中可能更优。"""
    
    report += f"""

---
*报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
    
    # 保存报告
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n报告已保存: {output_path}")
    return report


if __name__ == "__main__":
    print("="*60)
    print("分段回测分析")
    print("="*60)
    
    all_results = []
    
    for segment in SEGMENTS:
        print(f"\n{'#'*60}")
        print(f"# 开始: {segment['name']}")
        print(f"{'#'*60}")
        
        result_a = run_segment_backtest(PORTFOLIO_A, "组合 A（多元化）", segment)
        result_b = run_segment_backtest(PORTFOLIO_B, "组合 B（低波动）", segment)
        
        all_results.append({"A": result_a, "B": result_b})
    
    # 生成综合报告
    print(f"\n{'='*60}")
    print("生成综合分析报告...")
    print(f"{'='*60}")
    
    generate_segmented_report(all_results)
    
    print("\n" + "="*60)
    print("分段回测完成！")
    print("="*60)
