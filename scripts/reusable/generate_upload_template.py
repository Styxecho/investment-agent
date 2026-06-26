#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成宏观数据上传模板

Usage:
    python generate_upload_template.py --year 2026 --month 4 --output template.csv
"""

import pandas as pd
import argparse
from datetime import datetime
import calendar

# 月度指标模板
MONTHLY_TEMPLATE = [
    {'indicator_code': 'CN_PMI_MFG_M', 'description': '制造业PMI'},
    {'indicator_code': 'CN_PMI_SVC_M', 'description': '非制造业PMI'},
    {'indicator_code': 'CN_PMI_COMP_M', 'description': '综合PMI'},
    {'indicator_code': 'CN_IAV_YOY_M', 'description': '工业增加值同比'},
    {'indicator_code': 'CN_CPI_YOY_M', 'description': 'CPI同比'},
    {'indicator_code': 'CN_CCPI_YOY_M', 'description': '核心CPI同比'},
    {'indicator_code': 'CN_CPI_MOM_M', 'description': 'CPI环比'},
    {'indicator_code': 'CN_CCPI_MOM_M', 'description': '核心CPI环比'},
    {'indicator_code': 'CN_CPI_NPF_M', 'description': 'CPI非食品环比'},
    {'indicator_code': 'CN_PPI_YOY_M', 'description': 'PPI同比'},
    {'indicator_code': 'CN_PPI_MOM_M', 'description': 'PPI环比'},
    {'indicator_code': 'CN_PPI_NPF_M', 'description': 'PPI非食品环比'},
    {'indicator_code': 'CN_M0_YOY_M', 'description': 'M0同比'},
    {'indicator_code': 'CN_M1_YOY_M', 'description': 'M1同比'},
    {'indicator_code': 'CN_M2_YOY_M', 'description': 'M2同比'},
    {'indicator_code': 'CN_SFS_YOY_M', 'description': '社融存量同比'},
    {'indicator_code': 'CN_SFS_FLOW_M', 'description': '社融当月值(亿元)'},
    {'indicator_code': 'CN_IIV_YOY_M', 'description': '产成品存货同比'},
]

# 日度指标模板
DAILY_TEMPLATE = [
    {'indicator_code': 'CN_DR007_D', 'description': 'DR007日频'},
    {'indicator_code': 'CN_OMO_R007_D', 'description': 'OMO利率'},
    {'indicator_code': 'CN_R007_D', 'description': 'R007日频'},
]


def generate_monthly_template(year, month):
    """生成月度数据模板"""
    # 计算月末日期
    last_day = calendar.monthrange(year, month)[1]
    publish_date = f"{year}{month:02d}{last_day:02d}"
    
    rows = []
    for item in MONTHLY_TEMPLATE:
        rows.append({
            'indicator_code': item['indicator_code'],
            'publish_date': publish_date,
            'value': '',  # 用户填写
            'frequency': 'monthly',
            'period_type': 'yoy' if 'YOY' in item['indicator_code'] else ('mom' if 'MOM' in item['indicator_code'] else 'absolute'),
            'description': item['description'],
        })
    
    return pd.DataFrame(rows)


def generate_daily_template(year, month):
    """生成日度数据模板（整月）"""
    from pandas.tseries.offsets import BDay
    
    start_date = pd.Timestamp(year=year, month=month, day=1)
    end_date = pd.Timestamp(year=year, month=month, day=calendar.monthrange(year, month)[1])
    
    # 获取工作日
    business_days = pd.date_range(start=start_date, end=end_date, freq=BDay())
    
    rows = []
    for date in business_days:
        date_str = date.strftime('%Y%m%d')
        for item in DAILY_TEMPLATE:
            rows.append({
                'indicator_code': item['indicator_code'],
                'publish_date': date_str,
                'value': '',  # 用户填写
                'frequency': 'daily',
                'period_type': 'absolute',
                'description': item['description'],
            })
    
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description='生成宏观数据上传模板')
    parser.add_argument('--year', type=int, default=datetime.now().year, help='年份')
    parser.add_argument('--month', type=int, default=datetime.now().month, help='月份')
    parser.add_argument('--type', choices=['monthly', 'daily', 'both'], default='monthly', help='模板类型')
    parser.add_argument('--output', default='macro_upload_template.csv', help='输出文件名')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("V7 宏观数据上传模板生成器")
    print("=" * 70)
    print(f"\n生成 {args.year}年{args.month}月 的数据模板...")
    
    if args.type in ['monthly', 'both']:
        monthly_df = generate_monthly_template(args.year, args.month)
        monthly_file = args.output.replace('.csv', '_monthly.csv')
        monthly_df.to_csv(monthly_file, index=False, encoding='utf-8-sig')
        print(f"\n[OK] 月度模板已生成: {monthly_file}")
        print(f"     包含 {len(monthly_df)} 个指标")
        print("\n预览:")
        print(monthly_df.head(5).to_string(index=False))
    
    if args.type in ['daily', 'both']:
        daily_df = generate_daily_template(args.year, args.month)
        daily_file = args.output.replace('.csv', '_daily.csv')
        daily_df.to_csv(daily_file, index=False, encoding='utf-8-sig')
        print(f"\n[OK] 日度模板已生成: {daily_file}")
        print(f"     包含 {len(daily_df)} 条记录 ({len(DAILY_TEMPLATE)} 个指标 × 工作日)")
        print("\n预览:")
        print(daily_df.head(5).to_string(index=False))
    
    print("\n" + "=" * 70)
    print("使用说明:")
    print("1. 在'value'列填入实际数据")
    print("2. 不需要的指标可以删除整行")
    print("3. 保存后使用以下命令上传:")
    print(f"   python scripts/reusable/upload_macro_data.py --file {args.output} --type {args.type}")
    print("=" * 70)


if __name__ == '__main__':
    main()
