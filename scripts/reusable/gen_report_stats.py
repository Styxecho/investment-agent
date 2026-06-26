import pandas as pd
import numpy as np

# 读取数据
macro_df = pd.read_csv('docs/research/macro_analysis/macro_state_detail.csv')
macro_df['date'] = pd.to_datetime(macro_df['publish_date'], format='%Y%m%d')

returns_df = pd.read_csv('docs/research/macro_analysis/macro_state_asset_returns_detailed.csv')
returns_df['date'] = pd.to_datetime(returns_df['publish_date'])

def get_period_stats(start_year, end_year):
    """获取时期统计"""
    data = macro_df[(macro_df['date'].dt.year >= start_year) & (macro_df['date'].dt.year <= end_year)]
    ret = returns_df[(returns_df['date'].dt.year >= start_year) & (returns_df['date'].dt.year <= end_year)]
    
    stats = {}
    stats['months'] = len(data)
    stats['regimes'] = data['macro_regime'].value_counts().to_dict()
    
    # 资产表现
    for col in ['000300.SH_t1', '000905.SH_t1', 'CBA00651.CS_t1', 'NH0100.NHF_t1']:
        s = pd.to_numeric(ret[col], errors='coerce').dropna()
        if len(s) > 0:
            stats[col] = {
                'mean': s.mean() * 100,
                'win_rate': (s > 0).mean() * 100,
                'max': s.max() * 100,
                'min': s.min() * 100
            }
    
    return stats, data

# 生成各时期统计
periods = {
    '2016-2017': (2016, 2017),
    '2018-2019': (2018, 2019),
    '2021-2022': (2021, 2022),
    '2023-2024': (2023, 2024),
    '2025': (2025, 2025),
    '2026': (2026, 2026)
}

for name, (start, end) in periods.items():
    stats, data = get_period_stats(start, end)
    print(f"\n{'='*60}")
    print(f"{name} 统计")
    print(f"{'='*60}")
    print(f"总月数: {stats['months']}")
    print(f"象限分布: {stats['regimes']}")
    print("\n资产表现:")
    for asset, values in stats.items():
        if asset not in ['months', 'regimes']:
            print(f"  {asset}: 平均{values['mean']:.2f}%, 胜率{values['win_rate']:.1f}%, 最大{values['max']:.2f}%, 最小{values['min']:.2f}%")
