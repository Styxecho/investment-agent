"""
宏观状态-资产表现复盘分析脚本
可复用，支持任意宏观状态CSV与资产价格数据库

使用方法:
    python macro_state_asset_analysis.py
    
输出:
    1. 详细月度收益率CSV（含滞后1月/3月收益）
    2. 象限-资产表现统计报告（Markdown+可视化）
"""

import pandas as pd
import numpy as np
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def get_all_sector_codes(conn):
    """从数据库获取所有申万行业指数代码"""
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT index_code FROM index_daily WHERE index_code LIKE "801%.SI" ORDER BY index_code')
    return [row[0] for row in cursor.fetchall()]


def calc_monthly_returns(price_series):
    """
    计算月度收益率
    方法: 提取每月最后一个交易日的收盘价，计算 (本月末/上月末 - 1)
    
    改进: 只使用有真实数据的月末日期。如果某个月没有数据（如1月IAV缺失），
    则该月的月末价格为NaN，不计算该月的收益率
    """
    # 获取每月最后一条记录的日期和价格
    monthly_data = price_series.groupby(price_series.index.to_period('M')).agg(['last', 'count'])
    monthly_data.columns = ['close_price', 'count']
    
    # 如果某个月没有数据（count=0），设为NaN
    monthly_prices = monthly_data['close_price']
    monthly_prices.index = monthly_prices.index.to_timestamp('M')
    
    # 只保留有数据的价格
    monthly_prices = monthly_prices.dropna()
    
    # 计算月度收益率，要求上月和本月都有数据
    monthly_returns = monthly_prices.pct_change().dropna()
    
    return monthly_returns


def analyze_macro_state_assets(
    db_path,
    macro_csv,
    output_dir,
    assets_config=None,
    sector_map=None
):
    """
    宏观状态-资产表现分析主函数
    
    :param db_path: SQLite数据库路径
    :param macro_csv: 宏观状态CSV文件路径
    :param output_dir: 输出目录
    :param assets_config: 资产分类配置字典
    :param sector_map: 行业板块映射字典
    """
    
    # 默认资产配置
    if assets_config is None:
        assets_config = {
            '股票宽基': {
                '000300.SH': '沪深300',
                '000905.SH': '中证500', 
                '000852.SH': '中证1000',
                '932000.CSI': '中证2000',
                '399006.SZ': '创业板指',
                '000688.SH': '科创50',
            },
            '债券': {
                'CBA00621.CS': '国债1-3年',
                'CBA00651.CS': '国债7-10年',
                'CBA02701.CS': '信用债总值',
                'CBA00301.CS': '中债综合',
            },
            '商品': {
                'NH0100.NHF': '南华商品',
                'NH0200.NHF': '南华工业品',
                'AU.SHF': 'SHFE黄金',
            },
        }
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    
    # 自动获取所有申万行业指数
    all_sector_codes = get_all_sector_codes(conn)
    print(f"数据库中共有 {len(all_sector_codes)} 个申万行业指数")
    
    # 构建完整资产列表
    all_asset_codes = []
    for category in assets_config.values():
        all_asset_codes.extend(category.keys())
    all_asset_codes.extend(all_sector_codes)
    
    print(f"总共需要分析 {len(all_asset_codes)} 个资产")
    
    # 1. 读取宏观状态数据
    print("\n[1/6] 读取宏观状态数据...")
    macro_df = pd.read_csv(macro_csv)
    macro_df['publish_date'] = pd.to_datetime(macro_df['publish_date'], format='%Y%m%d')
    macro_df = macro_df.sort_values('publish_date').reset_index(drop=True)
    print(f"  宏观状态: {macro_df['publish_date'].min()} ~ {macro_df['publish_date'].max()}, {len(macro_df)}个月")
    
    # 2. 提取资产价格
    print("\n[2/6] 提取资产价格...")
    asset_prices = {}
    missing_assets = []
    
    for code in all_asset_codes:
        query = f"""
            SELECT trade_date, close_price 
            FROM index_daily 
            WHERE index_code = '{code}'
            ORDER BY trade_date
        """
        df = pd.read_sql(query, conn)
        
        if len(df) == 0:
            missing_assets.append(code)
            continue
        
        df['trade_date'] = pd.to_datetime(df['trade_date'].astype(str), format='mixed', dayfirst=False)
        df = df.set_index('trade_date')['close_price'].sort_index()
        asset_prices[code] = df
    
    if missing_assets:
        print(f"  警告: 以下资产无数据: {missing_assets}")
    
    print(f"  成功提取 {len(asset_prices)} 个资产")
    
    # 3. 计算月度收益率
    print("\n[3/6] 计算月度收益率...")
    asset_monthly_returns = {}
    for code, prices in asset_prices.items():
        returns = calc_monthly_returns(prices)
        if len(returns) > 0:
            asset_monthly_returns[code] = returns
    
    print(f"  成功计算 {len(asset_monthly_returns)} 个资产的月度收益率")
    
    # 4. 计算滞后收益
    print("\n[4/6] 计算滞后收益...")
    
    # 首先打印数据可用性报告
    print("\n  === 数据可用性检查 ===")
    data_availability = {}
    for code, returns in asset_monthly_returns.items():
        data_availability[code] = {
            'start_date': returns.index.min(),
            'end_date': returns.index.max(),
            'months': len(returns)
        }
        print(f"    {code}: {returns.index.min().strftime('%Y-%m')} ~ {returns.index.max().strftime('%Y-%m')} ({len(returns)}个月)")
    
    results = []
    
    for _, macro_row in macro_df.iterrows():
        date = macro_row['publish_date']
        
        record = {
            'publish_date': date.strftime('%Y-%m-%d'),
            'macro_regime': macro_row['macro_regime'],
            'growth_state': macro_row['growth_state'],
            'inflation_state': macro_row['inflation_state'],
            'liquidity_state': macro_row['liquidity_state'],
        }
        
        for code in all_asset_codes:
            if code not in asset_monthly_returns:
                record[f'{code}_t1'] = np.nan
                record[f'{code}_t3'] = np.nan
                continue
            
            returns = asset_monthly_returns[code]
            avail = data_availability[code]
            
            # 检查宏观状态日期是否在资产数据范围内
            # 要求：宏观状态日期 <= 资产最后日期，且下一个月的月末价格存在
            next_month = date + pd.DateOffset(months=1)
            next_month_end = next_month + pd.offsets.MonthEnd(0)
            
            # T+1月收益检查：需要下一个月有月末价格
            if next_month_end > avail['end_date'] or next_month_end < avail['start_date']:
                record[f'{code}_t1'] = np.nan
            else:
                # 查找下一个月的收益率
                future_returns = returns[returns.index >= next_month_end]
                if len(future_returns) >= 1:
                    record[f'{code}_t1'] = future_returns.iloc[0]
                else:
                    record[f'{code}_t1'] = np.nan
            
            # T+3月累计收益检查：需要接下来3个月都有月末价格
            third_month = date + pd.DateOffset(months=3)
            third_month_end = third_month + pd.offsets.MonthEnd(0)
            
            if third_month_end > avail['end_date'] or next_month_end < avail['start_date']:
                record[f'{code}_t3'] = np.nan
            else:
                # 获取接下来3个月的收益率
                future_returns = returns[returns.index >= next_month_end]
                if len(future_returns) >= 3:
                    cumulative_return = (1 + future_returns.iloc[:3]).prod() - 1
                    record[f'{code}_t3'] = cumulative_return
                else:
                    record[f'{code}_t3'] = np.nan
        
        results.append(record)
    
    detailed_df = pd.DataFrame(results)
    
    # 保存详细数据
    detailed_csv_path = f"{output_dir}/macro_state_asset_returns_detailed.csv"
    detailed_df.to_csv(detailed_csv_path, index=False, encoding='utf-8-sig')
    print(f"  已保存: {detailed_csv_path}")
    print(f"  包含 {len(detailed_df)} 个月 × {len([c for c in detailed_df.columns if '_t1' in c])} 个资产")
    
    # 5. 按象限统计
    print("\n[5/6] 按象限统计...")
    stat_results = []
    asset_cols_t1 = [c for c in detailed_df.columns if c.endswith('_t1')]
    asset_codes = [c.replace('_t1', '') for c in asset_cols_t1]
    
    for regime in detailed_df['macro_regime'].unique():
        regime_data = detailed_df[detailed_df['macro_regime'] == regime]
        
        for code in asset_codes:
            t1_col = f'{code}_t1'
            t3_col = f'{code}_t3'
            
            t1_returns = regime_data[t1_col].dropna()
            t3_returns = regime_data[t3_col].dropna()
            
            if len(t1_returns) == 0:
                continue
                
            # 获取资产名称和分类
            asset_name = None
            asset_category = None
            for cat_name, cat_assets in assets_config.items():
                if code in cat_assets:
                    asset_name = cat_assets[code]
                    asset_category = cat_name
                    break
            if not asset_name:
                asset_name = f"行业-{code}"
                asset_category = "行业"
            
            # T+1月统计
            stat_results.append({
                'macro_regime': regime,
                'asset_code': code,
                'asset_name': asset_name,
                'asset_category': asset_category,
                'lag': 'T+1M',
                'sample_size': len(t1_returns),
                'mean_return': t1_returns.mean(),
                'median_return': t1_returns.median(),
                'std_return': t1_returns.std(),
                'win_rate': (t1_returns > 0).mean(),
                'max_return': t1_returns.max(),
                'min_return': t1_returns.min(),
            })
            
            # T+3月统计
            if len(t3_returns) > 0:
                stat_results.append({
                    'macro_regime': regime,
                    'asset_code': code,
                    'asset_name': asset_name,
                    'asset_category': asset_category,
                    'lag': 'T+3M',
                    'sample_size': len(t3_returns),
                    'mean_return': t3_returns.mean(),
                    'median_return': t3_returns.median(),
                    'std_return': t3_returns.std(),
                    'win_rate': (t3_returns > 0).mean(),
                    'max_return': t3_returns.max(),
                    'min_return': t3_returns.min(),
                })
    
    stats_df = pd.DataFrame(stat_results)
    
    # 保存统计数据
    stats_csv_path = f"{output_dir}/macro_state_asset_stats.csv"
    stats_df.to_csv(stats_csv_path, index=False, encoding='utf-8-sig')
    print(f"  已保存: {stats_csv_path}")
    
    # 6. 生成热力图
    print("\n[6/6] 生成可视化...")
    for lag in ['T+1M', 'T+3M']:
        lag_stats = stats_df[stats_df['lag'] == lag].copy()
        main_assets = lag_stats[lag_stats['asset_category'].isin(['股票宽基', '债券', '商品'])]
        
        if len(main_assets) == 0:
            continue
        
        pivot_mean = main_assets.pivot(index='asset_name', columns='macro_regime', values='mean_return')
        
        fig, ax = plt.subplots(figsize=(14, 8))
        sns.heatmap(pivot_mean, annot=True, fmt='.2%', cmap='RdYlGn', center=0, 
                    ax=ax, cbar_kws={'label': '平均收益率'})
        ax.set_title(f'宏观象限-资产表现矩阵 ({lag})', fontsize=16, pad=20)
        ax.set_xlabel('宏观象限', fontsize=12)
        ax.set_ylabel('资产', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        heatmap_path = f"{output_dir}/heatmap_main_assets_{lag}.png"
        plt.savefig(heatmap_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  已保存: {heatmap_path}")
    
    conn.close()
    print("\n分析完成!")
    return detailed_df, stats_df


if __name__ == '__main__':
    DB_PATH = r'D:\Study\Project\investment-agent\data_external\db\external_data.db'
    MACRO_CSV = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_detail.csv'
    OUTPUT_DIR = r'D:\Study\Project\investment-agent\docs\research\macro_analysis'
    
    analyze_macro_state_assets(DB_PATH, MACRO_CSV, OUTPUT_DIR)
