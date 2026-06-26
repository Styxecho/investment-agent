"""
Macro state query service
"""
import json
import pandas as pd
from sqlalchemy import text
from dashboard.backend.database import engine


def get_state_history(start_date: str = None, end_date: str = None):
    """Get macro state history"""
    conditions = ["1=1"]
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
        publish_date as date,
        macro_regime as regime,
        growth_state,
        inflation_state,
        liquidity_state,
        warnings
    FROM macro_state_detail
    WHERE {where_clause}
    ORDER BY publish_date
    """
    
    df = pd.read_sql(text(sql), engine, params=params)
    
    results = []
    for _, row in df.iterrows():
        warnings = row['warnings']
        if warnings and isinstance(warnings, str):
            try:
                warnings = json.loads(warnings)
            except:
                warnings = [warnings] if warnings else []
        else:
            warnings = []
        
        results.append({
            "date": str(row['date']),
            "regime": row['regime'],
            "growth_state": row['growth_state'],
            "inflation_state": row['inflation_state'],
            "liquidity_state": row['liquidity_state'],
            "warnings": warnings,
        })
    
    return results


def get_latest_state():
    """Get latest macro state"""
    sql = """
    SELECT * FROM macro_state_detail
    ORDER BY publish_date DESC
    LIMIT 1
    """
    
    df = pd.read_sql(sql, engine)
    
    if len(df) == 0:
        return None
    
    row = df.iloc[0]
    return _format_state_record(row)


def get_state_by_date(date: str):
    """Get macro state for specific date"""
    sql = """
    SELECT * FROM macro_state_detail
    WHERE publish_date = :date
    LIMIT 1
    """
    
    df = pd.read_sql(text(sql), engine, params={"date": date})
    
    if len(df) == 0:
        return None
    
    row = df.iloc[0]
    return _format_state_record(row)


def get_regime_transitions():
    """Get regime transition history with durations"""
    states = get_state_history()
    
    if not states:
        return []
    
    transitions = []
    current_regime = states[0]['regime']
    start_idx = 0
    
    for i, state in enumerate(states[1:], 1):
        if state['regime'] != current_regime:
            transitions.append({
                "date": states[start_idx]['date'],
                "regime": current_regime,
                "duration_months": i - start_idx
            })
            current_regime = state['regime']
            start_idx = i
    
    # Add last regime
    transitions.append({
        "date": states[start_idx]['date'],
        "regime": current_regime,
        "duration_months": len(states) - start_idx
    })
    
    return transitions


def _format_state_record(row):
    """Format a state DataFrame row into API response"""
    # Parse warnings
    warnings = row.get('warnings')
    if warnings and isinstance(warnings, str):
        try:
            warnings = json.loads(warnings)
        except:
            warnings = [warnings] if warnings else []
    else:
        warnings = []
    
    return {
        "date": str(row['publish_date']),
        "regime": row['macro_regime'],
        "growth": {
            "level": row.get('growth_level', ''),
            "direction": row.get('growth_direction', ''),
            "state": row['growth_state'],
            "raw_values": {
                "pmi": float(row['pmi_raw']) if pd.notna(row.get('pmi_raw')) else None,
                "iav": float(row['iav_raw']) if pd.notna(row.get('iav_raw')) else None,
            },
            "factor_values": {
                "pmi_z": float(row['pmi_z']) if pd.notna(row.get('pmi_z')) else None,
                "iav_z": float(row['iav_z']) if pd.notna(row.get('iav_z')) else None,
            }
        },
        "inflation": {
            "level": row.get('inflation_level', ''),
            "direction": row.get('inflation_direction', ''),
            "state": row['inflation_state'],
            "raw_values": {
                "ccpi": float(row['ccpi_raw']) if pd.notna(row.get('ccpi_raw')) else None,
                "ppi": float(row['ppi_raw']) if pd.notna(row.get('ppi_raw')) else None,
            },
            "factor_values": {
                "ccpi_z": float(row['ccpi_z']) if pd.notna(row.get('ccpi_z')) else None,
                "ppi_z": float(row['ppi_z']) if pd.notna(row.get('ppi_z')) else None,
            }
        },
        "liquidity": {
            "level": row.get('liquidity_level', ''),
            "direction": row.get('liquidity_direction', ''),
            "state": row['liquidity_state'],
            "raw_values": {
                "m2": float(row['m2_raw']) if pd.notna(row.get('m2_raw')) else None,
                "sfs": float(row['sfs_raw']) if pd.notna(row.get('sfs_raw')) else None,
            },
            "factor_values": {
                "m2_z": float(row['m2_z']) if pd.notna(row.get('m2_z')) else None,
                "sfs_z": float(row['sfs_z']) if pd.notna(row.get('sfs_z')) else None,
            }
        },
        "warnings": warnings,
        "methodology_version": row.get('methodology_version', 'V7')
    }
