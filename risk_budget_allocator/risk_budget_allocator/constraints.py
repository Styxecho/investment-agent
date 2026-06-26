"""
Constraint handling for risk budget allocator.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple


def apply_bounds_and_normalize(
    weights: np.ndarray,
    min_weights: Optional[np.ndarray] = None,
    max_weights: Optional[np.ndarray] = None,
    total: Optional[float] = None,
    tol: float = 1e-10
) -> np.ndarray:
    """
    Apply min/max bounds to weights and renormalize to a target sum.

    Args:
        weights: Raw weight vector
        min_weights: Minimum weight for each asset
        max_weights: Maximum weight for each asset
        total: Target sum (default 1.0)
        tol: Numerical tolerance

    Returns:
        Bounded and normalized weight vector
    """
    weights = np.asarray(weights, dtype=float)
    n = len(weights)
    target = 1.0 if total is None else float(total)

    if min_weights is None:
        min_weights = np.zeros(n)
    else:
        min_weights = np.asarray(min_weights, dtype=float)

    if max_weights is None:
        max_weights = np.ones(n) * target
    else:
        max_weights = np.asarray(max_weights, dtype=float)

    # Clip to bounds
    weights = np.clip(weights, min_weights, max_weights)

    # Renormalize to target
    current_total = weights.sum()
    if current_total < tol:
        # If all weights are zero after clipping, use equal weight within bounds
        weights = (min_weights + max_weights) / 2
        current_total = weights.sum()

    if current_total > 0:
        weights = weights * (target / current_total)

    # Recursively clip and normalize until stable
    for _ in range(100):
        clipped = np.clip(weights, min_weights, max_weights)
        current_total = clipped.sum()
        if current_total < tol:
            break
        normalized = clipped * (target / current_total)
        if np.allclose(normalized, weights, atol=tol):
            return normalized
        weights = normalized

    return weights


def adjust_for_cash_floor(
    weights: Dict[str, float],
    min_cash: float = 0.01,
    asset_classes: Tuple[str, ...] = ("equity", "bond", "commodity")
) -> Dict[str, float]:
    """
    Ensure cash weight is at least min_cash by reducing risk assets.
    Assets at their minimum weight are not reduced further.
    """
    result = dict(weights)
    risk_total = sum(result.get(ac, 0.0) for ac in asset_classes)
    cash = 1.0 - risk_total

    if cash < min_cash and risk_total > 0:
        shortfall = min_cash - cash

        # Iteratively reduce risk assets that are above their effective minimum
        for _ in range(100):
            reducible = {ac: max(result.get(ac, 0.0), 0.0) for ac in asset_classes}
            total_reducible = sum(reducible.values())
            if total_reducible < 1e-12:
                break

            # Check if shortfall can be covered
            if total_reducible >= shortfall:
                scale = (risk_total - shortfall) / risk_total
                for ac in asset_classes:
                    result[ac] *= scale
                break
            else:
                # Cannot fully cover, set all reducible to zero
                for ac in asset_classes:
                    result[ac] = 0.0
                break

        result["cash"] = 1.0 - sum(result.get(ac, 0.0) for ac in asset_classes)

        # Final safeguard
        if result["cash"] < min_cash - 1e-10:
            risk_total = sum(result.get(ac, 0.0) for ac in asset_classes)
            if risk_total > 0:
                scale = (1.0 - min_cash) / risk_total
                for ac in asset_classes:
                    result[ac] *= scale
            result["cash"] = 1.0 - sum(result.get(ac, 0.0) for ac in asset_classes)
    else:
        result["cash"] = cash

    return result


def parse_constraints(
    constraints: Dict[str, Dict[str, Optional[float]]],
    asset_classes: Tuple[str, ...] = ("equity", "bond", "commodity")
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Parse weight constraints dictionary into min/max arrays.

    Args:
        constraints: Dict mapping asset class to {'min': x, 'max': y}
        asset_classes: Ordered asset classes

    Returns:
        (min_weights, max_weights) as numpy arrays
    """
    n = len(asset_classes)
    min_weights = np.zeros(n)
    max_weights = np.ones(n)

    for i, ac in enumerate(asset_classes):
        if ac in constraints:
            c = constraints[ac]
            if c.min is not None:
                min_weights[i] = float(c.min)
            if c.max is not None:
                max_weights[i] = float(c.max)

    return min_weights, max_weights
