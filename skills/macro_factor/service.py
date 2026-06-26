# skills/macro_factor/service.py
"""
宏观因子计算服务
封装核心计算逻辑，供Skill调用
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import logging

from data_external.db.engine import engine
from sqlalchemy import text

from .pipeline import MacroFactorPipeline
from .schema import FactorValue, FactorMatrix, ComputeRequest, QueryRequest

logger = logging.getLogger(__name__)


class MacroFactorService:
    """宏观因子计算服务"""
    
    def __init__(self):
        self.engine = engine
        self.pipeline = MacroFactorPipeline()
    
    def compute_factors(self, request: ComputeRequest) -> Dict:
        """
        批量计算因子
        
        Returns:
            {
                "success": [成功指标列表],
                "failed": {code: error_msg},
                "total_records": 总记录数
            }
        """
        # 获取要处理的指标列表
        if request.indicator_codes:
            indicators = request.indicator_codes
        else:
            query = "SELECT indicator_code FROM macro_factor_config WHERE is_active = 1"
            indicators = pd.read_sql(text(query), self.engine)['indicator_code'].tolist()
        
        success = []
        failed = {}
        total_records = 0
        
        for code in indicators:
            try:
                count = self.pipeline.run(code, request.start_date, request.end_date)
                success.append(code)
                total_records += count
                logger.info(f"✓ {code}: {count} 条")
            except Exception as e:
                failed[code] = str(e)
                logger.error(f"✗ {code}: {e}")
        
        return {
            "success": success,
            "failed": failed,
            "total_records": total_records
        }
    
    def query_factors(self, request: QueryRequest) -> FactorMatrix:
        """
        查询指定日期的因子值
        
        Returns:
            FactorMatrix
        """
        # 构建查询
        if request.indicator_codes:
            placeholders = ', '.join([f"'{c}'" for c in request.indicator_codes])
            code_filter = f"AND indicator_code IN ({placeholders})"
        else:
            code_filter = ""
        
        types_filter = ', '.join([f"'{t}'" for t in request.factor_types])
        
        query = f"""
        SELECT indicator_code, publish_date, factor_type, factor_value, cycle_value
        FROM macro_factor_value
        WHERE publish_date = :date
          AND factor_type IN ({types_filter})
          {code_filter}
        ORDER BY indicator_code
        """
        
        df = pd.read_sql(text(query), self.engine, params={"date": request.target_date})
        
        # 组装为FactorMatrix
        factors = {}
        for _, row in df.iterrows():
            code = row['indicator_code']
            if code not in factors:
                factors[code] = {}
            factors[code][row['factor_type']] = float(row['factor_value']) if pd.notna(row['factor_value']) else None
        
        return FactorMatrix(
            date=request.target_date,
            factors=factors
        )
    
    def query_factor_series(
        self, 
        indicator_code: str, 
        factor_type: str = "level",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        查询因子时间序列
        
        Returns:
            DataFrame with columns: [publish_date, factor_value, cycle_value]
        """
        conditions = ["indicator_code = :code", "factor_type = :ftype"]
        params = {"code": indicator_code, "ftype": factor_type}
        
        if start_date:
            conditions.append("publish_date >= :start")
            params["start"] = start_date
        if end_date:
            conditions.append("publish_date <= :end")
            params["end"] = end_date
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
        SELECT publish_date, factor_value, cycle_value
        FROM macro_factor_value
        WHERE {where_clause}
        ORDER BY publish_date
        """
        
        return pd.read_sql(text(query), self.engine, params=params)
    
    def get_available_indicators(self) -> List[Dict]:
        """获取所有可用指标列表"""
        query = """
        SELECT 
            c.indicator_code,
            c.indicator_name,
            c.category,
            c.frequency,
            COUNT(v.id) as record_count,
            MIN(v.publish_date) as earliest_date,
            MAX(v.publish_date) as latest_date
        FROM macro_indicator_catalog c
        LEFT JOIN macro_factor_value v ON c.indicator_code = v.indicator_code
        WHERE c.is_active = 1
        GROUP BY c.indicator_code
        ORDER BY c.category, c.indicator_code
        """
        return pd.read_sql(text(query), self.engine).to_dict('records')
    
    def get_latest_factors(self, indicator_codes: Optional[List[str]] = None) -> FactorMatrix:
        """获取最新日期的因子值"""
        # 获取最新日期
        date_query = "SELECT MAX(publish_date) as latest FROM macro_factor_value"
        latest_date = pd.read_sql(text(date_query), self.engine).iloc[0]['latest']
        
        if not latest_date:
            return FactorMatrix(date="", factors={})
        
        return self.query_factors(QueryRequest(
            target_date=str(latest_date),
            indicator_codes=indicator_codes
        ))


# 单例实例
macro_factor_service = MacroFactorService()
