import csv
import shutil
from pathlib import Path
from collections import defaultdict

# 路径定义
src = Path('data_external/reference/etf_universe.csv')
v1 = Path('data_external/reference/etf_universe_v1.csv')
v2 = Path('data_external/reference/etf_universe_v2.csv')

# 备份原文件
shutil.copy(src, v1)

# 表头映射：原始索引 -> (新字段名, 清洗函数)
def clean_numeric(val):
    """去除千分位逗号、空格，处理--和空值"""
    if val is None:
        return ''
    val = str(val).strip()
    if val in ['--', '-', '']:
        return ''
    # 去除千分位逗号
    val = val.replace(',', '')
    # 去除尾部空格
    val = val.strip()
    return val

def clean_text(val):
    if val is None:
        return ''
    return str(val).strip()

header_map = {
    0: ('code', clean_text),
    1: ('name', clean_text),
    2: ('index_code', clean_text),
    3: ('index_name', clean_text),
    4: ('fund_size', clean_numeric),       # 基金规模 亿元
    5: ('tracking_error', clean_numeric),  # 年跟踪误差
    6: ('daily_turnover', clean_numeric),  # 年日均成交量 亿元
    7: ('mgmt_fee', clean_numeric),        # 管理费率 %
    8: ('custody_fee', clean_numeric),     # 托管费率 %
    9: ('total_fee', clean_numeric),       # 费率
    10: ('asset_class_l1', clean_text),    # 大类资产_L1
    11: ('asset_class_l2', clean_text),    # 大类资产_L2
    12: ('sector_l1', clean_text),         # 行业主题_L1
    13: ('sector_l2', clean_text),         # 行业主题_L2
    14: ('market_cap_label', clean_text),  # 规模（大盘/中盘/小盘等）
    15: ('strategy_style', clean_text),    # 策略风格
}

def infer_size_style(row):
    """根据多字段推断市值风格定位"""
    name = str(row[1])
    index_name = str(row[3])
    asset_l2 = str(row[11])
    market_cap = str(row[14])
    strategy = str(row[15])
    asset_l1 = str(row[10])
    
    # 债券、商品、货币
    if asset_l1 == '债券':
        if '短融' in name or '短融' in index_name:
            return '短久期信用'
        elif '0-4年' in name or '0-3年' in name or '1-3年' in name or '2-5年' in name:
            return '短久期利率'
        elif '5年' in name or '5-10年' in name or '7-10年' in name:
            return '中久期利率'
        elif '10年' in name or '30年' in name:
            return '长久期利率'
        elif '可转债' in name:
            return '可转债'
        elif '信用债' in name or '公司债' in name or '城投债' in name:
            return '信用债'
        else:
            return '债券综合'
    elif asset_l1 == '商品':
        if '黄金' in name:
            return '黄金'
        elif '有色' in name:
            return '商品有色'
        elif '能源' in name or '化工' in name or '能化' in name:
            return '商品能化'
        elif '豆粕' in name:
            return '商品农产品'
        else:
            return '商品综合'
    elif asset_l1 == '货基':
        return '货币基金'
    
    # 股票类
    # 科创板
    if '科创50' in name or '科创50' in index_name:
        return '科创大盘'
    if '科创100' in name or '科创100' in index_name:
        return '科创中盘'
    if '科创200' in name or '科创200' in index_name:
        return '科创小盘'
    if '科创综指' in name or '科创板综合' in index_name or '上证科创板综合' in index_name:
        return '科创全市场'
    if '科创创业' in name or '双创' in name:
        return '科创创业'
    if '科创' in name and '信息' in name:
        return '科创信息'
    if '科创' in name and '芯片' in name:
        return '科创芯片'
    if '科创' in name and 'AI' in name or '科创' in name and '人工智能' in name:
        return '科创AI'
    if '科创' in name and '新能源' in name:
        return '科创新能源'
    if '科创' in name and '半导体' in name:
        return '科创芯片'
    if '科创' in name and '创新药' in name:
        return '科创医药'
    
    # 创业板
    if '创业板50' in name or '创业板50' in index_name:
        return '大盘成长'
    if '创业板' in name and ('中盘' in name or '中盘' in index_name):
        return '中盘成长'
    if '创业板' in name:
        return '大盘成长'
    
    # 宽基指数
    if '上证50' in name or '上证50' in index_name or '上证180' in name:
        return '大盘'
    if '沪深300' in name or '沪深300' in index_name:
        if '价值' in strategy or '价值' in name:
            return '大盘价值'
        elif '成长' in strategy or '成长' in name:
            return '大盘成长'
        else:
            return '大盘'
    if '中证A50' in name or '中证A50' in index_name:
        return '大盘'
    if '中证A500' in name or '中证A500' in index_name or 'A500' in name:
        return '大中盘'
    if '中证800' in name or '中证800' in index_name:
        return '大中盘'
    if '中证500' in name or '中证500' in index_name:
        if '价值' in strategy or '价值' in name:
            return '中盘价值'
        elif '成长' in strategy or '成长' in name:
            return '中盘成长'
        else:
            return '中盘'
    if '中证1000' in name or '中证1000' in index_name:
        if '价值' in strategy or '价值' in name:
            return '小盘价值'
        elif '成长' in strategy or '成长' in name:
            return '小盘成长'
        else:
            return '中小盘'
    if '中证2000' in name or '中证2000' in index_name:
        return '小盘'
    if '深证100' in name or '深证100' in index_name:
        return '大盘'
    if 'MSCI' in name or 'MSCI' in index_name:
        return '全市场'
    if '基本面' in name and ('60' in name or '120' in name):
        return '大盘' if '120' in name else '中盘'
    
    # 港股
    if asset_l2 == '港股宽基' or '港股' in name:
        if '恒生' in name and '科技' not in name and '互联网' not in name and '消费' not in name and '医药' not in name and '汽车' not in name:
            return '港股大盘'
        elif '国企' in name or '央企' in name:
            return '港股大盘'
        else:
            return '港股主题'
    
    # 海外
    if asset_l2 == '海外宽基':
        if '纳指' in name or '纳斯达克' in index_name:
            return '纳斯达克'
        if '标普' in name or '标普500' in index_name or 'S&P' in index_name:
            return '标普500'
        if '日经' in name or '日本' in name or '东证' in name:
            return '日本股市'
        if '巴西' in name or 'IBOV' in index_name:
            return '新兴市场'
        return '海外市场'
    
    # 策略风格（Smart Beta）
    if asset_l2 == '策略风格':
        # 先判断市值
        size_hint = ''
        if '沪深300' in name or '上证180' in name or '深证300' in name or '大盘' in name:
            size_hint = '大盘'
        elif '中证500' in name or '中盘' in name:
            size_hint = '中盘'
        elif '中证1000' in name or '小盘' in name:
            size_hint = '小盘'
        elif '创业板' in name:
            size_hint = '大盘'
        elif '科创' in name:
            size_hint = '科创大盘'
        elif '全市场' in market_cap or '全市场' in name:
            size_hint = '全市场'
        elif '港股' in name:
            size_hint = '港股'
        else:
            size_hint = '全市场'
        
        # 再判断风格
        style_hint = ''
        if '红利' in strategy or '红利' in name:
            style_hint = '红利'
        elif '低波' in strategy or '低波' in name:
            style_hint = '低波'
        elif '价值' in strategy or '价值' in name:
            style_hint = '价值'
        elif '成长' in strategy or '成长' in name:
            style_hint = '成长'
        elif '质量' in strategy or '质量' in name:
            style_hint = '质量'
        elif '基本面' in strategy or '基本面' in name:
            style_hint = '基本面'
        elif '现金流' in strategy or '现金流' in name:
            style_hint = '现金流'
        elif '央国企' in strategy or '央企' in name or '国企' in name:
            style_hint = '央国企'
        elif '动量' in strategy or '动量' in name:
            style_hint = '动量'
        
        if size_hint and style_hint:
            return f'{size_hint}{style_hint}'
        elif style_hint:
            return style_hint
        else:
            return size_hint if size_hint else '全市场'
    
    # 行业主题
    if asset_l2 == '行业主题':
        # 港股行业主题
        if '港股' in name or '恒生' in name:
            return '港股主题'
        # 海外行业主题
        if '纳指' in name or '标普' in name:
            return '海外主题'
        # A股行业主题，暂时用market_cap_label或空值
        if market_cap and market_cap not in ['', 'NA']:
            return market_cap
        return ''
    
    return ''


def infer_pool_role(row, group_max_size):
    """推断pool_role，基于同类规模最大原则"""
    code = str(row[0])
    name = str(row[1])
    asset_l1 = str(row[10])
    asset_l2 = str(row[11])
    size_style = infer_size_style(row)
    
    # 货币和货基
    if asset_l1 == '货基':
        if code == group_max_size.get(('货基', '货币基金'), ''):
            return 'core'
        return 'satellite'
    
    # 债券
    if asset_l1 == '债券':
        if size_style == '短久期信用' and code == group_max_size.get(('债券', '短久期信用'), ''):
            return 'core'
        if size_style == '短久期利率' and code == group_max_size.get(('债券', '短久期利率'), ''):
            return 'core'
        if size_style == '中久期利率' and code == group_max_size.get(('债券', '中久期利率'), ''):
            return 'core'
        if size_style == '长久期利率' and code == group_max_size.get(('债券', '长久期利率'), ''):
            return 'core'
        if size_style == '信用债' and code == group_max_size.get(('债券', '信用债'), ''):
            return 'satellite'
        if size_style == '可转债' and code == group_max_size.get(('债券', '可转债'), ''):
            return 'satellite'
        return 'extended'
    
    # 商品
    if asset_l1 == '商品':
        if size_style == '黄金' and code == group_max_size.get(('商品', '黄金'), ''):
            return 'core'
        return 'satellite'
    
    # 股票类
    if asset_l1 == '股票':
        # 核心池候选
        core_candidates = [
            (('股票', '宽基', '大盘'), 'core'),
            (('股票', '宽基', '中盘'), 'core'),
            (('股票', '宽基', '中小盘'), 'core'),
            (('股票', '宽基', '小盘'), 'core'),
            (('股票', '宽基', '科创大盘'), 'core'),
            (('股票', '宽基', '科创中盘'), 'satellite'),  # 备选，先放satellite
            (('股票', '港股宽基', '港股大盘'), 'core'),
            (('股票', '海外宽基', '纳斯达克'), 'core'),
            (('股票', '海外宽基', '标普500'), 'core'),
            (('股票', '海外宽基', '日本股市'), 'satellite'),
        ]
        
        for key, role in core_candidates:
            if code == group_max_size.get(key, ''):
                return role
        
        # 策略风格中，部分可作为核心备选（如大盘红利）
        strategy_core = [
            (('股票', '策略风格', '大盘红利'), 'satellite'),
            (('股票', '策略风格', '中盘红利'), 'satellite'),
        ]
        for key, role in strategy_core:
            if code == group_max_size.get(key, ''):
                return role
        
        # 行业主题和其余策略风格归入卫星池
        if asset_l2 in ['行业主题', '策略风格', '港股宽基']:
            return 'satellite'
        
        return 'extended'
    
    return 'extended'


# 读取原始数据
rows = []
with open(src, 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    original_header = next(reader)
    for row in reader:
        rows.append(row)

print(f"Total rows: {len(rows)}")

# 第一步：为所有行推断size_style
for row in rows:
    size_style = infer_size_style(row)
    row.append(size_style)

# 第二步：按组合键分组，找出每组规模最大的ETF
def parse_size(val):
    try:
        val = str(val).replace(',', '').strip()
        return float(val)
    except:
        return 0.0

group_max_size = {}

# 定义分组键的优先级
for row in rows:
    code = str(row[0])
    asset_l1 = str(row[10])
    asset_l2 = str(row[11])
    size_style = row[16]  # 刚添加的size_style
    fund_size = parse_size(row[4])
    
    # 多种分组键
    keys = []
    
    if asset_l1 == '货基':
        keys.append(('货基', size_style))
    elif asset_l1 == '债券':
        keys.append((asset_l1, size_style))
    elif asset_l1 == '商品':
        keys.append((asset_l1, size_style))
    elif asset_l1 == '股票':
        if asset_l2 == '宽基':
            keys.append((asset_l1, asset_l2, size_style))
        elif asset_l2 == '港股宽基':
            keys.append((asset_l1, asset_l2, size_style))
        elif asset_l2 == '海外宽基':
            keys.append((asset_l1, asset_l2, size_style))
        elif asset_l2 == '策略风格':
            keys.append((asset_l1, asset_l2, size_style))
        elif asset_l2 == '行业主题':
            # 行业主题按sector_l2 + size_style分组
            sector_l2 = str(row[13])
            keys.append((asset_l1, asset_l2, sector_l2))
    
    for key in keys:
        if key not in group_max_size or fund_size > parse_size(group_max_size[key][1]):
            group_max_size[key] = (code, row[4])
        elif fund_size == parse_size(group_max_size[key][1]):
            # 规模相同，选代码字典序小的（稳定排序）
            if code < group_max_size[key][0]:
                group_max_size[key] = (code, row[4])

# 简化为只保留code
group_max_size = {k: v[0] for k, v in group_max_size.items()}

# 第三步：标记pool_role
for row in rows:
    pool_role = infer_pool_role(row, group_max_size)
    row.append(pool_role)

# 写入v2
new_header = [header_map[i][0] for i in range(16)] + ['size_style', 'pool_role']

with open(v2, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(new_header)
    for row in rows:
        # 清洗原有16个字段
        cleaned = []
        for i in range(16):
            cleaner = header_map[i][1]
            cleaned.append(cleaner(row[i]))
        # 添加size_style和pool_role
        cleaned.extend([row[16], row[17]])
        writer.writerow(cleaned)

# 统计
core_count = sum(1 for r in rows if r[17] == 'core')
satellite_count = sum(1 for r in rows if r[17] == 'satellite')
extended_count = sum(1 for r in rows if r[17] == 'extended')

print(f"V2 generated: {v2}")
print(f"Core: {core_count}, Satellite: {satellite_count}, Extended: {extended_count}")
print(f"Total: {len(rows)}")

# 打印核心池名单
print("\nCore pool candidates:")
for row in rows:
    if row[17] == 'core':
        print(f"  {row[0]} {row[1]} | size_style={row[16]} | fund_size={row[4]}")
