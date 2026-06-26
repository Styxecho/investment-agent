"""
组合 C（A ∪ B 去重）回测
测试全局风险平价 vs 分开优化的效果
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

# 组合 A 资产
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

# 组合 B 资产
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

# 组合 C：A ∪ B 去重
# 使用字典去重，保持第一次出现的顺序
PORTFOLIO_C_DICT = {}
for asset in PORTFOLIO_A + PORTFOLIO_B:
    if asset["code"] not in PORTFOLIO_C_DICT:
        PORTFOLIO_C_DICT[asset["code"]] = asset
PORTFOLIO_C = list(PORTFOLIO_C_DICT.values())

print("=" * 60)
print("组合C（A ∪ B 去重）资产列表")
print("=" * 60)
for i, asset in enumerate(PORTFOLIO_C, 1):
    in_a = "[A]" if asset["code"] in [a["code"] for a in PORTFOLIO_A] else "   "
    in_b = "[B]" if asset["code"] in [a["code"] for a in PORTFOLIO_B] else "   "
    print(f"{i:2d}. {asset['code']} {asset['name']} {in_a} {in_b}")

print(f"\n组合A: {len(PORTFOLIO_A)} 只")
print(f"组合B: {len(PORTFOLIO_B)} 只")
print(f"组合C（去重）: {len(PORTFOLIO_C)} 只")
print(f"重复资产: {len(PORTFOLIO_A) + len(PORTFOLIO_B) - len(PORTFOLIO_C)} 只")


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
    
    # 导出结果
    export_paths = result.export_results(
        output_dir="data_runtime/backtest",
        portfolio_name=portfolio_name.replace("（", "_").replace("）", "").replace(" ", "_")
    )
    print(f"\n导出文件:")
    for key, path in export_paths.items():
        print(f"  - {key}: {path}")
    
    return result


def compare_weights(result_a, result_b, result_c):
    """对比三个组合的典型权重分配"""
    print("\n" + "="*60)
    print("典型权重分配对比（第一个非零权重日）")
    print("="*60)
    
    for result, name in [(result_a, "A"), (result_b, "B"), (result_c, "C")]:
        if result and result.rebalance_events:
            event = result.rebalance_events[0]
            print(f"\n组合 {name} @ {event.trade_date}:")
            
            # 按类别分组
            stocks = []
            bonds = []
            others = []
            
            for code, weight in sorted(event.target_weights.items(), key=lambda x: -x[1]):
                if weight < 0.001:
                    continue
                if code in ['511260.SH', '159972.SZ']:
                    bonds.append((code, weight))
                elif code == '511360.SH':
                    bonds.append((code, weight))  # 现金替代
                else:
                    stocks.append((code, weight))
            
            print(f"  债券类 ({len(bonds)}只):", end="")
            bond_sum = sum(w for _, w in bonds)
            print(f" 合计={bond_sum:.2%}")
            for code, w in bonds[:5]:
                print(f"    {code}: {w:.2%}")
            
            print(f"  权益类 ({len(stocks)}只):", end="")
            stock_sum = sum(w for _, w in stocks)
            print(f" 合计={stock_sum:.2%}")
            for code, w in stocks[:8]:
                print(f"    {code}: {w:.2%}")


def generate_comparison_report(result_a, result_b, result_c, output_path="docs/research/backtest_combined_comparison.md"):
    """生成组合对比报告"""
    
    # 获取净值序列
    nav_data = {}
    for result, name in [(result_a, "A"), (result_b, "B"), (result_c, "C")]:
        if result:
            nav_data[name] = pd.Series(
                [r.nav for r in result.daily_records],
                index=pd.to_datetime([r.trade_date for r in result.daily_records])
            )
    
    report = f"""# 组合A/B/C 全面对比报告

## 组合配置

### 组合 A（多元化，{len(PORTFOLIO_A)}只ETF）
{"".join([f"- {a['code']} {a['name']}" for a in PORTFOLIO_A])}

### 组合 B（低波动，{len(PORTFOLIO_B)}只ETF）
{"".join([f"- {a['code']} {a['name']}" for a in PORTFOLIO_B])}

### 组合 C（A∪B去重，{len(PORTFOLIO_C)}只ETF）
{"".join([f"- {a['code']} {a['name']}" for a in PORTFOLIO_C])}

## 绩效对比

| 指标 | 组合 A（多元化） | 组合 B（低波动） | 组合 C（合并） |
|------|-----------------|-----------------|---------------|
| 累计收益率 | {result_a.metrics.cumulative_return:.2%} | {result_b.metrics.cumulative_return:.2%} | {result_c.metrics.cumulative_return:.2%} |
| 年化收益率 | {result_a.metrics.annualized_return:.2%} | {result_b.metrics.annualized_return:.2%} | {result_c.metrics.annualized_return:.2%} |
| 年化波动率 | {result_a.metrics.annualized_volatility:.2%} | {result_b.metrics.annualized_volatility:.2%} | {result_c.metrics.annualized_volatility:.2%} |
| 最大回撤 | {result_a.metrics.max_drawdown:.2%} | {result_b.metrics.max_drawdown:.2%} | {result_c.metrics.max_drawdown:.2%} |
| 夏普比率 | {result_a.metrics.sharpe_ratio:.4f} | {result_b.metrics.sharpe_ratio:.4f} | {result_c.metrics.sharpe_ratio:.4f} |
| 卡玛比率 | {result_a.metrics.calmar_ratio:.4f} | {result_b.metrics.calmar_ratio:.4f} | {result_c.metrics.calmar_ratio:.4f} |
| 索提诺比率 | {result_a.metrics.sortino_ratio:.4f} | {result_b.metrics.sortino_ratio:.4f} | {result_c.metrics.sortino_ratio:.4f} |
| 月度胜率 | {result_a.metrics.win_rate_monthly:.2%} | {result_b.metrics.win_rate_monthly:.2%} | {result_c.metrics.win_rate_monthly:.2%} |
| 年化换手率 | {result_a.metrics.annualized_turnover:.2%} | {result_b.metrics.annualized_turnover:.2%} | {result_c.metrics.annualized_turnover:.2%} |

## 关键发现

1. **收益表现**: 组合 C 累计收益 {result_c.metrics.cumulative_return:.2%} vs 组合 A {result_a.metrics.cumulative_return:.2%} vs 组合 B {result_b.metrics.cumulative_return:.2%}
2. **风险调整后收益**: 组合 C 夏普比率 {result_c.metrics.sharpe_ratio:.4f} vs 组合 A {result_a.metrics.sharpe_ratio:.4f} vs 组合 B {result_b.metrics.sharpe_ratio:.4f}
3. **回撤控制**: 组合 C 最大回撤 {result_c.metrics.max_drawdown:.2%} vs 组合 A {result_a.metrics.max_drawdown:.2%} vs 组合 B {result_b.metrics.max_drawdown:.2%}
4. **换手率**: 组合 C 年化换手率 {result_c.metrics.annualized_turnover:.2%} vs 组合 A {result_a.metrics.annualized_turnover:.2%} vs 组合 B {result_b.metrics.annualized_turnover:.2%}

## 理论分析

### 全局优化 vs 分开优化

- **组合A和B分开优化**：各自在子空间内寻找风险平价最优解，可能错过全局最优
- **组合C全局优化**：在更大的资产空间内搜索，理论上应该找到更好的风险-收益平衡

### 预期 vs 实际

{"**实际结果验证了理论预期**" if result_c.metrics.sharpe_ratio > max(result_a.metrics.sharpe_ratio, result_b.metrics.sharpe_ratio) else "**实际结果未达预期**"}：

- 组合C的夏普比率 {'>' if result_c.metrics.sharpe_ratio > result_a.metrics.sharpe_ratio else '<'} 组合A
- 组合C的夏普比率 {'>' if result_c.metrics.sharpe_ratio > result_b.metrics.sharpe_ratio else '<'} 组合B

### 可能原因

1. **资产冗余**：A和B有大量重叠资产（债券、黄金），合并后债券类资产过多
2. **风格冲突**：成长型（纳指、科创）和红利型在同一个组合中互相稀释
3. **样本外偏差**：回测区间恰好不利于某种风格的暴露

## 结论

"""
    
    if result_c.metrics.sharpe_ratio > max(result_a.metrics.sharpe_ratio, result_b.metrics.sharpe_ratio):
        report += """**全局风险平价（组合C）确实优于分开优化**，支持将A和B合并为一个更大的资产池进行统一配置。

优势：
- 更灵活的资产配置空间
- 自动化的风格切换（牛市配成长、熊市配红利）
- 更高的风险调整后收益
"""
    elif result_c.metrics.sharpe_ratio > min(result_a.metrics.sharpe_ratio, result_b.metrics.sharpe_ratio):
        report += """**全局风险平价（组合C）表现介于A和B之间**，说明合并有一定价值但未达最优。

建议：
- 组合C可以作为"中间路线"，兼具A的收益弹性和B的防御性
- 但仍需根据市场环境动态调整风格暴露
"""
    else:
        report += """**全局风险平价（组合C）未优于分开优化**，可能因为：

1. 资产冗余导致债券集中度过高
2. 风格冲突导致"平均化"陷阱
3. 回测区间不利于全局配置

建议：
- 保持A和B分开配置
- 或精简C的资产池，去除冗余债券资产
- 或采用核心-卫星策略，而非简单合并
"""
    
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
    print("\n开始回测对比...")
    print("=" * 60)
    
    # 执行回测
    result_a = run_backtest(PORTFOLIO_A, "组合 A（多元化）")
    result_b = run_backtest(PORTFOLIO_B, "组合 B（低波动）")
    result_c = run_backtest(PORTFOLIO_C, "组合 C（A∪B合并）")
    
    if result_a and result_b and result_c:
        # 对比权重分配
        compare_weights(result_a, result_b, result_c)
        
        # 生成对比报告
        print("\n生成对比报告...")
        generate_comparison_report(result_a, result_b, result_c)
        
        print("\n" + "=" * 60)
        print("回测完成！")
        print("=" * 60)
    else:
        print("\n部分回测失败，请检查数据")
