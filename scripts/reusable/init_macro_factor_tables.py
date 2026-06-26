#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase A: 创建宏观因子数据库表
- macro_factor_value: 存储计算后的因子值
- macro_factor_config: 每个指标的计算配置
"""

import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')

from data_external.db.engine import engine
from sqlalchemy import text

def create_macro_factor_tables():
    """创建宏观因子相关表"""
    
    # 1. 创建 macro_factor_value 表
    create_factor_value_sql = """
    CREATE TABLE IF NOT EXISTS macro_factor_value (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator_code VARCHAR(50) NOT NULL,
        publish_date VARCHAR(8) NOT NULL,
        factor_type VARCHAR(20) NOT NULL,
        factor_value DECIMAL(10,4),
        raw_value DECIMAL(18,4),
        cycle_value DECIMAL(18,4),
        trend_value DECIMAL(18,4),
        zscore_window INTEGER,
        filter_method VARCHAR(30),
        filter_params VARCHAR(100),
        is_winsorized BOOLEAN DEFAULT 0,
        data_source VARCHAR(20) DEFAULT 'computed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(indicator_code, publish_date, factor_type),
        CHECK (factor_type IN ('level', 'change'))
    )
    """
    
    # 2. 创建索引（SQLite需要单独执行）
    create_index_date_sql = "CREATE INDEX IF NOT EXISTS idx_factor_date ON macro_factor_value(publish_date)"
    create_index_code_sql = "CREATE INDEX IF NOT EXISTS idx_factor_code ON macro_factor_value(indicator_code)"
    create_index_type_sql = "CREATE INDEX IF NOT EXISTS idx_factor_type ON macro_factor_value(factor_type)"
    
    # 3. 创建 macro_factor_config 表
    create_factor_config_sql = """
    CREATE TABLE IF NOT EXISTS macro_factor_config (
        indicator_code VARCHAR(50) PRIMARY KEY,
        filter_type VARCHAR(30) DEFAULT 'one_sided_hp',
        filter_params VARCHAR(100) DEFAULT '{"lamb": 14400}',
        level_window INTEGER DEFAULT 36,
        change_window INTEGER DEFAULT 48,
        winsorize_threshold DECIMAL(4,2) DEFAULT 3.0,
        min_periods_for_zscore INTEGER DEFAULT 12,
        hp_warmup_months INTEGER DEFAULT 18,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_factor_value_sql))
        conn.execute(text(create_index_date_sql))
        conn.execute(text(create_index_code_sql))
        conn.execute(text(create_index_type_sql))
        conn.execute(text(create_factor_config_sql))
        conn.commit()
    
    print("[OK] 宏观因子表创建成功")

def init_factor_config():
    """初始化指标配置（16个指标）"""
    
    configs = [
        ('CN_PMI_MFG_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_PMI_SVC_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_PMI_COMP_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_IAV_YOY_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_CPI_YOY_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_PPI_YOY_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_NHCCI_D', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_M2_YOY_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_M1_YOY_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_M0_YOY_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_SFS_YOY_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_TREASURY_BOND_10Y_D', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_FX_USDCNY_MID_D', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_DR007_D', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_DXY_D', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
        ('CN_IIV_YOY_M', 'one_sided_hp', '{"lamb": 14400}', 36, 48, 3.0, 12, 18, 1),
    ]
    
    insert_sql = """
    INSERT OR REPLACE INTO macro_factor_config 
    (indicator_code, filter_type, filter_params, level_window, change_window, 
     winsorize_threshold, min_periods_for_zscore, hp_warmup_months, is_active)
    VALUES (:code, :ftype, :fparams, :lwin, :cwin, :wthresh, :minp, :warmup, :active)
    """
    
    with engine.connect() as conn:
        for config in configs:
            conn.execute(text(insert_sql), {
                'code': config[0],
                'ftype': config[1],
                'fparams': config[2],
                'lwin': config[3],
                'cwin': config[4],
                'wthresh': config[5],
                'minp': config[6],
                'warmup': config[7],
                'active': config[8]
            })
        conn.commit()
    
    print(f"[OK] 已初始化 {len(configs)} 个指标配置")

def verify_tables():
    """验证表创建结果"""
    import pandas as pd
    
    print("\n=== 表结构验证 ===")
    
    # 检查 macro_factor_value 表
    df = pd.read_sql("SELECT COUNT(*) as cnt FROM macro_factor_value", engine)
    print(f"macro_factor_value: {df.iloc[0]['cnt']} 条记录")
    
    # 检查 macro_factor_config 表
    df = pd.read_sql("SELECT * FROM macro_factor_config LIMIT 5", engine)
    print(f"\nmacro_factor_config 样本:")
    print(df.to_string(index=False))
    
    # 检查索引
    df = pd.read_sql("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='macro_factor_value'", engine)
    print(f"\nmacro_factor_value 索引:")
    print(df.to_string(index=False))

if __name__ == '__main__':
    print("=== Phase A: 创建宏观因子数据库表 ===\n")
    
    create_macro_factor_tables()
    init_factor_config()
    verify_tables()
    
    print("\n=== Phase A 完成 ===")
