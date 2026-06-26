#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导入指数数据到index_daily表
"""
import pandas as pd
import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
from sqlalchemy import text

# 读取CSV，跳过前3行
file_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\index_data.csv'

# 读取列名（第4行）和代码（第5行）
with open(file_path, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

# 解析列名
col_names_line = lines[3].strip().split(',')
code_names_line = lines[4].strip().split(',')

# 找出前收盘价和收盘价的分界点
split_idx = col_names_line.index('')
print(f"前收盘价列数: {split_idx}")
print(f"总列数: {len(col_names_line)}")

# 读取前收盘价数据（第6行起，到split_idx列）
pre_close_data = []
close_data = []

for line in lines[5:]:
    parts = line.strip().split(',')
    if len(parts) < 10:
        continue
    
    # 前收盘价部分（列0到split_idx-1）
    pre_row = parts[:split_idx]
    pre_close_data.append(pre_row)
    
    # 收盘价部分（列split_idx+1起）
    close_row = parts[split_idx+1:split_idx+1+split_idx]
    close_data.append(close_row)

# 创建DataFrame
pre_close_cols = code_names_line[:split_idx]
close_cols = code_names_line[split_idx+1:split_idx+1+split_idx]

df_pre = pd.DataFrame(pre_close_data, columns=pre_close_cols)
df_close = pd.DataFrame(close_data, columns=close_cols)

print(f"前收盘价数据: {len(df_pre)} 行")
print(f"收盘价数据: {len(df_close)} 行")

# 转换日期列
df_pre['Date'] = pd.to_datetime(df_pre['Date'])
df_close['Date'] = pd.to_datetime(df_close['Date'])

# 转换数值列（排除Date列）
index_codes = [c for c in pre_close_cols if c != 'Date']
print(f"指数数量: {len(index_codes)}")
print(f"指数列表: {index_codes}")

for code in index_codes:
    df_pre[code] = pd.to_numeric(df_pre[code], errors='coerce')
    df_close[code] = pd.to_numeric(df_close[code], errors='coerce')

# 合并为长格式
records = []
for code in index_codes:
    for i in range(len(df_pre)):
        date = df_pre['Date'].iloc[i]
        pre_close = df_pre[code].iloc[i]
        close = df_close[code].iloc[i]
        
        if pd.notna(pre_close) and pd.notna(close):
            records.append({
                'index_code': code,
                'trade_date': date.strftime('%Y%m%d'),
                'pre_close_price': float(pre_close),
                'close_price': float(close)
            })

df_import = pd.DataFrame(records)
print(f"\n导入记录数: {len(df_import)}")

# 保存到CSV验证
df_import.to_csv(r'D:\Study\Project\investment-agent\docs\research\macro_analysis\index_import_preview.csv', 
                 index=False, encoding='utf-8-sig')
print("预览文件已保存")

# 插入数据库
with engine.connect() as conn:
    # 清空现有index_daily数据（可选，根据需求）
    # conn.execute(text("DELETE FROM index_daily"))
    
    # 插入数据
    for _, row in df_import.iterrows():
        conn.execute(text("""
            INSERT INTO index_daily (index_code, trade_date, pre_close_price, close_price)
            VALUES (:code, :date, :pre_close, :close)
        """), {
            'code': row['index_code'],
            'date': row['trade_date'],
            'pre_close': row['pre_close_price'],
            'close': row['close_price']
        })
    
    conn.commit()

print("\n数据导入完成！")

# 验证
verify_sql = """
SELECT index_code, MIN(trade_date) as start, MAX(trade_date) as end, COUNT(*) as rows
FROM index_daily 
GROUP BY index_code
ORDER BY index_code
"""
df_verify = pd.read_sql(verify_sql, engine)
print("\n导入验证:")
print(df_verify.to_string(index=False))

print(f"\n总记录数: {df_verify['rows'].sum()}")
print(f"指数数量: {len(df_verify)}")
