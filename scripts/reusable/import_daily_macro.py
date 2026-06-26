#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导入日频宏观数据（修复版）"""

import pandas as pd
import sys

sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine

def import_daily_data():
    daily_file = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_indicators_history_series_daily.csv'
    df = pd.read_csv(daily_file, encoding='utf-8-sig', header=None)
    
    # Row index 3 has Chinese column names
    # Row index 4 has English codes
    col_names = df.iloc[3, :].tolist()
    
    print("原始列名:")
    for i, name in enumerate(col_names):
        if pd.notna(name) and str(name).strip():
            print(f"  列{i}: {name}")
    
    # 明确映射（基于已知列结构）
    col_mapping = {
        1: 'CN_NHCCI_D',      # 南华商品指数
        2: 'CN_FX_USDCNY_MID_D',  # 中间价:美元兑人民币
        3: 'CN_DR007_D',      # 中国:银行间质押式回购加权利率:7天
        4: 'CN_TREASURY_BOND_10Y_D',  # 中债国债到期收益率:10年
    }
    
    # 数据从index 5开始
    data_df = df.iloc[5:, [0, 1, 2, 3, 4]].copy()
    data_df.columns = ['date', 'col_1', 'col_2', 'col_3', 'col_4']
    
    # 转换日期
    data_df['date'] = pd.to_datetime(data_df['date'], errors='coerce')
    data_df = data_df.dropna(subset=['date'])
    data_df['date'] = data_df['date'].dt.strftime('%Y%m%d')
    
    # 构建记录
    records = []
    for col_idx, indicator_code in col_mapping.items():
        col_name = f'col_{col_idx}'
        count = 0
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
                    count += 1
                except:
                    pass
        print(f"  {indicator_code}: {count} 条记录")
    
    if records:
        value_df = pd.DataFrame(records)
        value_df.to_sql('macro_indicator_value', engine, if_exists='append', index=False)
        print(f"\n[OK] 导入 {len(records)} 条日频数据")
    else:
        print("[WARN] 未找到日频数据")

if __name__ == '__main__':
    import_daily_data()
