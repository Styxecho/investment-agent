"""
国证指数成分股权重批量下载脚本

使用方法:
1. 修改 index_list 中的指数代码列表
2. 运行脚本: python download_guozheng_indices.py
3. 文件将保存到 D:\Study\Research\ETF\csindex\ 目录

作者: AI Assistant
日期: 2026-04-22
"""

import requests
import pandas as pd
import io
import os
import time
from datetime import datetime

# 配置
DOWNLOAD_DIR = r'D:\Study\Research\ETF\csindex'
BASE_URL = 'https://www.cnindex.com.cn/sample-detail/download-history'

# 需要下载的国证指数列表
# 格式: (指数代码, 指数名称)
GUOZHENG_INDICES = [
    # 科技板块
    ('980017', '国证半导体芯片指数'),
    ('980018', '国证商用卫星通信产业指数'),
    ('980022', '国证机器人产业指数'),
    
    # 制造板块
    ('980027', '国证新能源电池指数'),
    ('980032', '国证新能源车电池指数'),
    ('980076', '国证通用航空产业指数'),
    
    # 消费板块
    ('980030', '国证消费电子主题指数'),
]

# 其他可能需要下载的国证指数（请根据实际情况补充）
ADDITIONAL_INDICES = [
    # 如果还有其他国证指数需要下载，请在这里添加
    # ('399264', '创业板软件指数'),  # 注意：399开头是深圳证券交易所指数，不是国证
]


def download_index_components(index_code, index_name, output_dir):
    """
    下载单个指数的成分股权重数据
    
    Args:
        index_code: 指数代码
        index_name: 指数名称
        output_dir: 保存目录
    
    Returns:
        bool: 是否成功
    """
    url = f'{BASE_URL}?indexcode={index_code}'
    
    try:
        print(f'正在下载 {index_code} {index_name}...')
        
        # 发送请求
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # 检查返回内容是否为Excel文件
        content_length = len(response.content)
        if content_length < 1000:
            print(f'  [警告] 文件太小 ({content_length} bytes)，可能不是有效数据')
            return False
        
        # 尝试读取Excel验证内容
        try:
            df = pd.read_excel(io.BytesIO(response.content))
            if len(df) == 0:
                print(f'  [警告] Excel文件为空')
                return False
            
            # 检查必要的列
            required_cols = ['样本代码', '权重（%）']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                print(f'  [警告] 缺少列: {missing_cols}')
                print(f'  实际列名: {df.columns.tolist()}')
                # 继续保存，但标记为需检查
        except Exception as e:
            print(f'  [警告] 无法读取Excel: {str(e)}')
            # 仍然保存原始文件
        
        # 保存文件
        filename = f'{index_code}_{index_name}_index_weight.xls'
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        print(f'  [成功] 已保存到 {filename} ({content_length} bytes)')
        return True
        
    except requests.exceptions.RequestException as e:
        print(f'  [失败] 网络错误: {str(e)}')
        return False
    except Exception as e:
        print(f'  [失败] 错误: {str(e)}')
        return False


def batch_download(indices_list, output_dir, delay=2):
    """
    批量下载指数成分股数据
    
    Args:
        indices_list: 指数列表 [(code, name), ...]
        output_dir: 保存目录
        delay: 下载间隔（秒），避免请求过快
    """
    print('=' * 60)
    print('国证指数成分股权重批量下载')
    print('=' * 60)
    print(f'下载目录: {output_dir}')
    print(f'指数数量: {len(indices_list)}')
    print(f'下载间隔: {delay}秒')
    print('=' * 60)
    print()
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 统计
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for i, (code, name) in enumerate(indices_list, 1):
        print(f'[{i}/{len(indices_list)}] ', end='')
        
        # 检查文件是否已存在
        filename = f'{code}_{name}_index_weight.xls'
        filepath = os.path.join(output_dir, filename)
        
        if os.path.exists(filepath):
            print(f'{code} {name}')
            print(f'  [跳过] 文件已存在')
            skip_count += 1
            continue
        
        # 下载
        if download_index_components(code, name, output_dir):
            success_count += 1
        else:
            fail_count += 1
        
        # 间隔等待
        if i < len(indices_list):
            time.sleep(delay)
    
    # 打印统计
    print()
    print('=' * 60)
    print('下载完成！')
    print('=' * 60)
    print(f'成功: {success_count}')
    print(f'失败: {fail_count}')
    print(f'跳过: {skip_count}')
    print(f'总计: {len(indices_list)}')
    print('=' * 60)


def verify_downloaded_files(output_dir):
    """
    验证已下载的文件
    """
    print()
    print('=' * 60)
    print('验证已下载的文件')
    print('=' * 60)
    
    files = [f for f in os.listdir(output_dir) if f.endswith('_index_weight.xls')]
    files.sort()
    
    print(f'找到 {len(files)} 个指数权重文件\n')
    
    for filename in files:
        filepath = os.path.join(output_dir, filename)
        try:
            df = pd.read_excel(filepath)
            code = filename.split('_')[0]
            name = filename.split('_')[1]
            print(f'{code} {name}: {len(df)}只成分股')
        except Exception as e:
            print(f'{filename}: [错误] {str(e)}')


if __name__ == '__main__':
    # 合并所有需要下载的指数
    all_indices = GUOZHENG_INDICES + ADDITIONAL_INDICES
    
    # 执行批量下载
    batch_download(all_indices, DOWNLOAD_DIR, delay=2)
    
    # 验证已下载的文件
    verify_downloaded_files(DOWNLOAD_DIR)
    
    print()
    print('提示:')
    print('1. 如果某些指数下载失败，请检查指数代码是否正确')
    print('2. 可以在 ADDITIONAL_INDICES 列表中添加更多指数')
    print('3. 文件保存在:', DOWNLOAD_DIR)
