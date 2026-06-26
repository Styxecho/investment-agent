#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重新计算PMI因子（减50处理）和新增M1M2剪刀差因子
"""

import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')

from skills.macro_factor.pipeline import MacroFactorPipeline
from data_external.db.engine import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def recompute_pmi_factors():
    """重新计算PMI因子（使用subtract_baseline=50）"""
    pipeline = MacroFactorPipeline()
    
    pmi_codes = ['CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M']
    
    for code in pmi_codes:
        logger.info(f"重新计算 {code} (subtract_baseline=50)")
        
        # 删除旧的因子数据
        with engine.connect() as conn:
            conn.execute(text('DELETE FROM macro_factor_value WHERE indicator_code = :code'), {'code': code})
            conn.commit()
        
        # 重新计算
        count = pipeline.run(code, '20150101', '20241231')
        logger.info(f"{code}: 存储 {count} 条新因子记录")

def compute_m1m2_scissor():
    """计算M1-M2剪刀差因子"""
    pipeline = MacroFactorPipeline()
    
    logger.info("计算 CN_M1M2_DIFF_M (M1-M2剪刀差)")
    
    # 删除旧数据（如果有）
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM macro_indicator_value WHERE indicator_code = 'CN_M1M2_DIFF_M'"))
        conn.execute(text("DELETE FROM macro_factor_value WHERE indicator_code = 'CN_M1M2_DIFF_M'"))
        conn.commit()
    
    # 计算因子
    count = pipeline.run('CN_M1M2_DIFF_M', '20150101', '20241231')
    logger.info(f"CN_M1M2_DIFF_M: 存储 {count} 条因子记录")

if __name__ == '__main__':
    print("=== 重新计算PMI因子和新增剪刀差因子 ===\n")
    
    recompute_pmi_factors()
    print()
    compute_m1m2_scissor()
    
    print("\n=== 验证 ===")
    import pandas as pd
    
    # 验证PMI因子
    df = pd.read_sql("""
        SELECT indicator_code, publish_date, factor_type, factor_value
        FROM macro_factor_value
        WHERE indicator_code IN ('CN_PMI_MFG_M', 'CN_PMI_SVC_M', 'CN_PMI_COMP_M')
          AND publish_date IN ('20160229', '20161231', '20170228', '20171231')
        ORDER BY indicator_code, publish_date, factor_type
    """, engine)
    print("\nPMI因子关键时点验证:")
    print(df.to_string(index=False))
    
    # 验证剪刀差
    df2 = pd.read_sql("""
        SELECT indicator_code, publish_date, factor_type, factor_value
        FROM macro_factor_value
        WHERE indicator_code = 'CN_M1M2_DIFF_M'
          AND publish_date IN ('20160229', '20161231', '20170228', '20171231', '20200331', '20211031')
        ORDER BY publish_date, factor_type
    """, engine)
    print("\nM1M2剪刀差关键时点验证:")
    print(df2.to_string(index=False))
    
    print("\n=== 完成 ===")
