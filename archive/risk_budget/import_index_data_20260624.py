"""
Import index data from Wind-exported CSV to index_daily table.

Source file: data_external/market/index_data_20260624.csv
Contains three indices side by side:
  - CBA00101.CS (中债-新综合财富指数)
  - AU.SHF (SHFE黄金)
  - 000985.CSI (中证全指)
"""

import sys
from pathlib import Path
import os

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(str(project_root))

import pandas as pd
from sqlalchemy import text

from data_external.db.engine import engine


def parse_wind_index_csv(file_path: str) -> pd.DataFrame:
    """
    Parse Wind-exported CSV with multiple indices side by side.
    """
    # Read raw CSV, skip header rows
    df = pd.read_csv(file_path, skiprows=9, header=None)

    # The columns are grouped in triplets of 8 columns each:
    # [Date, pre_close, open, high, low, close, volume, amt, empty, Date, pre_close, ..., empty, ...]
    # Extract each index block
    indices = [
        {"code": "CBA00101.CS", "start_col": 0},
        {"code": "AU.SHF", "start_col": 9},
        {"code": "000985.CSI", "start_col": 18},
    ]

    records = []
    for idx_info in indices:
        start = idx_info["start_col"]
        code = idx_info["code"]

        # Extract 8 columns for this index
        sub = df.iloc[:, start:start+8].copy()
        sub.columns = ["date", "pre_close", "open", "high", "low", "close", "volume", "amount"]

        # Drop rows where date is NaN
        sub = sub.dropna(subset=["date"])

        # Convert date
        sub["date"] = pd.to_datetime(sub["date"]).dt.strftime("%Y%m%d")

        # Convert numeric columns
        numeric_cols = ["pre_close", "open", "high", "low", "close", "volume", "amount"]
        for col in numeric_cols:
            sub[col] = pd.to_numeric(sub[col], errors="coerce")

        sub["index_code"] = code
        records.append(sub)

    all_data = pd.concat(records, ignore_index=True)
    all_data = all_data.sort_values(["index_code", "date"]).reset_index(drop=True)

    return all_data


def import_to_db(df: pd.DataFrame) -> None:
    """Import parsed data to index_daily table using UPSERT logic."""
    # Clean data
    df = df.where(pd.notnull(df), None)

    with engine.connect() as conn:
        for _, row in df.iterrows():
            # Delete existing record if any (to handle duplicates)
            delete_sql = text("""
                DELETE FROM index_daily
                WHERE index_code = :index_code AND trade_date = :trade_date
            """)
            conn.execute(delete_sql, {
                "index_code": row["index_code"],
                "trade_date": row["date"],
            })

            # Insert new record
            insert_sql = text("""
                INSERT INTO index_daily (
                    index_code, trade_date, pre_close_price, open_price,
                    high_price, low_price, close_price, volume, amount
                ) VALUES (
                    :index_code, :trade_date, :pre_close_price, :open_price,
                    :high_price, :low_price, :close_price, :volume, :amount
                )
            """)
            conn.execute(insert_sql, {
                "index_code": row["index_code"],
                "trade_date": row["date"],
                "pre_close_price": row["pre_close"],
                "open_price": row["open"],
                "high_price": row["high"],
                "low_price": row["low"],
                "close_price": row["close"],
                "volume": row["volume"],
                "amount": row["amount"],
            })

        conn.commit()


def verify_import() -> None:
    """Verify data in index_daily."""
    import pandas as pd

    codes = ["CBA00101.CS", "AU.SHF", "000985.CSI"]
    for code in codes:
        df = pd.read_sql(
            f"SELECT MIN(trade_date) as min_dt, MAX(trade_date) as max_dt, COUNT(*) as cnt "
            f"FROM index_daily WHERE index_code = '{code}'",
            engine,
        )
        row = df.iloc[0]
        print(f"{code}: count={row['cnt']}, min={row['min_dt']}, max={row['max_dt']}")


if __name__ == "__main__":
    file_path = r"D:\Study\Project\investment-agent\data_external\market\index_data_20260624.csv"

    print("Parsing index data...")
    df = parse_wind_index_csv(file_path)
    print(f"Parsed {len(df)} records for {df['index_code'].nunique()} indices")
    print(df.groupby("index_code").size())

    print("\nImporting to database...")
    import_to_db(df)

    print("\nVerifying import...")
    verify_import()

    print("\nDone!")
