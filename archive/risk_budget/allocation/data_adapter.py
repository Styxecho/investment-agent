"""
Data adapter for risk budget allocator within investment-agent.

Loads index prices from the project's SQLite database or CSV files
and converts them into a standard DataFrame expected by risk_budget_allocator.
"""

import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from data_external.db.engine import engine


def load_index_prices(
    index_codes: list,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    price_field: str = "close_price",
) -> pd.DataFrame:
    """
    Load index prices from SQLite database.

    Args:
        index_codes: List of index codes
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        price_field: Price field to use

    Returns:
        DataFrame with dates as index and index codes as columns
    """
    codes_str = ", ".join([f"'{code}'" for code in index_codes])
    sql = f"""
    SELECT index_code, trade_date, {price_field} as price
    FROM index_daily
    WHERE index_code IN ({codes_str})
    """

    params = {}
    if start_date:
        sql += " AND trade_date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        sql += " AND trade_date <= :end_date"
        params["end_date"] = end_date

    df = pd.read_sql(sql, engine, params=params)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df = df.pivot(index="trade_date", columns="index_code", values="price")
    df = df.sort_index()

    return df
