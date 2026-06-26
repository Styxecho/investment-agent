import sqlite3
from datetime import datetime

conn = sqlite3.connect('data_external/db/external_data.db')
cursor = conn.cursor()

# 所有ETF
codes = [
    '510300.SH', '510500.SH', '512100.SH', '159531.SZ', '588000.SH',
    '159920.SZ', '513010.SH', '513100.SH', '513500.SH', '518880.SH',
    '511260.SH', '159972.SZ', '511360.SH',
    '510880.SH', '512890.SH', '159201.SZ', '561580.SH', '513920.SH', '159545.SZ'
]

code_to_name = {
    '510300.SH': '沪深300ETF华泰柏瑞', '510500.SH': '中证500ETF南方', 
    '512100.SH': '中证1000ETF南方', '159531.SZ': '中证2000ETF南方',
    '588000.SH': '科创50ETF华夏', '159920.SZ': '恒生ETF华夏',
    '513010.SH': '恒生科技ETF易方达', '513100.SH': '纳指ETF国泰',
    '513500.SH': '标普500ETF博时', '518880.SH': '黄金ETF华安',
    '511260.SH': '十年国债ETF国泰', '159972.SZ': '5年地方债ETF鹏华',
    '511360.SH': '短融ETF海富通', '510880.SH': '红利ETF华泰柏瑞',
    '512890.SH': '红利低波ETF华泰柏瑞', '159201.SZ': '自由现金流ETF华夏',
    '561580.SH': '央企红利ETF华泰柏瑞', '513920.SH': '港股通央企红利ETF华安',
    '159545.SZ': '恒生红利低波ETF易方达'
}

print('='*110)
print('缓存数据库ETF数据覆盖报告（2019-01-01起）')
print('='*110)
print(f'{"ETF代码":<15} {"ETF名称":<22} {"最早有效日期":<14} {"2019年数据":<12} {"2020年数据":<12} {"数据状态":<15}')
print('-'*110)

target_2019 = datetime(2019, 1, 1)

for code in codes:
    cursor.execute('''
        SELECT trade_date, close_price
        FROM stock_daily 
        WHERE symbol = ? AND close_price IS NOT NULL
        ORDER BY trade_date ASC LIMIT 1
    ''', (code,))
    first_record = cursor.fetchone()
    
    cursor.execute('''
        SELECT COUNT(*) 
        FROM stock_daily 
        WHERE symbol = ? AND close_price IS NOT NULL AND trade_date >= ? AND trade_date < ?
    ''', (code, '2019-01-01', '2020-01-01'))
    count_2019 = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT COUNT(*) 
        FROM stock_daily 
        WHERE symbol = ? AND close_price IS NOT NULL AND trade_date >= ? AND trade_date < ?
    ''', (code, '2020-01-01', '2021-01-01'))
    count_2020 = cursor.fetchone()[0]
    
    if first_record:
        first_date = first_record[0]
        dt = datetime.strptime(first_date, '%Y-%m-%d')
        
        if dt <= target_2019:
            status = '完整（2019年前已上市）'
        elif dt.year == 2019:
            status = f'2019年{dt.month}月上市'
        elif dt.year == 2020:
            status = f'2020年{dt.month}月上市'
        elif dt.year == 2021:
            status = f'2021年{dt.month}月上市'
        elif dt.year == 2023:
            status = f'2023年{dt.month}月上市'
        elif dt.year == 2024:
            status = f'2024年{dt.month}月上市'
        elif dt.year == 2025:
            status = f'2025年{dt.month}月上市'
        else:
            status = f'{dt.year}年上市'
    else:
        first_date = '无数据'
        status = '无数据'
    
    has_2019 = '有' if count_2019 > 0 else '无'
    has_2020 = '有' if count_2020 > 0 else '无'
    
    print(f'{code:<15} {code_to_name.get(code, ""):<22} {first_date:<14} {has_2019:<12} {has_2020:<12} {status:<15}')

print('='*110)

# 汇总
print()
print('汇总统计：')
print('-'*110)

# 完整覆盖2019年的ETF
cursor.execute('''
    SELECT symbol, MIN(trade_date) as first_date
    FROM stock_daily
    WHERE close_price IS NOT NULL
    GROUP BY symbol
    HAVING first_date <= '2019-01-01'
''')
complete_2019 = cursor.fetchall()

# 2019年后上市的ETF
cursor.execute('''
    SELECT symbol, MIN(trade_date) as first_date
    FROM stock_daily
    WHERE close_price IS NOT NULL
    GROUP BY symbol
    HAVING first_date > '2019-01-01'
    ORDER BY first_date
''')
incomplete_2019 = cursor.fetchall()

print(f'从2019年起数据完整的ETF：{len(complete_2019)} 只')
for code, first_date in complete_2019:
    print(f'  {code} {code_to_name.get(code, "")}: 最早数据 {first_date}')

print()
print(f'从2019年起数据缺失的ETF：{len(incomplete_2019)} 只')
for code, first_date in incomplete_2019:
    name = code_to_name.get(code, '')
    dt = datetime.strptime(first_date, '%Y-%m-%d')
    gap_days = (dt - target_2019).days
    print(f'  {code} {name}:')
    print(f'    最早有效数据日期: {first_date}')
    print(f'    距2019-01-01缺口: {gap_days} 天（约 {gap_days/365:.1f} 年）')
    print(f'    建议: 使用跟踪指数补齐2019-01-01 至 {first_date} 期间数据')

conn.close()
print()
print('='*110)
print('说明：')
print('1. "完整"表示该ETF在2019年前已上市，且数据库中有2019年起的数据')
print('2. 当前数据库中0值已转换为NULL，未上市期间不再显示虚假数据')
print('3. 由于iFinD试用账号限制（1年历史数据），无法拉取2019-2020年数据')
print('4. 需要升级iFinD正式账号后才能补齐2019-2021年的历史数据')
print('='*110)
