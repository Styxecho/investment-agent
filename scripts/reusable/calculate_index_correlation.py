#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
计算指数收益率相关性矩阵

输入: index_daily表中的价格数据（2025-12-31之后）
输出: 收益率相关性矩阵，用于双维度聚类
"""

import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')

import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime

# 配置
DB_PATH = r'D:\Study\Project\investment-agent\data_external\db\external_data.db'
START_DATE = '2025-12-31'


def load_index_data():
    """从数据库加载指数价格数据"""
    conn = sqlite3.connect(DB_PATH)
    
    query = f"""
    SELECT index_code, trade_date, close_price
    FROM index_daily
    WHERE trade_date >= '{START_DATE}'
    AND close_price IS NOT NULL
    ORDER BY index_code, trade_date
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"加载数据: {len(df)} 条记录")
    print(f"指数数量: {df['index_code'].nunique()}")
    print(f"日期范围: {df['trade_date'].min()} 至 {df['trade_date'].max()}")
    
    return df


def calculate_returns(df):
    """计算日收益率"""
    # 转换日期格式
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    
    # 按指数分组计算收益率
    returns_list = []
    
    for index_code, group in df.groupby('index_code'):
        group = group.sort_values('trade_date')
        group['daily_return'] = group['close_price'].pct_change()
        returns_list.append(group[['index_code', 'trade_date', 'daily_return']])
    
    returns_df = pd.concat(returns_list, ignore_index=True)
    returns_df = returns_df.dropna(subset=['daily_return'])
    
    print(f"\n收益率数据: {len(returns_df)} 条记录")
    print(f"收益率统计:")
    print(returns_df['daily_return'].describe())
    
    return returns_df


def calculate_correlation_matrix(returns_df):
    """计算相关性矩阵"""
    # 透视表: 行=日期, 列=指数, 值=收益率
    pivot_df = returns_df.pivot(index='trade_date', columns='index_code', values='daily_return')
    
    print(f"\n透视表形状: {pivot_df.shape}")
    print(f"日期数量: {len(pivot_df)}")
    print(f"指数数量: {len(pivot_df.columns)}")
    
    # 计算相关性矩阵
    corr_matrix = pivot_df.corr(method='pearson')
    
    print(f"\n相关性矩阵形状: {corr_matrix.shape}")
    print(f"\n相关性统计:")
    print(corr_matrix.describe())
    
    return corr_matrix, pivot_df


def save_correlation_matrix(corr_matrix):
    """保存相关性矩阵到CSV"""
    output_path = r'D:\Study\Project\investment-agent\data_runtime\index_correlation_matrix.csv'
    corr_matrix.to_csv(output_path)
    print(f"\n相关性矩阵已保存: {output_path}")


def analyze_correlation(corr_matrix):
    """分析相关性矩阵"""
    # 提取上三角矩阵（去除对角线）
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
    correlations = corr_matrix.where(mask).stack()
    
    print("\n" + "="*60)
    print("相关性分析")
    print("="*60)
    print(f"\n相关性数量: {len(correlations)}")
    print(f"平均相关性: {correlations.mean():.4f}")
    print(f"中位数相关性: {correlations.median():.4f}")
    print(f"最大相关性: {correlations.max():.4f}")
    print(f"最小相关性: {correlations.min():.4f}")
    
    # 高相关性对 (>0.8)
    high_corr = correlations[correlations > 0.8]
    print(f"\n高相关性对 (>0.8): {len(high_corr)} 对")
    if len(high_corr) > 0:
        print("\n前10个高相关性对:")
        print(high_corr.sort_values(ascending=False).head(10))
    
    # 低相关性对 (<0.2)
    low_corr = correlations[correlations < 0.2]
    print(f"\n低相关性对 (<0.2): {len(low_corr)} 对")
    
    return correlations


def main():
    """主函数"""
    print("="*60)
    print("指数收益率相关性矩阵计算")
    print("="*60)
    
    # 1. 加载数据
    df = load_index_data()
    
    # 2. 计算收益率
    returns_df = calculate_returns(df)
    
    # 3. 计算相关性矩阵
    corr_matrix, pivot_df = calculate_correlation_matrix(returns_df)
    
    # 4. 保存结果
    save_correlation_matrix(corr_matrix)
    
    # 5. 分析相关性
    correlations = analyze_correlation(corr_matrix)
    
    print("\n" + "="*60)
    print("计算完成!")
    print("="*60)
    
    return corr_matrix, pivot_df


if __name__ == '__main__':
    corr_matrix, pivot_df = main()
