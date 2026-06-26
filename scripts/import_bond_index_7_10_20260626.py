"""
Import 7-10 year China bond index data from Wind-exported CSV to index_daily table.

Source file: data_external/market/中债指数_20260626.csv
Contains two indices side by side:
  - CBA00351.CS (中债-总财富(7-10年)指数)
  - CBA00151.CS (中债-新综合财富(7-10年)指数)
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


def parse_bond_index_csv(file_path: str) -> pd.DataFrame:
    """
    Parse Wind-exported CSV with two indices side by side.

    Layout: row 0-6 metadata, row 7 header, row 8+ data.
    Two blocks separated by an empty column:
      cols 0-7  -> CBA00351.CS
      cols 9-16 -> CBA00151.CS
    """
    df = pd.read_csv(file_path, encoding="utf-8-sig", skiprows=8, header=None)

    block1 = df.iloc[:, 0:8].copy()
    block2 = df.iloc[:, 9:17].copy()

    columns = ["date", "pre_close", "open", "high", "low", "close", "volume", "amount"]
    block1.columns = columns
    block2.columns = columns

    block1["index_code"] = "CBA00351.CS"
    block2["index_code"] = "CBA00151.CS"

    all_data = pd.concat([block1, block2], ignore_index=True)
    all_data = all_data.dropna(subset=["date"])

    # Convert date
    all_data["date"] = pd.to_datetime(all_data["date"]).dt.strftime("%Y%m%d")

    # Convert numeric columns
    numeric_cols = ["pre_close", "open", "high", "low", "close", "volume", "amount"]
    for col in numeric_cols:
        all_data[col] = pd.to_numeric(all_data[col], errors="coerce")

    all_data = all_data.sort_values(["index_code", "date"]).reset_index(drop=True)
    return all_data


def import_to_db(df: pd.DataFrame) -> None:
    """Import parsed data to index_daily table using UPSERT logic."""
    df = df.where(pd.notnull(df), None)

    with engine.connect() as conn:
        for _, row in df.iterrows():
            delete_sql = text("""
                DELETE FROM index_daily
                WHERE index_code = :index_code AND trade_date = :trade_date
            """)
            conn.execute(delete_sql, {
                "index_code": row["index_code"],
                "trade_date": row["date"],
            })

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
    codes = ["CBA00351.CS", "CBA00151.CS"]
    for code in codes:
        df = pd.read_sql(
            f"SELECT MIN(trade_date) as min_dt, MAX(trade_date) as max_dt, COUNT(*) as cnt "
            f"FROM index_daily WHERE index_code = '{code}'",
            engine,
        )
        row = df.iloc[0]
        print(f"{code}: count={row['cnt']}, min={row['min_dt']}, max={row['max_dt']}")


if __name__ == "__main__":
    file_path = r"D:\Study\Project\investment-agent\data_external\market\中债指数_20260626.csv"

    print("Parsing 7-10 year bond index data...")
    df = parse_bond_index_csv(file_path)
    print(f"Parsed {len(df)} records for {df['index_code'].nunique()} indices")
    print(df.groupby("index_code").size())

    print("\nImporting to database...")
    import_to_db(df)

    print("\nVerifying import...")
    verify_import()

    print("\nDone!")
