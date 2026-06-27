# scripts/reusable/run_industry_rotation_backtest.py
"""
Phase 2.5 行业轮动卫星策略回测入口脚本

用法：
    python scripts/reusable/run_industry_rotation_backtest.py
    python scripts/reusable/run_industry_rotation_backtest.py --config config/industry_rotation.yaml

输出：
    output/industry_rotation_backtest/
        - daily_nav.csv
        - trades.csv
        - rebalances.csv
        - metrics.json
        - backtest_report.md
        - nav_curve.png
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import yaml

from skills.industry_rotation.backtest_engine import (
    IndustryRotationBacktestEngine,
    BacktestConfig,
    MicroConfig,
    RiskConfig
)


def load_config(path: str) -> BacktestConfig:
    """从 YAML 加载回测配置"""
    with open(path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    
    micro = MicroConfig(**raw.get('micro', {}))
    risk = RiskConfig(**raw.get('risk', {}))
    
    return BacktestConfig(
        start_date=raw.get('start_date', '20150101'),
        end_date=raw.get('end_date', '20260624'),
        asset_allocation=raw.get('asset_allocation', {'equity': 50.0, 'bond': 40.0, 'commodity': 10.0}),
        satellite_ratio_in_equity=raw.get('satellite_ratio_in_equity', 0.10),
        transaction_cost=raw.get('transaction_cost', 0.001),
        initial_nav=raw.get('initial_nav', 1.0),
        micro_config=micro,
        risk_config=risk,
        use_etf_mapping=raw.get('use_etf_mapping', False),
        output_dir=raw.get('output_dir', 'output/industry_rotation_backtest')
    )


def main():
    parser = argparse.ArgumentParser(description='Phase 2.5 行业轮动卫星策略回测')
    parser.add_argument(
        '--config',
        type=str,
        default='config/industry_rotation.yaml',
        help='配置文件路径'
    )
    args = parser.parse_args()
    
    config = load_config(args.config)
    
    engine = IndustryRotationBacktestEngine(config)
    result = engine.run()
    
    if result['success']:
        print("\n=== 回测完成 ===")
        print("策略绩效:")
        for k, v in result['metrics']['strategy'].items():
            print(f"  {k}: {v}")
        print("\n基准对比:")
        for bench, metrics in result['metrics']['benchmarks'].items():
            print(f"\n  {bench}:")
            for k, v in metrics.items():
                print(f"    {k}: {v}")
        print(f"\n输出文件: {result['output_paths']}")
    else:
        print(f"回测失败: {result.get('error')}")
        return 1
    
    return 0


if __name__ == '__main__':
    main()
