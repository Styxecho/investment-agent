#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
切片一：2016-2017 供给侧改革与漂亮50 复盘分析
"""

import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
import pandas as pd
from data_external.db.engine import engine

# 提取2016-2017年因子数据
df = pd.read_sql("""
SELECT 
    indicator_code,
    publish_date,
    factor_type,
    factor_value
FROM macro_factor_value
WHERE publish_date BETWEEN '20160131' AND '20171231'
ORDER BY indicator_code, factor_type, publish_date
""", engine)

# 添加类别标签
category_map = {
    'CN_PMI_MFG_M': '经济增长', 'CN_PMI_SVC_M': '经济增长', 'CN_PMI_COMP_M': '经济增长', 'CN_IAV_YOY_M': '经济增长',
    'CN_CPI_YOY_M': '通胀', 'CN_PPI_YOY_M': '通胀', 'CN_NHCCI_D': '通胀',
    'CN_M0_YOY_M': '流动性', 'CN_M1_YOY_M': '流动性', 'CN_M2_YOY_M': '流动性', 'CN_SFS_YOY_M': '流动性', 'CN_DR007_D': '流动性',
    'CN_TREASURY_BOND_10Y_D': '利率', 'CN_FX_USDCNY_MID_D': '风险', 'CN_DXY_D': '风险', 'CN_IIV_YOY_M': '库存'
}
df['category'] = df['indicator_code'].map(category_map)

# 计算每个类别在关键月份的均值
df['date'] = pd.to_datetime(df['publish_date'], format='%Y%m%d')
df['year_month'] = df['date'].dt.to_period('M')

# 按月统计各类别因子均值
monthly_summary = df.groupby(['year_month', 'category', 'factor_type'])['factor_value'].mean().reset_index()

# 选取关键月份展示
key_months = ['2016-02', '2016-06', '2016-12', '2017-06', '2017-12']
key_data = monthly_summary[monthly_summary['year_month'].astype(str).isin(key_months)]

print('=== 切片一：2016-2017 宏观因子复盘 ===\n')

print('关键月份因子概览（水平因子）：')
print(key_data[key_data['factor_type'] == 'level'].pivot_table(
    index=['year_month', 'category'], 
    columns='factor_type', 
    values='factor_value'
).to_string())

# 计算年度统计
print('\n\n=== 2016年 vs 2017年 对比 ===')
df['year'] = df['date'].dt.year
annual = df[df['factor_type'] == 'level'].groupby(['year', 'category'])['factor_value'].agg(['mean', 'min', 'max']).round(2)
print(annual.to_string())

# 导出详细数据
output_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\slice_2016_2017_factors.csv'
df.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f'\n详细数据已导出: {output_file}')

# 导出月度汇总
summary_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\slice_2016_2017_monthly.csv'
monthly_wide = monthly_summary.pivot_table(
    index='year_month', 
    columns=['category', 'factor_type'], 
    values='factor_value'
)
monthly_wide.to_csv(summary_file, encoding='utf-8-sig')
print(f'月度汇总已导出: {summary_file}')
