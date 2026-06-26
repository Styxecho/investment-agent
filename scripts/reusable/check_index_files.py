import pandas as pd
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 检查所有指数权重文件的完整性
check_dir = 'D:/Study/Research/ETF/csindex'

print('指数权重文件完整性检查')
print('=' * 80)
print()

files = [f for f in os.listdir(check_dir) if 'index_weight' in f]
files.sort()

valid_files = []
invalid_files = []
empty_files = []

for filename in files:
    filepath = os.path.join(check_dir, filename)
    file_size = os.path.getsize(filepath)
    
    # 检查文件大小
    if file_size < 1000:
        empty_files.append((filename, file_size))
        continue
    
    # 尝试读取文件
    try:
        # 尝试不同的引擎
        df = None
        for engine in [None, 'openpyxl', 'xlrd']:
            try:
                if engine:
                    df = pd.read_excel(filepath, engine=engine)
                else:
                    df = pd.read_excel(filepath)
                break
            except:
                continue
        
        if df is None:
            invalid_files.append((filename, file_size, '无法读取'))
            continue
            
        # 检查是否有数据
        if len(df) == 0:
            empty_files.append((filename, file_size))
            continue
        
        # 检查必要的列
        required_cols = ['样本代码', '权重']
        has_code = any('代码' in str(col) or 'code' in str(col).lower() for col in df.columns)
        has_weight = any('权重' in str(col) or 'weight' in str(col).lower() for col in df.columns)
        
        if not has_code:
            invalid_files.append((filename, file_size, '缺少代码列'))
            continue
        
        if not has_weight:
            invalid_files.append((filename, file_size, '缺少权重列'))
            continue
        
        # 检查权重数据是否有效
        weight_col = [col for col in df.columns if '权重' in str(col) or 'weight' in str(col).lower()][0]
        valid_weights = df[weight_col].dropna()
        
        if len(valid_weights) == 0:
            empty_files.append((filename, file_size))
            continue
        
        # 检查权重格式（应该是0-100之间的数值）
        sample_weight = valid_weights.iloc[0]
        if isinstance(sample_weight, (int, float)):
            if sample_weight > 1:  # 百分比格式（如0.383表示0.383%）
                weight_format = '百分比(%)'
            else:  # 小数格式（如0.00383）
                weight_format = '小数'
        else:
            weight_format = '未知'
        
        valid_files.append({
            'filename': filename,
            'size': file_size,
            'rows': len(df),
            'cols': len(df.columns),
            'weight_format': weight_format,
            'sample_weight': sample_weight
        })
        
    except Exception as e:
        invalid_files.append((filename, file_size, str(e)))

# 输出结果
print('检查结果汇总:')
print('-' * 80)
print('有效文件: %d个' % len(valid_files))
print('空文件: %d个' % len(empty_files))
print('损坏文件: %d个' % len(invalid_files))
print()

if empty_files:
    print('空文件列表（需要重新下载）:')
    for filename, size in empty_files:
        print('  %s (%d bytes)' % (filename, size))
    print()

if invalid_files:
    print('损坏/异常文件列表:')
    for filename, size, reason in invalid_files:
        print('  %s (%d bytes) - %s' % (filename, size, reason))
    print()

print('有效文件详情（前20个）:')
print('-' * 80)
for i, info in enumerate(valid_files[:20]):
    print('%s' % info['filename'])
    print('  大小: %d bytes, 行数: %d, 列数: %d' % (info['size'], info['rows'], info['cols']))
    print('  权重格式: %s, 示例: %s' % (info['weight_format'], info['sample_weight']))
    print()

print('=' * 80)
print('建议:')
if empty_files or invalid_files:
    print('1. 删除空文件和损坏文件')
    print('2. 重新下载这些指数的成分股权重数据')
    print('3. 对于中证指数(000/399开头)，尝试从中证官网下载')
    print('4. 对于国证指数(980开头)，尝试从国证官网下载')
else:
    print('所有文件检查通过！')
    print('权重格式统一为: %s' % valid_files[0]['weight_format'] if valid_files else '未知')

# 保存有效文件列表
valid_index_codes = [f['filename'].split('_')[0] for f in valid_files]
print()
print('有效指数代码数量: %d个' % len(set(valid_index_codes)))
