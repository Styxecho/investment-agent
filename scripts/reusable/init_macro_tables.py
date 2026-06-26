#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
创建宏观数据表并导入历史数据（最终版）
"""

import pandas as pd
import numpy as np
import sys

sys.path.insert(0, r'D:\Study\Project\investment-agent')

from data_external.db.engine import engine
from sqlalchemy import text

def create_tables():
    """创建宏观数据表"""
    
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS macro_indicator_value"))
        conn.execute(text("DROP TABLE IF EXISTS macro_indicator_catalog"))
        conn.commit()
    
    create_catalog_sql = """
    CREATE TABLE macro_indicator_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator_code VARCHAR(50) UNIQUE NOT NULL,
        indicator_name VARCHAR(100) NOT NULL,
        category VARCHAR(30) NOT NULL,
        country VARCHAR(20) NOT NULL,
        frequency VARCHAR(10) NOT NULL,
        unit VARCHAR(20),
        data_source VARCHAR(20) DEFAULT 'wind',
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK (category IN ('growth', 'inflation', 'liquidity', 'rates', 'risk', 'inventory')),
        CHECK (country IN ('CN', 'US')),
        CHECK (frequency IN ('daily', 'monthly', 'quarterly')),
        CHECK (unit IN ('ABS', 'PCT', 'INDEX', 'BILLION'))
    )
    """
    
    create_value_sql = """
    CREATE TABLE macro_indicator_value (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator_code VARCHAR(50) NOT NULL,
        publish_date VARCHAR(8) NOT NULL,
        value DECIMAL(18,4),
        frequency VARCHAR(10) NOT NULL,
        period_type VARCHAR(10),
        data_source VARCHAR(20) DEFAULT 'wind',
        is_revised BOOLEAN DEFAULT 0,
        revision_note VARCHAR(200),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(indicator_code, publish_date, frequency, period_type),
        CHECK (frequency IN ('daily', 'monthly', 'quarterly')),
        CHECK (period_type IN ('yoy', 'mom', 'cumulative', 'absolute'))
    )
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_catalog_sql))
        conn.execute(text(create_value_sql))
        conn.commit()
    
    print("[OK] 数据库表创建成功")


def import_catalog():
    """导入指标目录"""
    
    catalog_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_indicators.csv'
    df = pd.read_csv(catalog_file, encoding='utf-8-sig')
    df.columns = ['indicator_code', 'indicator_name', 'category', 'country', 'frequency', 'unit']
    
    # 中文映射为英文
    df['category'] = df['category'].map({
        '经济增长': 'growth', '通胀': 'inflation', '流动性': 'liquidity',
        '利率': 'rates', '风险': 'risk', '库存': 'inventory'
    })
    df['country'] = df['country'].map({'中国': 'CN', '美国': 'US'})
    df['unit'] = df['unit'].map({'绝对值': 'ABS', '百分比': 'PCT', '指数点': 'INDEX', '亿元': 'BILLION'})
    df['frequency'] = df['frequency'].map({'日频': 'daily', '月频': 'monthly', '季频': 'quarterly'})
    df['description'] = df['indicator_name']
    
    df.to_sql('macro_indicator_catalog', engine, if_exists='append', index=False)
    print(f"[OK] 导入 {len(df)} 个指标目录")
    return df


def match_indicator(col_name, catalog_df):
    """
    智能匹配列名与indicator_code
    
    策略：
    1. 完全匹配（clean后相等）
    2. 包含匹配（一方包含另一方）
    3. 关键词匹配（提取关键词进行匹配）
    4. 手动映射（特定指标）
    """
    
    col_clean = col_name.replace(':', '').replace('-', '').replace(' ', '')
    
    # 手动映射表（特定指标）
    manual_mapping = {
        '中间价美元兑人民币': 'CN_FX_USDCNY_MID_D',
        '美元兑人民币': 'CN_FX_USDCNY_MID_D',
        '银行间质押式回购加权利率7天': 'CN_DR007_D',  # 如果存在
        '银行间质押式回购': 'CN_DR007_D',
    }
    
    if col_clean in manual_mapping:
        return manual_mapping[col_clean]
    
    # 尝试自动匹配
    best_match = None
    best_score = 0
    
    for _, row in catalog_df.iterrows():
        indicator_name = str(row['indicator_name'])
        cat_clean = indicator_name.replace('-', '').replace(':', '').replace(' ', '')
        
        # 策略1: 完全匹配或包含匹配
        if col_clean == cat_clean or col_clean in cat_clean or cat_clean in col_clean:
            return row['indicator_code']
        
        # 策略2: 关键词匹配（计算公共子串比例）
        # 提取3-4个字符的关键词
        col_keywords = set()
        for i in range(len(col_clean)-2):
            col_keywords.add(col_clean[i:i+3])
        
        cat_keywords = set()
        for i in range(len(cat_clean)-2):
            cat_keywords.add(cat_clean[i:i+3])
        
        common = col_keywords & cat_keywords
        if len(common) > 0:
            score = len(common) / max(len(col_keywords), len(cat_keywords))
            if score > best_score:
                best_score = score
                best_match = row['indicator_code']
    
    # 只有当匹配度足够高时才返回
    if best_score >= 0.3:  # 阈值30%
        return best_match
    
    return None


def import_monthly_data():
    """导入月频历史数据"""
    
    monthly_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\marco_indicators_history_series_monthly.csv'
    df = pd.read_csv(monthly_file, encoding='gbk')
    
    # 列名已经在df.columns中
    col_names = df.columns.tolist()
    
    # 获取catalog
    catalog_df = pd.read_sql("SELECT * FROM macro_indicator_catalog", engine)
    
    # 建立列索引到indicator_code的映射
    col_mapping = {}
    for i in range(1, len(col_names)):  # 跳过第1列（日期列）
        col_name = str(col_names[i])
        matched_code = match_indicator(col_name, catalog_df)
        if matched_code:
            col_mapping[i] = matched_code
    
    print(f"[INFO] 成功匹配 {len(col_mapping)} 个月频指标")
    for col_idx, code in col_mapping.items():
        print(f"  列{col_idx}: {col_names[col_idx]} -> {code}")
    
    # 显示未匹配的列
    unmatched = [i for i in range(1, len(col_names)) if i not in col_mapping]
    if unmatched:
        print(f"[WARN] 未匹配 {len(unmatched)} 个指标:")
        for i in unmatched:
            print(f"  列{i}: {col_names[i]}")
    
    # 数据从第6行开始（索引5）
    data_df = df.iloc[5:].copy()
    data_df.columns = ['date'] + [f'col_{i}' for i in range(1, len(data_df.columns))]
    
    # 转换日期
    data_df['date'] = pd.to_datetime(data_df['date'], errors='coerce')
    data_df = data_df.dropna(subset=['date'])
    data_df['date'] = data_df['date'].dt.strftime('%Y%m%d')
    
    # 构建记录
    records = []
    for col_idx, indicator_code in col_mapping.items():
        col_name = f'col_{col_idx}'
        for _, row in data_df.iterrows():
            value = row[col_name]
            if pd.notna(value) and str(value).strip() != '':
                try:
                    records.append({
                        'indicator_code': indicator_code,
                        'publish_date': row['date'],
                        'value': float(value),
                        'frequency': 'monthly',
                        'period_type': 'absolute' if 'PMI' in indicator_code else 'yoy',
                        'data_source': 'wind'
                    })
                except:
                    pass
    
    if records:
        value_df = pd.DataFrame(records)
        value_df.to_sql('macro_indicator_value', engine, if_exists='append', index=False)
        print(f"[OK] 导入 {len(records)} 条月频数据")
    else:
        print("[WARN] 未找到月频数据")


def import_daily_data():
    """导入日频历史数据"""
    
    daily_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_indicators_history_series_daily.csv'
    df = pd.read_csv(daily_file, encoding='utf-8-sig')
    
    # 中文列名在第3行（索引2）
    raw_col_names = df.iloc[2, :].tolist()
    
    # 获取catalog
    catalog_df = pd.read_sql("SELECT * FROM macro_indicator_catalog", engine)
    
    # 建立列索引到indicator_code的映射
    col_mapping = {}
    for i in range(1, len(raw_col_names)):  # 跳过第0列（日期列）
        if pd.isna(raw_col_names[i]):
            continue
        col_name = str(raw_col_names[i])
        matched_code = match_indicator(col_name, catalog_df)
        if matched_code:
            col_mapping[i] = matched_code
    
    print(f"[INFO] 成功匹配 {len(col_mapping)} 个日频指标")
    for col_idx, code in col_mapping.items():
        print(f"  列{col_idx}: {raw_col_names[col_idx]} -> {code}")
    
    # 显示未匹配的列
    unmatched = [i for i in range(1, len(raw_col_names)) if i not in col_mapping and pd.notna(raw_col_names[i])]
    if unmatched:
        print(f"[WARN] 未匹配 {len(unmatched)} 个指标:")
        for i in unmatched:
            print(f"  列{i}: {raw_col_names[i]}")
    
    # 数据从第5行开始（索引4）
    data_df = df.iloc[4:].copy()
    # 只保留有数据的列（前5列）
    data_df = data_df.iloc[:, :5]
    data_df.columns = ['date'] + [f'col_{i}' for i in range(1, len(data_df.columns))]
    
    # 转换日期
    data_df['date'] = pd.to_datetime(data_df['date'], errors='coerce')
    data_df = data_df.dropna(subset=['date'])
    data_df['date'] = data_df['date'].dt.strftime('%Y%m%d')
    
    # 构建记录
    records = []
    for col_idx, indicator_code in col_mapping.items():
        col_name = f'col_{col_idx}'
        for _, row in data_df.iterrows():
            value = row[col_name]
            if pd.notna(value) and str(value).strip() != '':
                try:
                    records.append({
                        'indicator_code': indicator_code,
                        'publish_date': row['date'],
                        'value': float(value),
                        'frequency': 'daily',
                        'period_type': 'absolute',
                        'data_source': 'wind'
                    })
                except:
                    pass
    
    if records:
        value_df = pd.DataFrame(records)
        value_df.to_sql('macro_indicator_value', engine, if_exists='append', index=False)
        print(f"[OK] 导入 {len(records)} 条日频数据")
    else:
        print("[WARN] 未找到日频数据")


if __name__ == '__main__':
    print("=== 宏观数据表创建与初始化 ===\n")
    
    create_tables()
    import_catalog()
    import_monthly_data()
    import_daily_data()
    
    print("\n=== 完成 ===")
    
    # 验证
    catalog_count = pd.read_sql("SELECT COUNT(*) as cnt FROM macro_indicator_catalog", engine).iloc[0]['cnt']
    value_count = pd.read_sql("SELECT COUNT(*) as cnt FROM macro_indicator_value", engine).iloc[0]['cnt']
    print(f"\n  指标目录: {catalog_count} 个")
    print(f"  指标数值: {value_count} 条")
    
    print("\n指标目录样本：")
    print(pd.read_sql("SELECT indicator_code, indicator_name, category, country FROM macro_indicator_catalog LIMIT 5", engine).to_string(index=False))
    
    print("\n月频数据样本：")
    print(pd.read_sql("SELECT * FROM macro_indicator_value WHERE frequency='monthly' LIMIT 5", engine).to_string(index=False))
    
    print("\n日频数据样本：")
    print(pd.read_sql("SELECT * FROM macro_indicator_value WHERE frequency='daily' LIMIT 5", engine).to_string(index=False))
