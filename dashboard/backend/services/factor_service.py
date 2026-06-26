"""
Factor data query service
"""
import pandas as pd
from sqlalchemy import text
from dashboard.backend.database import engine


# Indicator code to name mapping
INDICATOR_NAMES = {
    'CN_PMI_MFG_M': '制造业PMI',
    'CN_PMI_SVC_M': '非制造业PMI',
    'CN_PMI_COMP_M': '综合PMI',
    'CN_IAV_YOY_M': '工业增加值同比',
    'CN_CCPI_YOY_M': '核心CPI同比',
    'CN_PPI_YOY_M': 'PPI同比',
    'CN_M2_YOY_M': 'M2同比',
    'CN_SFS_YOY_M': '社融存量同比',
}

INDICATOR_CATEGORIES = {
    'CN_PMI_MFG_M': 'growth',
    'CN_PMI_SVC_M': 'growth',
    'CN_PMI_COMP_M': 'growth',
    'CN_IAV_YOY_M': 'growth',
    'CN_CCPI_YOY_M': 'inflation',
    'CN_PPI_YOY_M': 'inflation',
    'CN_M2_YOY_M': 'liquidity',
    'CN_SFS_YOY_M': 'liquidity',
}


def get_factor_decomposition(indicator_code: str, start_date: str = None, end_date: str = None):
    """Get complete factor decomposition for an indicator"""
    conditions = ["indicator_code = :code"]
    params = {"code": indicator_code}
    
    if start_date:
        conditions.append("publish_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("publish_date <= :end_date")
        params["end_date"] = end_date
    
    where_clause = " AND ".join(conditions)
    
    sql = f"""
    SELECT 
        publish_date as date,
        factor_value as zscore,
        raw_value,
        cycle_value,
        trend_value,
        deviation,
        threshold,
        raw_direction,
        trend_direction,
        filter_method,
        filter_params
    FROM macro_factor_value
    WHERE {where_clause}
    ORDER BY publish_date
    """
    
    df = pd.read_sql(text(sql), engine, params=params)
    
    if len(df) == 0:
        return None
    
    first_row = df.iloc[0]
    
    return {
        "code": indicator_code,
        "name": INDICATOR_NAMES.get(indicator_code, indicator_code),
        "category": INDICATOR_CATEGORIES.get(indicator_code, 'unknown'),
        "filter_method": first_row.get('filter_method'),
        "filter_params": first_row.get('filter_params'),
        "data": [
            {
                "date": str(row['date']),
                "raw_value": float(row['raw_value']) if pd.notna(row['raw_value']) else None,
                "cycle_value": float(row['cycle_value']) if pd.notna(row['cycle_value']) else None,
                "trend_value": float(row['trend_value']) if pd.notna(row['trend_value']) else None,
                "zscore": float(row['zscore']) if pd.notna(row['zscore']) else None,
                "deviation": float(row['deviation']) if pd.notna(row['deviation']) else None,
                "threshold": float(row['threshold']) if pd.notna(row['threshold']) else None,
                "raw_direction": row['raw_direction'],
                "trend_direction": row['trend_direction'],
            }
            for _, row in df.iterrows()
        ]
    }


def get_latest_factors():
    """Get latest factor values for all indicators"""
    sql = """
    SELECT 
        v.indicator_code as code,
        v.publish_date as latest_date,
        v.factor_value as zscore,
        v.cycle_value as cycle,
        v.trend_value as trend,
        v.deviation,
        v.trend_direction as direction
    FROM macro_factor_value v
    INNER JOIN (
        SELECT indicator_code, MAX(publish_date) as max_date
        FROM macro_factor_value
        GROUP BY indicator_code
    ) latest ON v.indicator_code = latest.indicator_code 
        AND v.publish_date = latest.max_date
    ORDER BY v.indicator_code
    """
    
    df = pd.read_sql(sql, engine)
    
    results = []
    for _, row in df.iterrows():
        code = row['code']
        results.append({
            "code": code,
            "name": INDICATOR_NAMES.get(code, code),
            "category": INDICATOR_CATEGORIES.get(code, 'unknown'),
            "latest_date": str(row['latest_date']),
            "zscore": float(row['zscore']) if pd.notna(row['zscore']) else None,
            "cycle": float(row['cycle']) if pd.notna(row['cycle']) else None,
            "trend": float(row['trend']) if pd.notna(row['trend']) else None,
            "deviation": float(row['deviation']) if pd.notna(row['deviation']) else None,
            "direction": row['direction'],
        })
    
    return results
