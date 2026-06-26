"""
Indicator data query service
"""
import pandas as pd
from sqlalchemy import text
from dashboard.backend.database import engine


def get_indicator_catalog():
    """Get all indicator definitions from catalog"""
    sql = """
    SELECT 
        indicator_code as code,
        indicator_name as name,
        category,
        frequency,
        unit,
        description
    FROM macro_indicator_catalog
    WHERE is_active = 1
    ORDER BY category, indicator_code
    """
    df = pd.read_sql(sql, engine)
    return df.to_dict('records')


def get_indicator_history(indicator_codes: list, start_date: str = None, end_date: str = None):
    """Get historical data for specified indicators"""
    placeholders = ','.join([f"'{code}'" for code in indicator_codes])
    
    conditions = [f"v.indicator_code IN ({placeholders})"]
    params = {}
    
    if start_date:
        conditions.append("publish_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("publish_date <= :end_date")
        params["end_date"] = end_date
    
    where_clause = " AND ".join(conditions)
    
    sql = f"""
    SELECT 
        v.indicator_code as code,
        c.indicator_name as name,
        c.category,
        c.frequency,
        c.unit,
        v.publish_date as date,
        v.value
    FROM macro_indicator_value v
    JOIN macro_indicator_catalog c ON v.indicator_code = c.indicator_code
    WHERE {where_clause}
    ORDER BY v.indicator_code, v.publish_date
    """
    
    df = pd.read_sql(text(sql), engine, params=params)
    
    # Group by indicator
    results = []
    for code in indicator_codes:
        indicator_df = df[df['code'] == code]
        if len(indicator_df) == 0:
            continue
        
        first_row = indicator_df.iloc[0]
        results.append({
            "code": code,
            "name": first_row['name'],
            "category": first_row['category'],
            "frequency": first_row['frequency'],
            "unit": first_row['unit'],
            "data": [
                {"date": str(row['date']), "value": float(row['value'])}
                for _, row in indicator_df.iterrows()
            ]
        })
    
    return results


def get_latest_indicators():
    """Get latest value for each indicator"""
    sql = """
    SELECT 
        v.indicator_code as code,
        c.indicator_name as name,
        c.category,
        v.publish_date as latest_date,
        v.value as latest_value,
        c.unit
    FROM macro_indicator_value v
    JOIN macro_indicator_catalog c ON v.indicator_code = c.indicator_code
    INNER JOIN (
        SELECT indicator_code, MAX(publish_date) as max_date
        FROM macro_indicator_value
        GROUP BY indicator_code
    ) latest ON v.indicator_code = latest.indicator_code 
        AND v.publish_date = latest.max_date
    WHERE c.is_active = 1
    ORDER BY c.category, v.indicator_code
    """
    
    df = pd.read_sql(sql, engine)
    return df.to_dict('records')
