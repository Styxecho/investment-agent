"""
Data loading utilities for risk budget allocator.
"""

import warnings
import pandas as pd
from typing import Optional
from pathlib import Path


def load_prices_from_csv(
    path: str,
    date_col: str = "date",
    price_col: str = "close",
    code_col: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load prices from CSV.

    Supports two formats:
    1. Wide format: columns=[date, asset1, asset2, ...]
    2. Long format: columns=[date, code, close]

    Args:
        path: CSV file path
        date_col: Date column name
        price_col: Price column name (for long format)
        code_col: Asset code column name (for long format)

    Returns:
        DataFrame with dates as index and asset codes as columns
    """
    df = pd.read_csv(path, parse_dates=[date_col])
    df = df.set_index(date_col).sort_index()

    if code_col is not None and code_col in df.columns:
        # Long format
        df = df.pivot(columns=code_col, values=price_col)

    return df


def load_prices_from_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and return price DataFrame."""
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    return df.sort_index()


def validate_price_data(
    prices: pd.DataFrame,
    required_codes: list,
    min_observations: int = 30,
) -> pd.DataFrame:
    """
    Validate price data has required codes and enough observations.

    Args:
        prices: Price DataFrame
        required_codes: List of required asset codes
        min_observations: Minimum required observations

    Returns:
        Validated DataFrame

    Raises:
        ValueError: If validation fails
    """
    missing = [code for code in required_codes if code not in prices.columns]
    if missing:
        raise ValueError(f"Missing required asset codes: {missing}")

    prices = prices[required_codes].dropna()
    if len(prices) < min_observations:
        raise ValueError(
            f"Insufficient observations: {len(prices)} < {min_observations}"
        )

    return prices


def warn_on_missing_prices(
    prices: pd.DataFrame,
    asset_codes: list,
    context: str = "price window",
) -> None:
    """
    Warn if selected asset codes have missing prices in the given window.

    Args:
        prices: Price DataFrame
        asset_codes: Asset codes to check
        context: Description of the window for the warning message
    """
    for code in asset_codes:
        if code not in prices.columns:
            warnings.warn(
                f"Required asset code {code} not found in {context}.",
                UserWarning,
                stacklevel=2,
            )
            continue
        nan_count = prices[code].isna().sum()
        if nan_count > 0:
            warnings.warn(
                f"Asset {code} has {nan_count} missing prices in {context}. "
                "Returns will be computed from available observations, which may use stale data.",
                UserWarning,
                stacklevel=2,
            )
