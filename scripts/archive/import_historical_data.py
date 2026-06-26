"""
导入A类和B类ETF历史数据到数据库
"""
import pandas as pd
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from data_external.db.repositories import MarketDataRepository

def parse_group_csv(file_path, skip_rows, etf_codes):
    """
    解析并排格式的Group CSV文件
    
    :param file_path: CSV文件路径
    :param skip_rows: 跳过的标题行数
    :param etf_codes: ETF代码列表
    :return: dict {etf_code: DataFrame}
    """
    # 读取CSV，不设置header
    df = pd.read_csv(file_path, skiprows=skip_rows, header=None)
    
    # 每只ETF占9列（Date, pre_close, open, high, low, close, volume, amt, adjfactor）
    # 后面跟一个空列作为分隔符（除了最后一只）
    etf_data = {}
    
    for i, code in enumerate(etf_codes):
        start_col = i * 10  # 9列数据 + 1列分隔符
        end_col = start_col + 9
        
        if end_col > len(df.columns):
            print(f"警告: {code} 的列范围超出文件列数")
            continue
        
        # 提取该ETF的数据
        etf_df = df.iloc[:, start_col:end_col].copy()
        etf_df.columns = ['trade_date', 'pre_close', 'open', 'high', 'low', 
                          'close', 'volume', 'amount', 'adjust_factor']
        
        # 转换日期格式
        etf_df['trade_date'] = pd.to_datetime(etf_df['trade_date'])
        
        # 去除空行（该ETF未上市期间的空数据）
        etf_df = etf_df.dropna(subset=['close'])
        
        if len(etf_df) > 0:
            etf_data[code] = etf_df
            print(f"{code}: {len(etf_df)} records")
        else:
            print(f"{code}: No valid data")
    
    return etf_data

def import_to_database(etf_data):
    """将ETF数据导入数据库"""
    total_records = 0
    
    for code, df in etf_data.items():
        if len(df) == 0:
            continue
        
        try:
            MarketDataRepository.save_daily_data(df, code)
            total_records += len(df)
            print(f"[OK] {code}: Imported {len(df)} records")
        except Exception as e:
            print(f"[ERR] {code}: Import failed - {e}")
    
    return total_records

def verify_import(etf_codes):
    """验证导入结果"""
    conn = sqlite3.connect('data_external/db/external_data.db')
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("导入验证")
    print("="*60)
    
    for code in etf_codes:
        cursor.execute('''
            SELECT MIN(trade_date), MAX(trade_date), COUNT(*) 
            FROM stock_daily 
            WHERE symbol = ?
        ''', (code,))
        min_date, max_date, count = cursor.fetchone()
        
        print(f"{code}: {count} 条记录 | {min_date} ~ {max_date}")
    
    conn.close()

def main():
    print("="*60)
    print("ETF历史数据导入")
    print("="*60)
    
    # A类ETF
    a_codes = ['510300.SH', '510500.SH', '512100.SH', '159920.SZ', 
               '510880.SH', '513100.SH', '513500.SH', '518880.SH']
    a_file = Path('data_external/reference/A Group.csv')
    
    print("\n[Parse] A Group...")
    a_data = parse_group_csv(a_file, 14, a_codes)
    
    # B类ETF
    b_codes = ['511260.SH', '512890.SH', '159972.SZ', '511360.SH', '588000.SH']
    b_file = Path('data_external/reference/B Group.csv')
    
    print("\n[Parse] B Group...")
    b_data = parse_group_csv(b_file, 11, b_codes)
    
    # 合并数据
    all_data = {**a_data, **b_data}
    
    # 导入数据库
    print("\n[Import] Database...")
    total = import_to_database(all_data)
    
    print(f"\n[Done] Total imported: {total} records")
    
    # 验证
    verify_import(a_codes + b_codes)
    
    print("\n" + "="*60)
    print("Import Complete!")
    print("="*60)

if __name__ == "__main__":
    main()
