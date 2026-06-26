#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导入V2宏观数据到数据库
- 清理旧数据（针对V2中包含的指标）
- 导入月度数据（18个指标）
- 导入日度数据（2个指标）
- 更新指标目录
"""

import pandas as pd
import sys

sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
from sqlalchemy import text

# ============================================================
# 配置
# ============================================================

MONTHLY_FILE = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\raw_data\marco_indicators_history_series_monthly_v2.csv'
DAILY_FILE = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\raw_data\macro_indicators_history_series_daily_v2.csv'

# 指标元数据配置
INDICATOR_META = {
    # 月度指标
    'CN_PMI_MFG_M': {
        'name': '中国-制造业PMI',
        'category': 'growth',
        'frequency': 'monthly',
        'unit': 'INDEX',
        'period_type': 'absolute',
    },
    'CN_PMI_SVC_M': {
        'name': '中国-非制造业PMI',
        'category': 'growth',
        'frequency': 'monthly',
        'unit': 'INDEX',
        'period_type': 'absolute',
    },
    'CN_PMI_COMP_M': {
        'name': '中国-综合PMI',
        'category': 'growth',
        'frequency': 'monthly',
        'unit': 'INDEX',
        'period_type': 'absolute',
    },
    'CN_IAV_YOY_M': {
        'name': '中国-工业增加值-当月同比',
        'category': 'growth',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'yoy',
    },
    'CN_CPI_YOY_M': {
        'name': '中国-CPI-当月同比',
        'category': 'inflation',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'yoy',
    },
    'CN_CCPI_YOY_M': {
        'name': '中国-核心CPI-当月同比',
        'category': 'inflation',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'yoy',
    },
    'CN_CPI_MOM_M': {
        'name': '中国-CPI-环比',
        'category': 'inflation',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'mom',
    },
    'CN_CCPI_MOM_M': {
        'name': '中国-核心CPI-环比',
        'category': 'inflation',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'mom',
    },
    'CN_CPI_NPF_M': {
        'name': '中国-CPI-非食品价格环比',
        'category': 'inflation',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'mom',
    },
    'CN_PPI_YOY_M': {
        'name': '中国-PPI-当月同比',
        'category': 'inflation',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'yoy',
    },
    'CN_PPI_MOM_M': {
        'name': '中国-PPI-环比',
        'category': 'inflation',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'mom',
    },
    'CN_PPI_NPF_M': {
        'name': '中国-PPI-非食品价格环比',
        'category': 'inflation',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'mom',
    },
    'CN_M0_YOY_M': {
        'name': '中国-M0-同比',
        'category': 'liquidity',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'yoy',
    },
    'CN_M1_YOY_M': {
        'name': '中国-M1-同比',
        'category': 'liquidity',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'yoy',
    },
    'CN_M2_YOY_M': {
        'name': '中国-M2-同比',
        'category': 'liquidity',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'yoy',
    },
    'CN_SFS_YOY_M': {
        'name': '中国-社融规模存量-当月同比',
        'category': 'liquidity',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'yoy',
    },
    'CN_SFS_FLOW_M': {
        'name': '中国-社融规模-当月值',
        'category': 'liquidity',
        'frequency': 'monthly',
        'unit': 'BILLION',
        'period_type': 'absolute',
    },
    'CN_IIV_YOY_M': {
        'name': '中国-规模以上企业产成品存货-当月同比',
        'category': 'inventory',
        'frequency': 'monthly',
        'unit': 'PCT',
        'period_type': 'yoy',
    },
    # 日度指标
    'CN_DR007_D': {
        'name': '中国-存款类机构质押式回购加权利率-7天',
        'category': 'liquidity',
        'frequency': 'daily',
        'unit': 'PCT',
        'period_type': 'absolute',
    },
    'CN_OMO_R007_D': {
        'name': '中国-公开市场操作-7天逆回购利率',
        'category': 'rates',
        'frequency': 'daily',
        'unit': 'PCT',
        'period_type': 'absolute',
    },
}

# ============================================================
# 工具函数
# ============================================================

def clean_old_data(indicator_codes):
    """清理指定指标的旧数据"""
    placeholders = ','.join([f"'{code}'" for code in indicator_codes])
    delete_sql = f"DELETE FROM macro_indicator_value WHERE indicator_code IN ({placeholders})"
    
    with engine.connect() as conn:
        result = conn.execute(text(delete_sql))
        conn.commit()
        print(f"[OK] 已清理 {result.rowcount} 条旧记录")


def update_catalog():
    """更新指标目录（INSERT OR REPLACE）"""
    insert_sql = """
    INSERT OR REPLACE INTO macro_indicator_catalog 
    (indicator_code, indicator_name, category, country, frequency, unit, data_source, description, is_active)
    VALUES (:code, :name, :category, :country, :frequency, :unit, 'wind', :description, 1)
    """
    
    with engine.connect() as conn:
        count = 0
        for code, meta in INDICATOR_META.items():
            conn.execute(text(insert_sql), {
                'code': code,
                'name': meta['name'],
                'category': meta['category'],
                'country': 'CN',
                'frequency': meta['frequency'],
                'unit': meta['unit'],
                'description': meta['name'],
            })
            count += 1
        conn.commit()
    
    print(f"[OK] 已更新 {count} 个指标目录")


def import_monthly_data():
    """导入月度数据"""
    print("\n=== 导入月度数据 ===")
    
    # 读取CSV，第一行是indicator_code，前6行是元数据
    df = pd.read_csv(MONTHLY_FILE, encoding='gbk')
    
    # 列名已经在第一行
    columns = df.columns.tolist()
    print(f"[INFO] 发现 {len(columns)-1} 个指标列")
    
    # 跳过前6行元数据（索引0-5），从索引6开始是数据
    data_df = df.iloc[6:].copy()
    
    # 转换日期列
    data_df[columns[0]] = pd.to_datetime(data_df[columns[0]], errors='coerce')
    data_df = data_df.dropna(subset=[columns[0]])
    data_df['publish_date'] = data_df[columns[0]].dt.strftime('%Y%m%d')
    
    records = []
    for col in columns[1:]:
        indicator_code = col.strip()
        if indicator_code not in INDICATOR_META:
            print(f"[WARN] 未配置指标: {indicator_code}，跳过")
            continue
        
        meta = INDICATOR_META[indicator_code]
        count = 0
        
        for _, row in data_df.iterrows():
            value = row[col]
            if pd.notna(value) and str(value).strip() != '':
                try:
                    records.append({
                        'indicator_code': indicator_code,
                        'publish_date': row['publish_date'],
                        'value': float(value),
                        'frequency': 'monthly',
                        'period_type': meta['period_type'],
                        'data_source': 'wind',
                    })
                    count += 1
                except (ValueError, TypeError):
                    pass
        
        print(f"  {indicator_code}: {count} 条记录")
    
    if records:
        value_df = pd.DataFrame(records)
        value_df.to_sql('macro_indicator_value', engine, if_exists='append', index=False)
        print(f"[OK] 导入 {len(records)} 条月度数据")
    else:
        print("[WARN] 未找到月度数据")
    
    return len(records) if records else 0


def import_daily_data():
    """导入日度数据"""
    print("\n=== 导入日度数据 ===")
    
    df = pd.read_csv(DAILY_FILE, encoding='gbk')
    
    columns = df.columns.tolist()
    print(f"[INFO] 发现 {len(columns)-1} 个指标列")
    
    # 跳过前6行元数据
    data_df = df.iloc[6:].copy()
    
    # 转换日期列
    data_df[columns[0]] = pd.to_datetime(data_df[columns[0]], errors='coerce')
    data_df = data_df.dropna(subset=[columns[0]])
    data_df['publish_date'] = data_df[columns[0]].dt.strftime('%Y%m%d')
    
    records = []
    for col in columns[1:]:
        indicator_code = col.strip()
        if indicator_code not in INDICATOR_META:
            print(f"[WARN] 未配置指标: {indicator_code}，跳过")
            continue
        
        meta = INDICATOR_META[indicator_code]
        count = 0
        
        for _, row in data_df.iterrows():
            value = row[col]
            if pd.notna(value) and str(value).strip() != '':
                try:
                    records.append({
                        'indicator_code': indicator_code,
                        'publish_date': row['publish_date'],
                        'value': float(value),
                        'frequency': 'daily',
                        'period_type': meta['period_type'],
                        'data_source': 'wind',
                    })
                    count += 1
                except (ValueError, TypeError):
                    pass
        
        print(f"  {indicator_code}: {count} 条记录")
    
    if records:
        value_df = pd.DataFrame(records)
        value_df.to_sql('macro_indicator_value', engine, if_exists='append', index=False)
        print(f"[OK] 导入 {len(records)} 条日度数据")
    else:
        print("[WARN] 未找到日度数据")
    
    return len(records) if records else 0


def generate_summary():
    """生成数据摘要"""
    print("\n=== 数据摘要 ===")
    
    sql = """
    SELECT 
        indicator_code,
        COUNT(*) as cnt,
        MIN(publish_date) as min_date,
        MAX(publish_date) as max_date,
        frequency
    FROM macro_indicator_value
    WHERE indicator_code IN (
        'CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M', 'CN_IAV_YOY_M',
        'CN_CPI_YOY_M', 'CN_CCPI_YOY_M', 'CN_CPI_MOM_M', 'CN_CCPI_MOM_M',
        'CN_CPI_NPF_M', 'CN_PPI_YOY_M', 'CN_PPI_MOM_M', 'CN_PPI_NPF_M',
        'CN_M0_YOY_M', 'CN_M1_YOY_M', 'CN_M2_YOY_M', 'CN_SFS_YOY_M',
        'CN_SFS_FLOW_M', 'CN_IIV_YOY_M', 'CN_DR007_D', 'CN_OMO_R007_D'
    )
    GROUP BY indicator_code
    ORDER BY frequency, indicator_code
    """
    
    df = pd.read_sql(sql, engine)
    print(df.to_string(index=False))
    
    total = df['cnt'].sum()
    print(f"\n总计: {total} 条记录")


# ============================================================
# 主流程
# ============================================================

if __name__ == '__main__':
    print("=== V2宏观数据导入 ===\n")
    
    # 1. 清理旧数据
    all_codes = list(INDICATOR_META.keys())
    print(f"[INFO] 准备清理 {len(all_codes)} 个指标的旧数据")
    clean_old_data(all_codes)
    
    # 2. 更新目录
    update_catalog()
    
    # 3. 导入月度数据
    monthly_count = import_monthly_data()
    
    # 4. 导入日度数据
    daily_count = import_daily_data()
    
    # 5. 生成摘要
    generate_summary()
    
    print(f"\n=== 完成 ===")
    print(f"月度数据: {monthly_count} 条")
    print(f"日度数据: {daily_count} 条")
