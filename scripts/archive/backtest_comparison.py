# backtest_comparison.py
"""
组合 A vs 组合 B 回测对照实验
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from skills.portfolio.backtest.engine import BacktestEngine
from skills.portfolio.backtest.schema import BacktestRequest, BacktestAsset
from datetime import datetime
import pandas as pd

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

def run_backtest(portfolio, portfolio_name, start_date="20190401", end_date="20260417"):
    """执行单组合回测"""
    print(f"\n{'='*60}")
    print(f"回测: {portfolio_name}")
    print(f"{'='*60}")
    
    assets = [BacktestAsset(code=a["code"]) for a in portfolio]
    
    request = BacktestRequest(
        assets=assets,
        start_date=start_date,
        end_date=end_date,
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
    
    print(f"回测区间: {start_date} ~ {end_date}")
    print(f"交易日数: {len(result.daily_records)}")
    print(f"再平衡次数: {len(result.rebalance_events)}")
    print(f"\n绩效指标:")
    print(f"  累计收益率: {result.metrics.cumulative_return:.2%}")
    print(f"  年化收益率: {result.metrics.annualized_return:.2%}")
    print(f"  年化波动率: {result.metrics.annualized_volatility:.2%}")
    print(f"  最大回撤: {result.metrics.max_drawdown:.2%}")
    print(f"  夏普比率: {result.metrics.sharpe_ratio:.4f}")
    print(f"  卡玛比率: {result.metrics.calmar_ratio:.4f}")
    print(f"  索提诺比率: {result.metrics.sortino_ratio:.4f}")
    print(f"  月度胜率: {result.metrics.win_rate_monthly:.2%}")
    print(f"  年化换手率: {result.metrics.annualized_turnover:.2%}")
    
    # 导出三样标准结果
    export_paths = result.export_results(
        output_dir="data_runtime/backtest",
        portfolio_name=portfolio_name.replace("（", "_").replace("）", "").replace(" ", "_")
    )
    print(f"\n导出文件:")
    for key, path in export_paths.items():
        print(f"  - {key}: {path}")
    
    return result

def generate_report(result_a, result_b, output_path="docs/research/backtest_report.md"):
    """生成回测对比报告"""
    
    # 生成净值对比数据
    nav_a = pd.Series(
        [r.nav for r in result_a.daily_records],
        index=pd.to_datetime([r.trade_date for r in result_a.daily_records])
    )
    nav_b = pd.Series(
        [r.nav for r in result_b.daily_records],
        index=pd.to_datetime([r.trade_date for r in result_b.daily_records])
    )
    
    # 对齐日期
    common_dates = nav_a.index.intersection(nav_b.index)
    nav_a = nav_a.loc[common_dates]
    nav_b = nav_b.loc[common_dates]
    
    # 计算相对表现
    relative = nav_a / nav_b
    
    report = f"""# 组合回测对照实验报告

## 实验设计

**回测区间**: 2019-04-01 ~ 2026-04-17
**再平衡策略**: 月度再平衡（风险平价）
**协方差估计**: 滚动 60 交易日
**指数替代**: ETF上市前使用全收益指数数据，按比例缩放，扣除ETF费率

### 组合 A（多元化分散，13只）

{chr(10).join([f"- {a['code']} {a['name']}" for a in PORTFOLIO_A])}

### 组合 B（低波动集中，10只）

{chr(10).join([f"- {a['code']} {a['name']}" for a in PORTFOLIO_B])}

## 绩效对比

| 指标 | 组合 A（多元化） | 组合 B（低波动） |
|------|-----------------|-----------------|
| 累计收益率 | {result_a.metrics.cumulative_return:.2%} | {result_b.metrics.cumulative_return:.2%} |
| 年化收益率 | {result_a.metrics.annualized_return:.2%} | {result_b.metrics.annualized_return:.2%} |
| 年化波动率 | {result_a.metrics.annualized_volatility:.2%} | {result_b.metrics.annualized_volatility:.2%} |
| 最大回撤 | {result_a.metrics.max_drawdown:.2%} | {result_b.metrics.max_drawdown:.2%} |
| 夏普比率 | {result_a.metrics.sharpe_ratio:.4f} | {result_b.metrics.sharpe_ratio:.4f} |
| 卡玛比率 | {result_a.metrics.calmar_ratio:.4f} | {result_b.metrics.calmar_ratio:.4f} |
| 索提诺比率 | {result_a.metrics.sortino_ratio:.4f} | {result_b.metrics.sortino_ratio:.4f} |
| 月度胜率 | {result_a.metrics.win_rate_monthly:.2%} | {result_b.metrics.win_rate_monthly:.2%} |
| 年化换手率 | {result_a.metrics.annualized_turnover:.2%} | {result_b.metrics.annualized_turnover:.2%} |

## 关键发现

1. **收益表现**: 组合 A 累计收益 {result_a.metrics.cumulative_return:.2%} vs 组合 B {result_b.metrics.cumulative_return:.2%}
2. **风险特征**: 组合 A 波动率 {result_a.metrics.annualized_volatility:.2%} vs 组合 B {result_b.metrics.annualized_volatility:.2%}
3. **风险调整后收益**: 组合 A 夏普比率 {result_a.metrics.sharpe_ratio:.4f} vs 组合 B {result_b.metrics.sharpe_ratio:.4f}
4. **回撤控制**: 组合 A 最大回撤 {result_a.metrics.max_drawdown:.2%} vs 组合 B {result_b.metrics.max_drawdown:.2%}

## 结论

"""
    
    # 根据结果生成结论
    if result_a.metrics.sharpe_ratio > result_b.metrics.sharpe_ratio:
        report += f"从风险调整后收益（夏普比率）来看，**组合 A（多元化）表现更优**（{result_a.metrics.sharpe_ratio:.4f} vs {result_b.metrics.sharpe_ratio:.4f}）。\n\n"
    else:
        report += f"从风险调整后收益（夏普比率）来看，**组合 B（低波动）表现更优**（{result_b.metrics.sharpe_ratio:.4f} vs {result_a.metrics.sharpe_ratio:.4f}）。\n\n"
    
    if abs(result_a.metrics.max_drawdown) < abs(result_b.metrics.max_drawdown):
        report += f"从回撤控制来看，**组合 A（多元化）表现更好**，最大回撤 {result_a.metrics.max_drawdown:.2%} 小于组合 B 的 {result_b.metrics.max_drawdown:.2%}。\n\n"
    else:
        report += f"从回撤控制来看，**组合 B（低波动）表现更好**，最大回撤 {result_b.metrics.max_drawdown:.2%} 小于组合 A 的 {result_a.metrics.max_drawdown:.2%}。\n\n"
    
    if result_a.metrics.cumulative_return > result_b.metrics.cumulative_return:
        report += f"从绝对收益来看，**组合 A（多元化）累计收益更高**（{result_a.metrics.cumulative_return:.2%} vs {result_b.metrics.cumulative_return:.2%}）。\n"
    else:
        report += f"从绝对收益来看，**组合 B（低波动）累计收益更高**（{result_b.metrics.cumulative_return:.2%} vs {result_a.metrics.cumulative_return:.2%}）。\n"
    
    report += """
## 净值走势

```
净值对比（归一化到 1.0）:
"""
    
    # 添加净值走势文本图
    n_points = min(60, len(common_dates))
    step = len(common_dates) // n_points if len(common_dates) > n_points else 1
    
    for i in range(0, len(common_dates), step):
        date = common_dates[i]
        v_a = nav_a.iloc[i]
        v_b = nav_b.iloc[i]
        bar_a = "█" * int(v_a * 20)
        bar_b = "░" * int(v_b * 20)
        report += f"{date.strftime('%Y-%m-%d')} A: {bar_a:<20} ({v_a:.3f}) B: {bar_b:<20} ({v_b:.3f})\n"
    
    report += """```

---
*报告生成时间: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """*
"""
    
    # 保存报告
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n报告已保存: {output_path}")
    return report

if __name__ == "__main__":
    print("开始回测对照实验...")
    
    # 执行回测
    result_a = run_backtest(PORTFOLIO_A, "组合 A（多元化）")
    result_b = run_backtest(PORTFOLIO_B, "组合 B（低波动）")
    
    if result_a and result_b:
        # 生成报告
        report = generate_report(result_a, result_b)
        print("\n" + "="*60)
        print("回测完成！")
        print("="*60)
    else:
        print("\n回测失败，请检查数据")
