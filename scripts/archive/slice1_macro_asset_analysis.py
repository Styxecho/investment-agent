#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
切片1复盘：宏观因子与资产表现结合分析
时间范围：2016-2017
逻辑：当月宏观数据 → 次月资产收益（滞后1月）
"""
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from utils.trade_calendar import TradeCalendarService
from utils.returns_calculator import calculate_period_return

engine = create_engine('sqlite:///D:/Study/Project/investment-agent/data_external/db/external_data.db')

print("="*100)
print("切片1复盘：2016-2017 宏观因子与资产表现关联分析")
print("="*100)

# ============================================================================
# Step 1: 读取宏观因子数据（level类型）
# ============================================================================
print("\n【Step 1】读取宏观因子数据...")

macro_sql = """
SELECT 
    indicator_code,
    publish_date,
    factor_value,
    factor_type
FROM macro_factor_value
WHERE factor_type = 'level'
    AND publish_date BETWEEN '20160101' AND '20171231'
ORDER BY indicator_code, publish_date
"""

macro_df = pd.read_sql(macro_sql, engine)
macro_df['publish_date'] = pd.to_datetime(macro_df['publish_date'].astype(str))
macro_df['year_month'] = macro_df['publish_date'].dt.strftime('%Y%m')

print(f"宏观因子记录数: {len(macro_df)}")
print(f"指标数量: {macro_df['indicator_code'].nunique()}")
print(f"时间跨度: {macro_df['year_month'].min()} 至 {macro_df['year_month'].max()}")

# 透视：宽格式，每行一个月，每列一个指标
macro_pivot = macro_df.pivot(index='year_month', columns='indicator_code', values='factor_value')
print(f"\n宏观因子宽表: {macro_pivot.shape}")

# ============================================================================
# Step 2: 计算资产月度收益率（滞后1月）
# ============================================================================
print("\n【Step 2】计算资产月度收益率...")

# 读取指数价格数据
price_sql = """
SELECT index_code, trade_date, close_price
FROM index_daily
WHERE index_code IN (
    '000300.SH',   -- 沪深300
    '000905.SH',   -- 中证500
    '000852.SH',   -- 中证1000
    '801010.SI',   -- 农林牧渔
    '801030.SI',   -- 基础化工
    '801040.SI',   -- 钢铁
    '801050.SI',   -- 有色金属
    '801080.SI',   -- 电子
    '801110.SI',   -- 家用电器
    '801120.SI',   -- 食品饮料
    '801130.SI',   -- 纺织服饰
    '801140.SI',   -- 轻工制造
    '801150.SI',   -- 医药生物
    '801160.SI',   -- 公用事业
    '801170.SI',   -- 交通运输
    '801180.SI',   -- 房地产
    '801200.SI',   -- 商贸零售
    '801210.SI',   -- 社会服务
    '801230.SI',   -- 综合
    '801710.SI',   -- 建筑材料
    '801720.SI',   -- 建筑装饰
    '801730.SI',   -- 电力设备
    '801740.SI',   -- 国防军工
    '801750.SI',   -- 计算机
    '801760.SI',   -- 传媒
    '801770.SI',   -- 通信
    '801780.SI',   -- 银行
    '801790.SI',   -- 非银金融
    '801880.SI',   -- 汽车
    '801890.SI',   -- 机械设备
    '801950.SI',   -- 煤炭
    '801960.SI',   -- 石油石化
    '801970.SI',   -- 环保
    '801980.SI'    -- 美容护理
)
ORDER BY index_code, trade_date
"""

price_df = pd.read_sql(price_sql, engine)
price_df['trade_date'] = price_df['trade_date'].astype(str).str.replace('-', '')
print(f"价格数据记录数: {len(price_df)}")

# 计算月度收益率（滞后1月）
calendar = TradeCalendarService()
date_pairs = calendar.get_month_end_dates('20160101', '20171231')

asset_returns = []
for index_code, group in price_df.groupby('index_code'):
    group = group.sort_values('trade_date')
    price_series = group.set_index('trade_date')['close_price']
    
    for prev_end, curr_end in date_pairs:
        monthly_return = calculate_period_return(
            price_series,
            start_date=prev_end,
            end_date=curr_end,
            method='compound'
        )
        
        if monthly_return is not None:
            trade_month = curr_end[:6]
            asset_returns.append({
                'index_code': index_code,
                'trade_month': trade_month,
                'period_start': prev_end,
                'period_end': curr_end,
                'monthly_return': monthly_return
            })

asset_df = pd.DataFrame(asset_returns)
print(f"资产收益率记录数: {len(asset_df)}")

# 透视：宽格式
asset_pivot = asset_df.pivot(index='trade_month', columns='index_code', values='monthly_return')
print(f"资产收益率宽表: {asset_pivot.shape}")

# ============================================================================
# Step 3: 宏观状态定义与资产表现关联
# ============================================================================
print("\n【Step 3】宏观状态定义与资产表现关联...")

# 合并宏观因子和资产收益（滞后1月）
# 宏观数据2016-02 → 资产收益2016-03（即宏观月份+1）
macro_pivot.index = macro_pivot.index.astype(str)
asset_pivot.index = asset_pivot.index.astype(str)

# 为资产收益建立滞后索引（即使用上月宏观数据预测本月收益）
# 资产收益201603对应宏观数据201602（即宏观月份=资产月份-1）
asset_pivot_lag = asset_pivot.copy()
# 将YYYYMM转为datetime再减1个月
asset_pivot_lag.index = [
    (pd.to_datetime(x + '01', format='%Y%m%d') + pd.DateOffset(months=-1)).strftime('%Y%m')
    for x in asset_pivot_lag.index
]

# 合并
combined = pd.merge(macro_pivot, asset_pivot_lag, left_index=True, right_index=True, how='inner')
print(f"合并后数据量: {len(combined)} 个月")

# ============================================================================
# Step 4: 关键规则验证
# ============================================================================
print("\n【Step 4】策略规则验证...")

# 规则1: PPI > +2σ → 超配上游周期（煤炭、钢铁、有色）
print("\n" + "="*80)
print("规则1: PPI > +2σ → 上游周期行业")
print("="*80)

ppi_high = combined[combined['CN_PPI_YOY_M'] > 2.0]
print(f"PPI > +2σ 的月份数: {len(ppi_high)}")

if len(ppi_high) > 0:
    # 上游行业
    upstream_cols = ['801950.SI', '801040.SI', '801050.SI']  # 煤炭、钢铁、有色
    upstream_names = {'801950.SI': '煤炭', '801040.SI': '钢铁', '801050.SI': '有色金属'}
    
    print("\n上游行业在PPI高位期的平均月收益率:")
    for col in upstream_cols:
        if col in ppi_high.columns:
            avg_return = ppi_high[col].mean() * 100
            print(f"  {upstream_names[col]} ({col}): {avg_return:.2f}%")
    
    # 沪深300基准
    bench_return = ppi_high['000300.SH'].mean() * 100
    print(f"\n  沪深300基准: {bench_return:.2f}%")
    
    # 超额收益
    print("\n超额收益（vs 沪深300）:")
    for col in upstream_cols:
        if col in ppi_high.columns:
            excess = (ppi_high[col].mean() - ppi_high['000300.SH'].mean()) * 100
            print(f"  {upstream_names[col]}: {excess:+.2f}%")

# 规则2: PMI_MFG > PMI_SVC → 工业 > 消费/服务
print("\n" + "="*80)
print("规则2: PMI制造业 > PMI服务业 → 工业 > 消费")
print("="*80)

pmi_mfg = combined['CN_PMI_MFG_M'] if 'CN_PMI_MFG_M' in combined.columns else None
pmi_svc = combined['CN_PMI_SVC_M'] if 'CN_PMI_SVC_M' in combined.columns else None

if pmi_mfg is not None and pmi_svc is not None:
    pmi_industrial = combined[pmi_mfg > pmi_svc]
    print(f"PMI_MFG > PMI_SVC 的月份数: {len(pmi_industrial)}")
    
    if len(pmi_industrial) > 0:
        # 工业 vs 消费
        industrial_cols = ['801040.SI', '801050.SI', '801890.SI']  # 钢铁、有色、机械
        consumer_cols = ['801120.SI', '801110.SI', '801150.SI']    # 食品饮料、家电、医药
        
        industrial_names = {'801040.SI': '钢铁', '801050.SI': '有色金属', '801890.SI': '机械设备'}
        consumer_names = {'801120.SI': '食品饮料', '801110.SI': '家用电器', '801150.SI': '医药生物'}
        
        print("\n工业行业表现:")
        for col in industrial_cols:
            if col in pmi_industrial.columns:
                avg_return = pmi_industrial[col].mean() * 100
                print(f"  {industrial_names[col]}: {avg_return:.2f}%")
        
        print("\n消费行业表现:")
        for col in consumer_cols:
            if col in pmi_industrial.columns:
                avg_return = pmi_industrial[col].mean() * 100
                print(f"  {consumer_names[col]}: {avg_return:.2f}%")

# 规则3: M2持续低迷 → 大盘价值 > 小盘成长
print("\n" + "="*80)
print("规则3: M2低迷 → 大盘价值 > 小盘成长")
print("="*80)

m2_low = combined[combined['CN_M2_YOY_M'] < -1.0]
print(f"M2 < -1σ 的月份数: {len(m2_low)}")

if len(m2_low) > 0:
    large_cap = m2_low['000300.SH'].mean() * 100  # 沪深300
    mid_cap = m2_low['000905.SH'].mean() * 100    # 中证500
    small_cap = m2_low['000852.SH'].mean() * 100   # 中证1000
    
    print(f"\n不同市值表现:")
    print(f"  大盘（沪深300）: {large_cap:.2f}%")
    print(f"  中盘（中证500）: {mid_cap:.2f}%")
    print(f"  小盘（中证1000）: {small_cap:.2f}%")

# 规则4: PPI-CPI缺口 > +1.5σ → 上游 > 下游
print("\n" + "="*80)
print("规则4: PPI-CPI缺口 > +1.5σ → 上游 > 下游")
print("="*80)

if 'CN_PPI_YOY_M' in combined.columns and 'CN_CPI_YOY_M' in combined.columns:
    combined['ppi_cpi_gap'] = combined['CN_PPI_YOY_M'] - combined['CN_CPI_YOY_M']
    gap_high = combined[combined['ppi_cpi_gap'] > 1.5]
    print(f"PPI-CPI缺口 > +1.5σ 的月份数: {len(gap_high)}")
    
    if len(gap_high) > 0:
        upstream = gap_high['801050.SI'].mean() * 100  # 有色金属
        downstream = gap_high['801120.SI'].mean() * 100  # 食品饮料
        
        print(f"\n上游（有色金属）: {upstream:.2f}%")
        print(f"下游（食品饮料）: {downstream:.2f}%")
        print(f"差距: {(upstream - downstream):+.2f}%")

# ============================================================================
# Step 5: 完整月度对照表（关键月份）
# ============================================================================
print("\n" + "="*100)
print("【Step 5】关键月份宏观状态与次月资产表现对照")
print("="*100)

# 选择关键指标和行业
key_indicators = ['CN_PMI_MFG_M', 'CN_PPI_YOY_M', 'CN_CPI_YOY_M', 'CN_M2_YOY_M']
key_assets = ['000300.SH', '801950.SI', '801040.SI', '801050.SI', '801120.SI']
asset_names = {
    '000300.SH': '沪深300',
    '801950.SI': '煤炭',
    '801040.SI': '钢铁',
    '801050.SI': '有色金属',
    '801120.SI': '食品饮料'
}

# 构建展示表
display_data = []
for month in combined.index:
    row = {'宏观月份': month}
    
    # 宏观状态
    for ind in key_indicators:
        if ind in combined.columns:
            row[ind.replace('CN_', '').replace('_YOY_M', '').replace('_M', '')] = combined.loc[month, ind]
    
    # 次月资产收益（注意：combined中资产收益已经是滞后1月的）
    for asset in key_assets:
        if asset in combined.columns:
            ret = combined.loc[month, asset]
            row[asset_names[asset]] = f"{ret*100:.2f}%" if pd.notna(ret) else "N/A"
    
    display_data.append(row)

display_df = pd.DataFrame(display_data)
print("\n月度对照表（前12个月）:")
print(display_df.head(12).to_string(index=False))

# ============================================================================
# Step 6: 保存结果
# ============================================================================
output_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\slice1_macro_asset_analysis.csv'
combined.to_csv(output_path, encoding='utf-8-sig')
print(f"\n完整分析结果已保存: {output_path}")

print("\n" + "="*100)
print("分析完成！")
print("="*100)
