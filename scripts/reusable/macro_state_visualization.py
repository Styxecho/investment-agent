#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V7 宏观状态可视化
- 象限变迁时间轴
- 热力图
- 雷达图（最新状态）
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.dates import DateFormatter
import sys

sys.path.insert(0, r'D:\Study\Project\investment-agent')

# 读取数据
csv_path = r'D:\Study\Project\investment-agent\docs\research\macro_analysis\macro_state_detail.csv'
df = pd.read_csv(csv_path)
df['date'] = pd.to_datetime(df['publish_date'], format='%Y%m%d')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
# 1. 象限变迁时间轴
# ============================================================

def plot_regime_timeline():
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # 定义象限颜色
    regime_colors = {
        '极端滞胀': '#8B0000',      # 深红
        '典型滞胀': '#DC143C',      #  crimson
        '过热期': '#FF4500',         # 橙红
        '失速衰退': '#4B0082',      # 靛蓝
        '宽衰退': '#4169E1',        # 皇家蓝
        '弱复苏': '#32CD32',        # 酸橙绿
        '强势复苏': '#228B22',      # 森林绿
        '完美扩张': '#FFD700',      # 金色
        '类衰退过渡': '#DDA0DD',    # 梅红
        '震荡/观望': '#A9A9A9',     # 灰色
    }
    
    # 绘制时间轴
    for i in range(len(df) - 1):
        regime = df['macro_regime'].iloc[i]
        color = regime_colors.get(regime, '#A9A9A9')
        
        ax.barh(0, (df['date'].iloc[i+1] - df['date'].iloc[i]).days,
                left=df['date'].iloc[i], height=0.6,
                color=color, alpha=0.8, edgecolor='white', linewidth=0.5)
    
    # 最后一个点
    last_regime = df['macro_regime'].iloc[-1]
    ax.barh(0, 30, left=df['date'].iloc[-1], height=0.6,
            color=regime_colors.get(last_regime, '#A9A9A9'), alpha=0.8)
    
    # 添加图例
    legend_patches = [mpatches.Patch(color=color, label=regime)
                      for regime, color in regime_colors.items()]
    ax.legend(handles=legend_patches, loc='upper left', bbox_to_anchor=(0, 1.1), ncol=5)
    
    ax.set_xlabel('时间')
    ax.set_title('V7 宏观象限变迁时间轴 (2014-2026)', fontsize=16, fontweight='bold')
    ax.set_yticks([])
    ax.grid(True, alpha=0.3, axis='x')
    
    # 添加关键事件标注
    events = [
        ('2020-01-31', 'COVID-19爆发'),
        ('2021-06-30', '地产调控收紧'),
        ('2022-03-31', '上海封城'),
        ('2024-09-30', '政策转向'),
    ]
    
    for date_str, event in events:
        event_date = pd.to_datetime(date_str)
        if event_date >= df['date'].min() and event_date <= df['date'].max():
            ax.axvline(event_date, color='black', linestyle='--', alpha=0.5)
            ax.text(event_date, 0.5, event, rotation=90, fontsize=8, ha='right')
    
    plt.tight_layout()
    plt.savefig(r'D:\Study\Project\investment-agent\docs\research\macro_analysis\v7_regime_timeline.png',
                dpi=300, bbox_inches='tight')
    print("[OK] 已生成象限变迁图: v7_regime_timeline.png")
    plt.close()

# ============================================================
# 2. 三维度状态热力图
# ============================================================

def plot_dimension_heatmap():
    fig, axes = plt.subplots(3, 1, figsize=(16, 10))
    
    dimensions = [
        ('growth_state', '增长维度', ['扩张', '中性', '收缩']),
        ('inflation_state', '通胀维度', ['高通胀', '温和通胀', '低通胀']),
        ('liquidity_state', '流动性维度', ['双宽', '宽货币紧信用', '紧货币宽信用', '双紧']),
    ]
    
    colors_map = {
        '扩张': '#2E8B57', '中性': '#FFD700', '收缩': '#DC143C',
        '高通胀': '#8B0000', '温和通胀': '#FFD700', '低通胀': '#32CD32',
        '双宽': '#32CD32', '宽货币紧信用': '#FFD700',
        '紧货币宽信用': '#FF8C00', '双紧': '#DC143C',
    }
    
    for idx, (col, title, levels) in enumerate(dimensions):
        ax = axes[idx]
        
        # 简化状态为水平
        if col == 'growth_state':
            states = df[col].str.extract(r'(扩张|中性|收缩)')[0]
        elif col == 'inflation_state':
            states = df[col].str.extract(r'(高通胀|温和通胀|低通胀)')[0]
        else:
            states = df[col].str.extract(r'(双宽|宽货币紧信用|紧货币宽信用|双紧)')[0]
        
        # 创建颜色矩阵
        n_months = len(df)
        heatmap_data = np.zeros((1, n_months))
        color_list = []
        
        for i, state in enumerate(states):
            color = colors_map.get(str(state), '#A9A9A9')
            color_list.append(color)
        
        # 绘制热力图
        for i in range(n_months - 1):
            ax.barh(0, (df['date'].iloc[i+1] - df['date'].iloc[i]).days,
                   left=df['date'].iloc[i], height=1,
                   color=color_list[i], alpha=0.8, edgecolor='white')
        
        ax.barh(0, 30, left=df['date'].iloc[-1], height=1,
               color=color_list[-1], alpha=0.8)
        
        ax.set_ylabel(title, fontsize=12, fontweight='bold')
        ax.set_yticks([])
        ax.grid(True, alpha=0.3, axis='x')
    
    axes[-1].set_xlabel('时间')
    fig.suptitle('V7 三维度状态热力图', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig(r'D:\Study\Project\investment-agent\docs\research\macro_analysis\v7_dimension_heatmap.png',
                dpi=300, bbox_inches='tight')
    print("[OK] 已生成三维度热力图: v7_dimension_heatmap.png")
    plt.close()

# ============================================================
# 3. 象限分布饼图
# ============================================================

def plot_regime_distribution():
    fig, ax = plt.subplots(figsize=(10, 8))
    
    regime_counts = df['macro_regime'].value_counts()
    
    colors = {
        '极端滞胀': '#8B0000',
        '典型滞胀': '#DC143C',
        '过热期': '#FF4500',
        '失速衰退': '#4B0082',
        '宽衰退': '#4169E1',
        '弱复苏': '#32CD32',
        '强势复苏': '#228B22',
        '完美扩张': '#FFD700',
        '类衰退过渡': '#DDA0DD',
        '震荡/观望': '#A9A9A9',
    }
    
    pie_colors = [colors.get(r, '#A9A9A9') for r in regime_counts.index]
    
    wedges, texts, autotexts = ax.pie(regime_counts.values,
                                        labels=regime_counts.index,
                                        colors=pie_colors,
                                        autopct='%1.1f%%',
                                        startangle=90)
    
    ax.set_title('V7 宏观象限分布 (2014-2026)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(r'D:\Study\Project\investment-agent\docs\research\macro_analysis\v7_regime_distribution.png',
                dpi=300, bbox_inches='tight')
    print("[OK] 已生成象限分布图: v7_regime_distribution.png")
    plt.close()

# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 70)
    print("V7 宏观状态可视化")
    print("=" * 70)
    
    print("\n[INFO] 生成象限变迁时间轴...")
    plot_regime_timeline()
    
    print("\n[INFO] 生成三维度热力图...")
    plot_dimension_heatmap()
    
    print("\n[INFO] 生成象限分布饼图...")
    plot_regime_distribution()
    
    print("\n" + "=" * 70)
    print("[DONE] 可视化完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
