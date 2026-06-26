#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
宏观数据手动上传工具
- CSV格式校验
- 数据合理性检查
- 自动导入数据库
- 触发V7流水线重算

Usage:
    python upload_macro_data.py --file monthly_data.csv --type monthly
    python upload_macro_data.py --file daily_data.csv --type daily --auto-recalc
"""

import pandas as pd
import numpy as np
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
from sqlalchemy import text

# ============================================================
# 配置
# ============================================================

VALID_INDICATORS = {
    # 月度指标
    'CN_PMI_MFG_M': {'freq': 'monthly', 'unit': '%', 'min': 30, 'max': 70},
    'CN_PMI_SVC_M': {'freq': 'monthly', 'unit': '%', 'min': 30, 'max': 70},
    'CN_PMI_COMP_M': {'freq': 'monthly', 'unit': '%', 'min': 30, 'max': 70},
    'CN_IAV_YOY_M': {'freq': 'monthly', 'unit': '%', 'min': -20, 'max': 30},
    'CN_CPI_YOY_M': {'freq': 'monthly', 'unit': '%', 'min': -5, 'max': 15},
    'CN_CCPI_YOY_M': {'freq': 'monthly', 'unit': '%', 'min': -5, 'max': 15},
    'CN_CPI_MOM_M': {'freq': 'monthly', 'unit': '%', 'min': -5, 'max': 10},
    'CN_CCPI_MOM_M': {'freq': 'monthly', 'unit': '%', 'min': -5, 'max': 10},
    'CN_CPI_NPF_M': {'freq': 'monthly', 'unit': '%', 'min': -5, 'max': 10},
    'CN_PPI_YOY_M': {'freq': 'monthly', 'unit': '%', 'min': -15, 'max': 20},
    'CN_PPI_MOM_M': {'freq': 'monthly', 'unit': '%', 'min': -10, 'max': 10},
    'CN_PPI_NPF_M': {'freq': 'monthly', 'unit': '%', 'min': -10, 'max': 10},
    'CN_M0_YOY_M': {'freq': 'monthly', 'unit': '%', 'min': -10, 'max': 50},
    'CN_M1_YOY_M': {'freq': 'monthly', 'unit': '%', 'min': -10, 'max': 50},
    'CN_M2_YOY_M': {'freq': 'monthly', 'unit': '%', 'min': 0, 'max': 40},
    'CN_SFS_YOY_M': {'freq': 'monthly', 'unit': '%', 'min': -20, 'max': 50},
    'CN_SFS_FLOW_M': {'freq': 'monthly', 'unit': '亿元', 'min': 0, 'max': 100000},
    'CN_IIV_YOY_M': {'freq': 'monthly', 'unit': '%', 'min': -30, 'max': 50},
    # 日度指标
    'CN_DR007_D': {'freq': 'daily', 'unit': '%', 'min': 0, 'max': 10},
    'CN_OMO_R007_D': {'freq': 'daily', 'unit': '%', 'min': 0, 'max': 10},
    'CN_R007_D': {'freq': 'daily', 'unit': '%', 'min': 0, 'max': 10},
}

REQUIRED_COLUMNS = ['indicator_code', 'publish_date', 'value']

# ============================================================
# 校验函数
# ============================================================

def validate_csv(df, data_type):
    """校验CSV格式和内容"""
    errors = []
    warnings = []
    
    # 1. 检查必需列
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        errors.append(f"缺少必需列: {missing_cols}")
        return errors, warnings, None
    
    # 2. 检查指标代码
    invalid_indicators = df[~df['indicator_code'].isin(VALID_INDICATORS.keys())]['indicator_code'].unique()
    if len(invalid_indicators) > 0:
        errors.append(f"无效的指标代码: {list(invalid_indicators)}")
    
    # 3. 检查日期格式
    try:
        df['publish_date'] = df['publish_date'].astype(str).str.replace('-', '').str.replace('/', '')
        df['date_parsed'] = pd.to_datetime(df['publish_date'], format='%Y%m%d', errors='coerce')
        invalid_dates = df[df['date_parsed'].isna()]
        if len(invalid_dates) > 0:
            errors.append(f"日期格式错误: {invalid_dates['publish_date'].tolist()}")
    except Exception as e:
        errors.append(f"日期解析错误: {e}")
    
    # 4. 检查数值
    try:
        df['value_num'] = pd.to_numeric(df['value'], errors='coerce')
        invalid_values = df[df['value_num'].isna()]
        if len(invalid_values) > 0:
            errors.append(f"数值格式错误: {invalid_values[['indicator_code', 'publish_date', 'value']].to_dict('records')}")
    except Exception as e:
        errors.append(f"数值解析错误: {e}")
    
    # 5. 检查频率一致性
    if data_type == 'monthly':
        non_month_end = df[df['date_parsed'].dt.day != df['date_parsed'].dt.days_in_month]
        if len(non_month_end) > 0:
            warnings.append(f"以下记录不是月末日期，将自动调整为月末: {non_month_end['publish_date'].tolist()}")
            # 自动调整为月末
            df.loc[non_month_end.index, 'date_parsed'] = df.loc[non_month_end.index, 'date_parsed'] + pd.offsets.MonthEnd(0)
            df.loc[non_month_end.index, 'publish_date'] = df.loc[non_month_end.index, 'date_parsed'].dt.strftime('%Y%m%d')
    
    # 6. 数值范围检查
    for indicator, config in VALID_INDICATORS.items():
        indicator_data = df[df['indicator_code'] == indicator]
        if len(indicator_data) == 0:
            continue
        
        out_of_range = indicator_data[
            (indicator_data['value_num'] < config['min']) | 
            (indicator_data['value_num'] > config['max'])
        ]
        
        if len(out_of_range) > 0:
            warnings.append(
                f"{indicator} 有 {len(out_of_range)} 条记录超出常规范围 "
                f"[{config['min']}, {config['max']}]"
            )
    
    # 7. 检查重复
    duplicates = df[df.duplicated(['indicator_code', 'publish_date'], keep=False)]
    if len(duplicates) > 0:
        errors.append(f"存在重复记录: {duplicates[['indicator_code', 'publish_date']].to_dict('records')}")
    
    # 8. 环比突变检查
    for indicator in df['indicator_code'].unique():
        if indicator not in VALID_INDICATORS:
            continue
        
        indicator_data = df[df['indicator_code'] == indicator].sort_values('publish_date')
        if len(indicator_data) >= 2:
            # 获取历史数据用于对比
            hist_sql = f"SELECT publish_date, value FROM macro_indicator_value WHERE indicator_code = '{indicator}' ORDER BY publish_date DESC LIMIT 6"
            hist_df = pd.read_sql(hist_sql, engine)
            
            if len(hist_df) > 0:
                last_value = hist_df.iloc[0]['value']
                new_value = indicator_data.iloc[0]['value_num']
                
                if not (pd.isna(last_value) or pd.isna(new_value)):
                    change = abs(new_value - last_value)
                    if change > 5:  # 5个百分点的突变
                        warnings.append(
                            f"{indicator} 环比变化 {change:.2f} 个百分点，"
                            f"请确认数据准确性"
                        )
    
    return errors, warnings, df


def preview_data(df):
    """预览数据摘要"""
    print("\n=== 数据预览 ===")
    print(f"总记录数: {len(df)}")
    print(f"指标数量: {df['indicator_code'].nunique()}")
    print(f"日期范围: {df['publish_date'].min()} ~ {df['publish_date'].max()}")
    
    print("\n各指标统计:")
    summary = df.groupby('indicator_code').agg({
        'publish_date': ['min', 'max', 'count'],
        'value': ['min', 'max', 'mean']
    }).round(2)
    print(summary.to_string())

# ============================================================
# 导入函数
# ============================================================

def import_to_database(df, data_type):
    """导入数据到数据库"""
    records = []
    
    for _, row in df.iterrows():
        indicator_code = row['indicator_code']
        config = VALID_INDICATORS.get(indicator_code, {})
        
        records.append({
            'indicator_code': indicator_code,
            'publish_date': row['publish_date'],
            'value': row['value_num'],
            'frequency': config.get('freq', data_type),
            'period_type': 'absolute' if 'PMI' in indicator_code else 'yoy',
            'data_source': 'manual_upload',
        })
    
    # 使用INSERT OR REPLACE避免重复
    insert_sql = """
    INSERT OR REPLACE INTO macro_indicator_value 
    (indicator_code, publish_date, value, frequency, period_type, data_source)
    VALUES (:indicator_code, :publish_date, :value, :frequency, :period_type, :data_source)
    """
    
    with engine.connect() as conn:
        for record in records:
            conn.execute(text(insert_sql), record)
        conn.commit()
    
    return len(records)


# ============================================================
# V7流水线触发
# ============================================================

def trigger_v8_recalculation():
    """触发V8流水线重新计算"""
    print("\n[INFO] 触发V8流水线重新计算...")
    
    try:
        # 使用Skill进行重算
        import sys
        sys.path.insert(0, r'D:\Study\Project\investment-agent')
        from skills.macro_state import macro_state_service
        from skills.base import SkillContext
        
        result = macro_state_service.execute(SkillContext(
            extra_params={"mode": "recalculate"}
        ))
        
        if result.meta.status == "success":
            print("[OK] V8重算完成，CSV已导出")
            return True
        else:
            print(f"[ERROR] V8重算失败: {result.meta.message}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 触发重算失败: {e}")
        return False

# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='宏观数据手动上传工具')
    parser.add_argument('--file', required=True, help='CSV文件路径')
    parser.add_argument('--type', choices=['monthly', 'daily'], required=True, help='数据频率')
    parser.add_argument('--auto-recalc', action='store_true', help='上传后自动触发V7重算')
    parser.add_argument('--force', action='store_true', help='跳过确认，强制导入')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("V7 宏观数据手动上传工具")
    print("=" * 70)
    
    # 1. 读取CSV
    print(f"\n[INFO] 读取文件: {args.file}")
    try:
        df = pd.read_csv(args.file, encoding='utf-8-sig')
        print(f"[OK] 成功读取 {len(df)} 行数据")
    except Exception as e:
        print(f"[ERROR] 读取文件失败: {e}")
        sys.exit(1)
    
    # 2. 校验数据
    print("\n[INFO] 校验数据中...")
    errors, warnings, validated_df = validate_csv(df, args.type)
    
    if errors:
        print("\n[ERROR] 发现以下错误，无法导入:")
        for error in errors:
            print(f"  ✗ {error}")
        sys.exit(1)
    
    if warnings:
        print("\n[WARN] 发现以下警告:")
        for warning in warnings:
            print(f"  ! {warning}")
    
    # 3. 预览数据
    preview_data(validated_df)
    
    # 4. 确认导入
    if not args.force:
        print("\n" + "=" * 70)
        confirm = input("确认导入以上数据到数据库? [y/N]: ")
        if confirm.lower() != 'y':
            print("[INFO] 用户取消导入")
            sys.exit(0)
    
    # 5. 导入数据
    print("\n[INFO] 导入数据到数据库...")
    count = import_to_database(validated_df, args.type)
    print(f"[OK] 成功导入 {count} 条记录")
    
    # 6. 更新目录表
    print("\n[INFO] 更新指标目录...")
    # 自动添加缺失的指标到目录表
    # 这里可以调用之前的update_catalog逻辑
    
    # 7. 触发重算
    if args.auto_recalc:
        trigger_v8_recalculation()
    else:
        print("\n[INFO] 提示: 上传完成后，请手动运行以下命令重新计算V8状态:")
        print("  python -c \"from skills.macro_state import macro_state_skill; from skills.base import SkillContext; macro_state_skill.execute(SkillContext(extra_params={\\\"mode\\\": \\\"recalculate\\\"}))\"")
    
    print("\n" + "=" * 70)
    print("[DONE] 数据上传完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
