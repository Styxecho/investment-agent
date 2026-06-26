# skills/macro_factor/pipeline.py
"""
宏观因子计算流水线
整合所有步骤：加载 → 预处理 → 滤波 → 计算 → 存储
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

from data_external.db.engine import engine
from sqlalchemy import text
from skills.macro_factor.filters import BaseFilter, OneSidedHPFilter

logger = logging.getLogger(__name__)


class MacroFactorPipeline:
    """宏观因子计算流水线"""
    
    def __init__(self):
        self.engine = engine
    
    # =========================================================================
    # Step 1: 数据加载
    # =========================================================================
    def load_data(self, indicator_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从macro_indicator_value加载原始数据
        
        对于日频指标，会在下一步转换为月频
        """
        query = """
        SELECT publish_date, value, frequency 
        FROM macro_indicator_value 
        WHERE indicator_code = :code 
          AND publish_date BETWEEN :start AND :end
        ORDER BY publish_date
        """
        
        df = pd.read_sql(
            text(query), 
            self.engine, 
            params={"code": indicator_code, "start": start_date, "end": end_date}
        )
        
        if df.empty:
            logger.warning(f"{indicator_code}: 无数据")
            return df
        
        df['publish_date'] = pd.to_datetime(df['publish_date'], format='%Y%m%d')
        df = df.set_index('publish_date').sort_index()
        
        return df
    
    # =========================================================================
    # Step 2: 预处理（日频转月频 + 插值）
    # =========================================================================
    def preprocess(self, df: pd.DataFrame, indicator_code: str, config: dict = None) -> pd.Series:
        """
        预处理时间序列
        1. 日频数据：20日移动平均 → 取月末值
        2. 月频数据：直接使用
        3. 缺失值：线性插值
        4. 特殊处理：减基准值（如PMI减50）
        5. 特殊处理：计算衍生指标（如M1-M2剪刀差）
        """
        if df.empty:
            return pd.Series()
        
        # 判断频率
        freq = df['frequency'].iloc[0] if 'frequency' in df.columns else 'monthly'
        
        if freq == 'daily':
            # 日频：20日移动平均 → 月末值
            series = df['value'].astype(float)
            series_ma = series.rolling(window=20, min_periods=10).mean()
            # 取每月最后一个值
            monthly_series = series_ma.resample('ME').last()
            logger.info(f"{indicator_code}: 日频转月频 {len(series)}→{len(monthly_series)} 条")
        else:
            # 月频：直接使用
            monthly_series = df['value'].astype(float)
        
        # 线性插值处理缺失值
        monthly_series = monthly_series.interpolate(method='linear')
        
        # 特殊处理：减基准值（如PMI减50）
        if config and 'subtract_baseline' in config:
            baseline = config['subtract_baseline']
            monthly_series = monthly_series - baseline
            logger.info(f"{indicator_code}: 减去基准值 {baseline}")
        
        # 去掉开头的NaN（如果存在）
        monthly_series = monthly_series.dropna()
        
        return monthly_series
    
    # =========================================================================
    # Step 3: 滤波
    # =========================================================================
    def apply_filter(self, series: pd.Series, filter_obj: BaseFilter) -> Dict[str, pd.Series]:
        """应用滤波器"""
        if len(series) < 6:
            logger.warning(f"数据点太少({len(series)})，跳过滤波")
            return {'cycle': series, 'trend': pd.Series(index=series.index, data=series.mean())}
        
        return filter_obj.fit_transform(series)
    
    # =========================================================================
    # Step 4: 因子计算
    # =========================================================================
    def calculate_factors(
        self, 
        cycle: pd.Series, 
        level_window: int = 36,
        change_window: int = 48,
        winsorize: float = 3.0,
        min_periods: int = 12,
        warmup_months: int = 18
    ) -> pd.DataFrame:
        """
        计算水平因子和变化率因子
        
        返回DataFrame，包含：
        - cycle: 周期项
        - level: 水平Z-score
        - change: 变化率Z-score
        """
        n = len(cycle)
        result = pd.DataFrame(index=cycle.index)
        result['cycle'] = cycle
        result['level'] = np.nan
        result['change'] = np.nan
        result['is_winsorized'] = False
        
        # 计算水平因子（周期项的Z-score）
        for t in range(warmup_months, n):
            start = max(0, t - level_window)
            hist = cycle.iloc[start:t]  # 不包含当前值
            
            if len(hist) >= min_periods and hist.std() > 0:
                z = (cycle.iloc[t] - hist.mean()) / hist.std()
                
                # Winsorize
                if abs(z) > winsorize:
                    z = np.sign(z) * winsorize
                    result.loc[cycle.index[t], 'is_winsorized'] = True
                
                result.loc[cycle.index[t], 'level'] = z
        
        # 计算变化率因子（周期项一阶差分的Z-score）
        delta = cycle.diff()
        for t in range(warmup_months + 1, n):
            start = max(0, t - change_window)
            hist = delta.iloc[start:t]
            
            if len(hist) >= min_periods and hist.std() > 0:
                z = (delta.iloc[t] - hist.mean()) / hist.std()
                
                # Winsorize
                if abs(z) > winsorize:
                    z = np.sign(z) * winsorize
                
                result.loc[cycle.index[t], 'change'] = z
        
        return result
    
    # =========================================================================
    # Step 5: 存储
    # =========================================================================
    def store_factors(
        self, 
        indicator_code: str,
        factor_df: pd.DataFrame,
        filter_method: str,
        filter_params: Dict,
        level_window: int,
        change_window: int
    ) -> int:
        """
        将因子值存入macro_factor_value表
        返回存储的记录数
        """
        records = []
        
        for idx, row in factor_df.iterrows():
            date_str = idx.strftime('%Y%m%d')
            
            # level因子
            if pd.notna(row['level']):
                records.append({
                    'indicator_code': indicator_code,
                    'publish_date': date_str,
                    'factor_type': 'level',
                    'factor_value': float(row['level']),
                    'raw_value': None,  # 原始值不存储（在原始表中）
                    'cycle_value': float(row['cycle']) if pd.notna(row['cycle']) else None,
                    'trend_value': None,
                    'zscore_window': level_window,
                    'filter_method': filter_method,
                    'filter_params': str(filter_params),
                    'is_winsorized': bool(row['is_winsorized']),
                    'data_source': 'computed'
                })
            
            # change因子
            if pd.notna(row['change']):
                records.append({
                    'indicator_code': indicator_code,
                    'publish_date': date_str,
                    'factor_type': 'change',
                    'factor_value': float(row['change']),
                    'raw_value': None,
                    'cycle_value': float(row['cycle']) if pd.notna(row['cycle']) else None,
                    'trend_value': None,
                    'zscore_window': change_window,
                    'filter_method': filter_method,
                    'filter_params': str(filter_params),
                    'is_winsorized': False,  # 变化率不单独标记
                    'data_source': 'computed'
                })
        
        if not records:
            return 0
        
        # 批量插入
        insert_sql = """
        INSERT OR REPLACE INTO macro_factor_value 
        (indicator_code, publish_date, factor_type, factor_value, raw_value,
         cycle_value, trend_value, zscore_window, filter_method, filter_params,
         is_winsorized, data_source)
        VALUES (:indicator_code, :publish_date, :factor_type, :factor_value, :raw_value,
                :cycle_value, :trend_value, :zscore_window, :filter_method, :filter_params,
                :is_winsorized, :data_source)
        """
        
        with self.engine.connect() as conn:
            for record in records:
                conn.execute(text(insert_sql), record)
            conn.commit()
        
        return len(records)
    
    # =========================================================================
    # 完整流水线执行
    # =========================================================================
    def run(
        self,
        indicator_code: str,
        start_date: str,
        end_date: str,
        config: Optional[Dict] = None
    ) -> int:
        """
        执行完整流水线
        
        Returns:
            存储的记录数
        """
        logger.info(f"开始处理 {indicator_code} ({start_date} - {end_date})")
        
        # 加载配置
        if config is None:
            config = self._load_config(indicator_code)
        
        # Step 1: 加载
        if indicator_code == 'CN_M1M2_DIFF_M':
            # 剪刀差：从M1和M2计算
            raw_df = self._load_m1m2_scissor(start_date, end_date)
        else:
            raw_df = self.load_data(indicator_code, start_date, end_date)
        
        if raw_df.empty:
            return 0
        
        # Step 2: 预处理
        monthly_series = self.preprocess(raw_df, indicator_code, config)
        if monthly_series.empty:
            return 0
        
        # Step 3: 滤波
        filter_type = config.get('filter_type', 'one_sided_hp')
        if filter_type == 'one_sided_hp':
            filter_obj = OneSidedHPFilter(
                lamb=eval(config.get('filter_params', '{"lamb": 14400}')).get('lamb', 14400),
                warmup_months=config.get('hp_warmup_months', 18)
            )
        else:
            filter_obj = OneSidedHPFilter()  # 默认
        
        filtered = self.apply_filter(monthly_series, filter_obj)
        
        # Step 4: 计算因子
        factors = self.calculate_factors(
            filtered['cycle'],
            level_window=config.get('level_window', 36),
            change_window=config.get('change_window', 48),
            winsorize=config.get('winsorize_threshold', 3.0),
            min_periods=config.get('min_periods_for_zscore', 12),
            warmup_months=config.get('hp_warmup_months', 18)
        )
        
        # Step 5: 存储
        count = self.store_factors(
            indicator_code=indicator_code,
            factor_df=factors,
            filter_method=filter_obj.name,
            filter_params=filter_obj.get_params(),
            level_window=config.get('level_window', 36),
            change_window=config.get('change_window', 48)
        )
        
        logger.info(f"{indicator_code}: 存储 {count} 条因子记录")
        return count
    
    def _load_m1m2_scissor(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        加载M1-M2剪刀差数据
        从M1和M2原始数据计算差值
        """
        query = """
        SELECT publish_date, value, 'monthly' as frequency
        FROM macro_indicator_value
        WHERE indicator_code = 'CN_M1_YOY_M'
          AND publish_date BETWEEN :start AND :end
        ORDER BY publish_date
        """
        m1_df = pd.read_sql(text(query), self.engine, params={"start": start_date, "end": end_date})
        
        query = """
        SELECT publish_date, value
        FROM macro_indicator_value
        WHERE indicator_code = 'CN_M2_YOY_M'
          AND publish_date BETWEEN :start AND :end
        ORDER BY publish_date
        """
        m2_df = pd.read_sql(text(query), self.engine, params={"start": start_date, "end": end_date})
        
        if m1_df.empty or m2_df.empty:
            logger.warning("M1或M2数据缺失，无法计算剪刀差")
            return pd.DataFrame()
        
        # 转换日期为datetime并设为索引
        m1_df['publish_date'] = pd.to_datetime(m1_df['publish_date'], format='%Y%m%d')
        m2_df['publish_date'] = pd.to_datetime(m2_df['publish_date'], format='%Y%m%d')
        
        # 合并并计算差值
        merged = pd.merge(m1_df[['publish_date', 'value']], 
                         m2_df[['publish_date', 'value']], 
                         on='publish_date', suffixes=('_m1', '_m2'))
        merged['value'] = merged['value_m1'] - merged['value_m2']
        merged['frequency'] = 'monthly'
        
        # 设置日期索引
        merged = merged.set_index('publish_date')
        
        logger.info(f"CN_M1M2_DIFF_M: 计算 {len(merged)} 条剪刀差数据")
        return merged[['value', 'frequency']]
    
    def _load_config(self, indicator_code: str) -> Dict:
        """从数据库加载指标配置"""
        query = "SELECT * FROM macro_factor_config WHERE indicator_code = :code"
        df = pd.read_sql(text(query), self.engine, params={"code": indicator_code})
        
        if df.empty:
            logger.warning(f"{indicator_code}: 无配置，使用默认值")
            return {
                'filter_type': 'one_sided_hp',
                'filter_params': '{"lamb": 14400}',
                'level_window': 36,
                'change_window': 48,
                'winsorize_threshold': 3.0,
                'min_periods_for_zscore': 12,
                'hp_warmup_months': 18
            }
        
        return df.iloc[0].to_dict()
