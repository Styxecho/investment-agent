#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量提取指数历史价格数据并存入数据库

提取范围: 2025-12-31 至 2026-04-23
数据来源: iFinD
存储表: index_daily
"""

import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')

import pandas as pd
import sqlite3
from datetime import datetime
from skills.market_data.provider.ifind_provider import ifind_provider
from utils.logger import logger

# 配置
DB_PATH = r'D:\Study\Project\investment-agent\data_external\db\external_data.db'
START_DATE = '20251231'
END_DATE = '20260423'
BATCH_SIZE = 10  # 每批查询的指数数量


def get_index_codes():
    """读取指数代码列表"""
    with open(r'D:\Study\Project\investment-agent\scripts\index_codes.txt', 'r') as f:
        codes = [line.strip() for line in f if line.strip()]
    return codes


def format_index_code(code):
    """格式化指数代码，添加后缀"""
    # 根据代码前缀判断后缀
    if code.startswith('000') or code.startswith('880'):
        return f'{code}.SH'
    elif code.startswith('399'):
        return f'{code}.SZ'
    elif code.startswith('H') or code.startswith('h'):
        return f'{code}.CSI'
    elif code.startswith('93') or code.startswith('95') or code.startswith('98'):
        return f'{code}.CSI'
    else:
        return f'{code}.CSI'


def fetch_index_data_batch(codes_batch):
    """批量获取指数数据"""
    try:
        # 连接iFinD
        if not ifind_provider.connect():
            logger.error("iFinD connection failed")
            return None
        
        # 格式化代码
        formatted_codes = [format_index_code(code) for code in codes_batch]
        
        logger.info(f"Fetching data for: {', '.join(formatted_codes)}")
        
        # 获取数据
        df = ifind_provider.fetch_index_history(
            symbol=formatted_codes,
            start_date=START_DATE,
            end_date=END_DATE
        )
        
        return df
        
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        return None
    finally:
        ifind_provider.disconnect()


def save_to_database(df):
    """保存数据到数据库"""
    if df is None or df.empty:
        logger.warning("No data to save")
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    inserted = 0
    updated = 0
    
    try:
        for _, row in df.iterrows():
            index_code = row.get('scrt_code', '')
            trade_date = row.get('trade_date', '')
            pre_close = row.get('pre_close', None)
            close = row.get('close', None)
            
            if not index_code or not trade_date:
                continue
            
            # 转换日期格式
            if isinstance(trade_date, pd.Timestamp):
                trade_date = trade_date.strftime('%Y-%m-%d')
            elif isinstance(trade_date, str) and len(trade_date) == 8:
                trade_date = f'{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}'
            
            # 检查是否已存在
            cursor.execute(
                'SELECT id FROM index_daily WHERE index_code = ? AND trade_date = ?',
                (index_code, trade_date)
            )
            existing = cursor.fetchone()
            
            if existing:
                # 更新
                cursor.execute(
                    'UPDATE index_daily SET pre_close_price = ?, close_price = ? WHERE id = ?',
                    (pre_close, close, existing[0])
                )
                updated += 1
            else:
                # 插入
                cursor.execute(
                    'INSERT INTO index_daily (index_code, trade_date, pre_close_price, close_price) VALUES (?, ?, ?, ?)',
                    (index_code, trade_date, pre_close, close)
                )
                inserted += 1
        
        conn.commit()
        logger.info(f"Database updated: {inserted} inserted, {updated} updated")
        return inserted + updated
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to save data: {e}")
        return 0
    finally:
        conn.close()


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Starting index price data extraction")
    logger.info(f"Date range: {START_DATE} - {END_DATE}")
    logger.info("=" * 60)
    
    # 获取指数代码
    codes = get_index_codes()
    total_codes = len(codes)
    logger.info(f"Total {total_codes} indices to process")
    
    # 分批处理
    total_records = 0
    for i in range(0, total_codes, BATCH_SIZE):
        batch = codes[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total_codes + BATCH_SIZE - 1) // BATCH_SIZE
        
        logger.info(f"\nProcessing batch {batch_num}/{total_batches}: {batch}")
        
        # 获取数据
        df = fetch_index_data_batch(batch)
        
        if df is not None and not df.empty:
            logger.info(f"Retrieved {len(df)} records")
            # 保存到数据库
            records = save_to_database(df)
            total_records += records
        else:
            logger.warning(f"Batch {batch_num}: No data")
        
        # 短暂暂停，避免请求过快
        import time
        time.sleep(1)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Extraction complete. Total {total_records} records processed")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
