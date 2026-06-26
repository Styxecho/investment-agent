# skills/macro_state/data_manager.py
"""
Data Manager - CSV upload validation and database operations

Handles:
- CSV format validation
- Data quality checks
- Batch import to database
- Data freshness checks

Internal module - no external script dependencies.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import sys
sys.path.insert(0, r'D:\Study\Project\investment-agent')
from data_external.db.engine import engine
from sqlalchemy import text


# Valid indicator configurations
VALID_INDICATORS = {
    'CN_PMI_MFG_M': {'freq': 'monthly', 'min': 30, 'max': 70},
    'CN_PMI_SVC_M': {'freq': 'monthly', 'min': 30, 'max': 70},
    'CN_PMI_COMP_M': {'freq': 'monthly', 'min': 30, 'max': 70},
    'CN_IAV_YOY_M': {'freq': 'monthly', 'min': -20, 'max': 30},
    'CN_CPI_YOY_M': {'freq': 'monthly', 'min': -5, 'max': 15},
    'CN_CCPI_YOY_M': {'freq': 'monthly', 'min': -5, 'max': 15},
    'CN_CPI_MOM_M': {'freq': 'monthly', 'min': -5, 'max': 10},
    'CN_CCPI_MOM_M': {'freq': 'monthly', 'min': -5, 'max': 10},
    'CN_CPI_NPF_M': {'freq': 'monthly', 'min': -5, 'max': 10},
    'CN_PPI_YOY_M': {'freq': 'monthly', 'min': -15, 'max': 20},
    'CN_PPI_MOM_M': {'freq': 'monthly', 'min': -10, 'max': 10},
    'CN_PPI_NPF_M': {'freq': 'monthly', 'min': -10, 'max': 10},
    'CN_M0_YOY_M': {'freq': 'monthly', 'min': -10, 'max': 50},
    'CN_M1_YOY_M': {'freq': 'monthly', 'min': -10, 'max': 50},
    'CN_M2_YOY_M': {'freq': 'monthly', 'min': 0, 'max': 40},
    'CN_SFS_YOY_M': {'freq': 'monthly', 'min': -20, 'max': 50},
    'CN_SFS_FLOW_M': {'freq': 'monthly', 'min': 0, 'max': 100000},
    'CN_IIV_YOY_M': {'freq': 'monthly', 'min': -30, 'max': 50},
    'CN_DR007_D': {'freq': 'daily', 'min': 0, 'max': 10},
    'CN_OMO_R007_D': {'freq': 'daily', 'min': 0, 'max': 10},
    'CN_R007_D': {'freq': 'daily', 'min': 0, 'max': 10},
}

REQUIRED_COLUMNS = ['indicator_code', 'publish_date', 'value']


class DataManager:
    """数据管理器"""
    
    def __init__(self):
        self.engine = engine
    
    def validate_csv(self, df: pd.DataFrame, data_type: str = 'monthly') -> Tuple[List[str], List[str], pd.DataFrame]:
        """
        校验CSV数据
        返回: (errors, warnings, validated_df)
        """
        errors = []
        warnings = []
        
        # 1. 检查必需列
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")
            return errors, warnings, df
        
        # 2. 检查指标代码
        invalid_indicators = df[~df['indicator_code'].isin(VALID_INDICATORS.keys())]['indicator_code'].unique()
        if len(invalid_indicators) > 0:
            errors.append(f"Invalid indicator codes: {list(invalid_indicators)}")
        
        # 3. 检查日期格式
        try:
            df['publish_date'] = df['publish_date'].astype(str).str.replace('-', '').str.replace('/', '')
            df['date_parsed'] = pd.to_datetime(df['publish_date'], format='%Y%m%d', errors='coerce')
            invalid_dates = df[df['date_parsed'].isna()]
            if len(invalid_dates) > 0:
                errors.append(f"Invalid date format: {invalid_dates['publish_date'].tolist()}")
        except Exception as e:
            errors.append(f"Date parsing error: {e}")
        
        # 4. 检查数值
        try:
            df['value_num'] = pd.to_numeric(df['value'], errors='coerce')
            invalid_values = df[df['value_num'].isna()]
            if len(invalid_values) > 0:
                errors.append(f"Invalid values: {len(invalid_values)} records")
        except Exception as e:
            errors.append(f"Value parsing error: {e}")
        
        # 5. 频率一致性检查
        if data_type == 'monthly':
            non_month_end = df[df['date_parsed'].dt.day != df['date_parsed'].dt.days_in_month]
            if len(non_month_end) > 0:
                warnings.append(f"Non month-end dates found, auto-adjusted: {len(non_month_end)} records")
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
                    f"{indicator}: {len(out_of_range)} records out of range [{config['min']}, {config['max']}]"
                )
        
        # 7. 重复检查
        duplicates = df[df.duplicated(['indicator_code', 'publish_date'], keep=False)]
        if len(duplicates) > 0:
            errors.append(f"Duplicate records found: {len(duplicates)}")
        
        return errors, warnings, df
    
    def check_data_completeness(self) -> Dict:
        """
        检查数据齐备性
        返回最新数据时间点和缺失指标
        """
        # 获取各指标最新日期
        sql = """
        SELECT 
            indicator_code,
            MAX(publish_date) as latest_date,
            COUNT(*) as record_count
        FROM macro_indicator_value
        GROUP BY indicator_code
        ORDER BY indicator_code
        """
        
        df = pd.read_sql(sql, self.engine)
        
        if len(df) == 0:
            return {
                'overall_latest': None,
                'indicators': {},
                'missing': list(VALID_INDICATORS.keys())
            }
        
        # 找到总体最新日期（取最小值，因为需要所有指标都更新）
        latest_dates = pd.to_datetime(df['latest_date'], format='%Y%m%d')
        overall_latest = latest_dates.min()
        
        # 检查缺失指标
        existing_indicators = set(df['indicator_code'].tolist())
        required_indicators = set(VALID_INDICATORS.keys())
        missing_indicators = list(required_indicators - existing_indicators)
        
        # 构建指标详情
        indicators_info = {}
        for _, row in df.iterrows():
            indicators_info[row['indicator_code']] = {
                'latest_date': row['latest_date'],
                'record_count': row['record_count']
            }
        
        return {
            'overall_latest': overall_latest.strftime('%Y%m%d') if overall_latest else None,
            'indicators': indicators_info,
            'missing': missing_indicators
        }
    
    def check_data_freshness(self) -> Tuple[str, str, Optional[str]]:
        """
        检查数据时效性
        返回: (status, db_latest, expected_date)
        status: 'FRESH' | 'STALE' | 'NO_DATA'
        """
        completeness = self.check_data_completeness()
        
        if completeness['overall_latest'] is None:
            return 'NO_DATA', 'N/A', None
        
        db_latest = completeness['overall_latest']
        db_date = datetime.strptime(db_latest, '%Y%m%d')
        
        # 计算预期最新日期（上个月末）
        today = datetime.now()
        if today.day <= 15:
            # 如果本月还没过15号，预期数据是上上个月
            expected = (today.replace(day=1) - pd.offsets.MonthEnd(2))
        else:
            # 如果本月过了15号，预期数据是上个月
            expected = (today.replace(day=1) - pd.offsets.MonthEnd(1))
        
        expected_date = expected.strftime('%Y%m%d')
        
        if db_date >= expected:
            return 'FRESH', db_latest, expected_date
        else:
            return 'STALE', db_latest, expected_date
    
    def import_data(self, df: pd.DataFrame, data_type: str = 'monthly') -> int:
        """
        导入数据到数据库
        返回导入记录数
        """
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
        
        # 使用INSERT OR REPLACE
        insert_sql = """
        INSERT OR REPLACE INTO macro_indicator_value 
        (indicator_code, publish_date, value, frequency, period_type, data_source)
        VALUES (:indicator_code, :publish_date, :value, :frequency, :period_type, :data_source)
        """
        
        with self.engine.connect() as conn:
            for record in records:
                conn.execute(text(insert_sql), record)
            conn.commit()
        
        return len(records)
    
    def clear_factors_and_states(self):
        """清空因子和状态表（用于重算前）"""
        with self.engine.connect() as conn:
            conn.execute(text("DELETE FROM macro_factor_value"))
            conn.execute(text("DELETE FROM macro_state_detail"))
            conn.commit()
    
    def load_raw_data(self, indicator_codes: List[str]) -> Dict[str, pd.DataFrame]:
        """
        加载原始数据
        返回: {indicator_code: DataFrame}
        """
        data = {}
        
        for code in indicator_codes:
            sql = f"""
            SELECT publish_date, value 
            FROM macro_indicator_value 
            WHERE indicator_code = '{code}' AND value IS NOT NULL
            ORDER BY publish_date
            """
            df = pd.read_sql(sql, self.engine)
            if len(df) > 0:
                df['publish_date'] = pd.to_datetime(df['publish_date'], format='%Y%m%d')
                df = df.set_index('publish_date').sort_index()
                data[code] = df
        
        return data
    
    def store_factors(self, factor_results: Dict[str, pd.DataFrame]):
        """存储因子计算结果"""
        # 获取数据库表的实际列
        pragma_sql = "PRAGMA table_info(macro_factor_value)"
        pragma_df = pd.read_sql(pragma_sql, self.engine)
        db_columns = set(pragma_df['name'].tolist())
        
        all_records = []
        for indicator_code, df in factor_results.items():
            if df is None or len(df) == 0:
                continue
            
            # 只保留数据库中存在的列
            available_cols = [col for col in df.columns if col in db_columns]
            store_df = df[available_cols].copy()
            store_df = store_df.dropna(subset=['factor_value'])
            
            if len(store_df) > 0:
                all_records.append(store_df)
        
        if all_records:
            combined = pd.concat(all_records, ignore_index=True)
            combined.to_sql('macro_factor_value', self.engine, if_exists='append', index=False)
    
    def store_states(self, states_df: pd.DataFrame):
        """存储状态计算结果"""
        if len(states_df) == 0:
            return
        
        # 获取数据库表的实际列
        pragma_sql = "PRAGMA table_info(macro_state_detail)"
        pragma_df = pd.read_sql(pragma_sql, self.engine)
        db_columns = set(pragma_df['name'].tolist())
        
        # 只保留数据库中存在的列
        available_cols = [col for col in states_df.columns if col in db_columns]
        store_df = states_df[available_cols].copy()
        
        if len(store_df) > 0:
            store_df.to_sql('macro_state_detail', self.engine, if_exists='append', index=False)
    
    def load_daily_series(self, indicator_code: str, forward_fill: bool = False) -> Optional[pd.Series]:
        """
        加载日频数据序列
        
        Args:
            indicator_code: 指标代码
            forward_fill: 是否前向填充缺失值（适用于OMO等政策利率）
        
        Returns:
            以日期为索引的Series，或None（无数据）
        """
        sql = f"""
        SELECT publish_date, value 
        FROM macro_indicator_value 
        WHERE indicator_code = '{indicator_code}' AND value IS NOT NULL
        ORDER BY publish_date
        """
        df = pd.read_sql(sql, self.engine)
        
        if len(df) == 0:
            return None
        
        df['publish_date'] = pd.to_datetime(df['publish_date'], format='%Y%m%d')
        df = df.set_index('publish_date').sort_index()
        series = df['value']
        
        if forward_fill:
            # 创建完整交易日历索引（仅工作日）
            full_index = pd.date_range(
                start=series.index.min(), 
                end=series.index.max(), 
                freq='B'  # 工作日
            )
            series = series.reindex(full_index)
            series = series.ffill()  # 前向填充
        
        return series
    
    def get_latest_date(self) -> Optional[str]:
        """获取数据库最新日期"""
        sql = "SELECT MAX(publish_date) as latest FROM macro_indicator_value"
        df = pd.read_sql(sql, self.engine)
        
        if len(df) > 0 and df.iloc[0]['latest']:
            return str(df.iloc[0]['latest'])
        return None
