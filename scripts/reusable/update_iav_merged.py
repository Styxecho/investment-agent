#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
1. 清理旧IAV数据
2. 导入合并后的IAV数据（列5）
3. 对1月缺失值进行线性插值
"""

import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
import pandas as pd
from data_external.db.engine import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_old_iav():
    """清理旧的IAV数据"""
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM macro_indicator_value WHERE indicator_code = 'CN_IAV_YOY_M'"))
        conn.execute(text("DELETE FROM macro_factor_value WHERE indicator_code = 'CN_IAV_YOY_M'"))
        conn.commit()
    logger.info("Cleaned old IAV data")

def import_merged_iav():
    """导入合并后的IAV数据（列5）"""
    monthly_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\marco_indicators_history_series_monthly.csv'
    df = pd.read_csv(monthly_file, encoding='gbk')
    
    # 数据从第6行开始
    data_df = df.iloc[5:].copy()
    date_col = data_df.columns[0]
    data_df[date_col] = pd.to_datetime(data_df[date_col], errors='coerce')
    data_df = data_df.dropna(subset=[date_col])
    
    # 使用列5（合并数据）
    col5_name = df.columns[5]
    logger.info(f"Using column 5: {col5_name}")
    
    records = []
    for _, row in data_df.iterrows():
        val = row.iloc[5]
        if pd.notna(val) and str(val).strip() != '':
            try:
                records.append({
                    'indicator_code': 'CN_IAV_YOY_M',
                    'publish_date': row[date_col].strftime('%Y%m%d'),
                    'value': float(val),
                    'frequency': 'monthly',
                    'period_type': 'yoy',
                    'data_source': 'wind'
                })
            except:
                pass
    
    if records:
        value_df = pd.DataFrame(records)
        # 先按日期排序
        value_df = value_df.sort_values('publish_date')
        
        # 对缺失的1月进行插值
        value_df['date'] = pd.to_datetime(value_df['publish_date'], format='%Y%m%d')
        value_df = value_df.set_index('date').sort_index()
        
        # 创建完整的月度序列
        full_index = pd.date_range(start=value_df.index.min(), end=value_df.index.max(), freq='ME')
        value_df = value_df.reindex(full_index)
        
        # 线性插值
        value_df['value'] = value_df['value'].interpolate(method='linear')
        value_df['indicator_code'] = 'CN_IAV_YOY_M'
        value_df['frequency'] = 'monthly'
        value_df['period_type'] = 'yoy'
        value_df['data_source'] = 'wind'
        
        # 恢复publish_date
        value_df['publish_date'] = value_df.index.strftime('%Y%m%d')
        value_df = value_df.reset_index(drop=True)
        
        # 只保留有值的记录
        value_df = value_df.dropna(subset=['value'])
        
        # 存入数据库
        value_df[['indicator_code', 'publish_date', 'value', 'frequency', 'period_type', 'data_source']].to_sql(
            'macro_indicator_value', engine, if_exists='append', index=False
        )
        
        logger.info(f"Imported {len(value_df)} merged IAV records")
        
        # 显示插值前后的对比
        print("\n=== 插值示例 ===")
        sample = value_df[value_df['publish_date'].str.contains(r'202[0-4]01|202[0-4]02')].iloc[:10]
        print(sample[['publish_date', 'value']].to_string(index=False))
    
    return len(value_df) if 'value_df' in dir() else 0

if __name__ == '__main__':
    print("=== 更新IAV为合并数据 ===\n")
    clean_old_iav()
    count = import_merged_iav()
    print(f"\n=== 完成，导入 {count} 条合并IAV数据 ===")
