"""
Covariance estimation interface for risk budget allocator.

Provides a unified interface for multiple covariance estimation methods:
- sample: sample covariance annualized
- ewma: exponentially weighted moving average covariance
- ledoit_wolf: Ledoit-Wolf shrinkage estimation
"""

import warnings
import numpy as np
import pandas as pd
from typing import Literal


def estimate_covariance(
    returns: pd.DataFrame,
    method: Literal["sample", "ewma", "ledoit_wolf"] = "sample",
    **kwargs
) -> pd.DataFrame:
    """
    Unified covariance estimation interface.

    Args:
        returns: DataFrame of asset returns, columns=asset codes
        method: Covariance estimation method
        **kwargs: Method-specific parameters
            - sample: annualization=252
            - ewma: halflife=30
            - ledoit_wolf: annualization=252

    Returns:
        Annualized covariance matrix as DataFrame
    """
    if returns.isna().any().any():
        nan_cols = returns.columns[returns.isna().any()].tolist()
        warnings.warn(
            f"Returns contain NaN in columns {nan_cols}. "
            "Covariance will use pairwise complete observations, which may use stale data.",
            UserWarning,
            stacklevel=2,
        )

    if method == "sample":
        valid_keys = {"annualization"}
        sample_kwargs = {k: v for k, v in kwargs.items() if k in valid_keys}
        return _sample_covariance(returns, **sample_kwargs)
    elif method == "ewma":
        valid_keys = {"halflife"}
        ewma_kwargs = {k: v for k, v in kwargs.items() if k in valid_keys}
        return _ewma_covariance(returns, **ewma_kwargs)
    elif method == "ledoit_wolf":
        valid_keys = {"annualization"}
        lw_kwargs = {k: v for k, v in kwargs.items() if k in valid_keys}
        return _ledoit_wolf_covariance(returns, **lw_kwargs)
    else:
        raise ValueError(f"Unknown covariance method: {method}")


def _sample_covariance(returns: pd.DataFrame, annualization: int = 252) -> pd.DataFrame:
    """Sample covariance annualized."""
    cov = returns.cov() * annualization
    return cov


def _ewma_covariance(returns: pd.DataFrame, halflife: int = 30) -> pd.DataFrame:
    """
    EWMA covariance with given half-life.

    pandas ewm uses span parameter. Relationship:
        span = 2 * halflife - 1
    """
    span = max(2 * halflife - 1, 1)
    ewm_cov = returns.ewm(span=span).cov()
    # Get the last covariance matrix
    last_date = ewm_cov.index.get_level_values(0)[-1]
    cov = ewm_cov.loc[last_date]
    # Annualize: multiply by 252
    cov = cov * 252
    return cov


def _ledoit_wolf_covariance(returns: pd.DataFrame, annualization: int = 252) -> pd.DataFrame:
    """
    Ledoit-Wolf shrinkage covariance estimator.
    Falls back to sample covariance if sample size is insufficient.
    """
    n_obs, n_assets = returns.shape
    if n_obs < n_assets * 2:
        # Not enough observations for reliable shrinkage
        return _sample_covariance(returns, annualization)

    try:
        from sklearn.covariance import LedoitWolf
        lw = LedoitWolf()
        lw.fit(returns.dropna().values)
        cov = pd.DataFrame(
            lw.covariance_ * annualization,
            index=returns.columns,
            columns=returns.columns
        )
        return cov
    except ImportError:
        # sklearn not available, fall back to sample
        return _sample_covariance(returns, annualization)
