#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase E: 批量计算历史宏观因子
"""

import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')

from skills.macro_factor.pipeline import MacroFactorPipeline
from data_external.db.engine import engine
import pandas as pd
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def batch_compute_factors(start_date: str = "20150101", end_date: str = "20241231"):
    """批量计算所有活跃指标的因子"""
    
    # 获取所有活跃指标
    query = "SELECT indicator_code FROM macro_factor_config WHERE is_active = 1"
    indicators = pd.read_sql(text(query), engine)['indicator_code'].tolist()
    
    logger.info(f"开始批量计算 {len(indicators)} 个指标的因子")
    
    pipeline = MacroFactorPipeline()
    total_records = 0
    
    for code in indicators:
        try:
            count = pipeline.run(code, start_date, end_date)
            total_records += count
            logger.info(f"✓ {code}: {count} 条记录")
        except Exception as e:
            logger.error(f"✗ {code}: 计算失败 - {e}")
    
    logger.info(f"\n批量计算完成: 总计 {total_records} 条因子记录")
    
    # 验证结果
    verify_results()

def verify_results():
    """验证计算结果"""
    print("\n=== 验证结果 ===")
    
    # 统计各指标因子数量
    stats = pd.read_sql("""
        SELECT 
            indicator_code,
            factor_type,
            COUNT(*) as cnt,
            MIN(publish_date) as start_date,
            MAX(publish_date) as end_date,
            ROUND(AVG(factor_value), 2) as mean_val,
            ROUND(MIN(factor_value), 2) as min_val,
            ROUND(MAX(factor_value), 2) as max_val
        FROM macro_factor_value
        GROUP BY indicator_code, factor_type
        ORDER BY indicator_code, factor_type
    """, engine)
    
    print(stats.to_string(index=False))
    
    # 检查是否有异常值超出[-3, 3]
    outliers = pd.read_sql("""
        SELECT indicator_code, publish_date, factor_type, factor_value
        FROM macro_factor_value
        WHERE ABS(factor_value) > 3.1
        LIMIT 10
    """, engine)
    
    if not outliers.empty:
        print("\n⚠️  发现异常值（应已被截断）:")
        print(outliers.to_string(index=False))
    else:
        print("\n✓ 无异常值（所有因子值在[-3, 3]范围内）")

if __name__ == '__main__':
    batch_compute_factors()
