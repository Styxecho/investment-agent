"""
Risk budget solver for asset allocation.

Implements risk budgeting optimization:
- Target risk contribution RC_i = w_i * (Σw)_i / (w^T Σw) ≈ b_i
- Supports weight bounds
- Solver chain: SLSQP -> trust-constr -> unconstrained + clip -> inverse-volatility fallback
"""

import numpy as np
from scipy.optimize import minimize
from typing import Optional, Tuple

from .constraints import apply_bounds_and_normalize


def risk_budget_weights(
    cov_matrix: np.ndarray,
    risk_budget: np.ndarray,
    min_weights: Optional[np.ndarray] = None,
    max_weights: Optional[np.ndarray] = None,
    max_iter: int = 1000,
    tol: float = 1e-8,
    random_seed: int = 42,
) -> Tuple[np.ndarray, bool]:
    """
    Solve risk budget weights.

    Solver chain:
    1. SLSQP with bounds and sum-to-one constraint
    2. trust-constr if SLSQP fails or violates constraints
    3. Unconstrained risk budget + clip/normalize
    4. Inverse-volatility approximation: w_i ∝ b_i / σ_i, then clip/normalize

    Args:
        cov_matrix: Annualized covariance matrix
        risk_budget: Risk budget proportions, sum to 1
        min_weights: Minimum weight per asset
        max_weights: Maximum weight per asset
        max_iter: Maximum iterations
        tol: Convergence tolerance
        random_seed: Random seed for multi-start

    Returns:
        (weights, fallback_triggered)
    """
    cov_matrix = np.asarray(cov_matrix, dtype=float)
    risk_budget = np.asarray(risk_budget, dtype=float)
    n = cov_matrix.shape[0]

    if min_weights is None:
        min_weights = np.zeros(n)
    if max_weights is None:
        max_weights = np.ones(n)

    min_weights = np.asarray(min_weights, dtype=float)
    max_weights = np.asarray(max_weights, dtype=float)

    # Validate risk budget
    if not np.isclose(risk_budget.sum(), 1.0):
        risk_budget = risk_budget / risk_budget.sum()

    bounds = [(min_weights[i], max_weights[i]) for i in range(n)]

    # Step 1: Try SLSQP
    result = _solve_with_slsqp(cov_matrix, risk_budget, bounds, max_iter, tol)
    if result is not None and _check_valid(result, bounds, tol):
        return result, False

    # Step 2: Try trust-constr
    result = _solve_with_trust_constr(cov_matrix, risk_budget, bounds, max_iter, tol)
    if result is not None and _check_valid(result, bounds, tol):
        return result, False

    # Step 3: Unconstrained risk budget + clip/normalize
    result = _solve_unconstrained(cov_matrix, risk_budget, random_seed)
    if result is not None:
        result = apply_bounds_and_normalize(result, min_weights, max_weights)
        if _check_valid(result, bounds, tol):
            return result, True

    # Step 4: Inverse-volatility fallback
    result = _inverse_volatility_approx(cov_matrix, risk_budget)
    result = apply_bounds_and_normalize(result, min_weights, max_weights)
    return result, True


def _risk_budget_objective(w: np.ndarray, cov: np.ndarray, budget: np.ndarray) -> float:
    """Least-squares risk budget objective."""
    w = np.asarray(w, dtype=float)
    portfolio_var = float(w @ cov @ w)
    if portfolio_var < 1e-16:
        # Degenerate case: equal weighted penalty
        return float(np.sum((w - budget) ** 2) * 1e6)

    marginal_risk = cov @ w
    rc = w * marginal_risk / portfolio_var
    return float(np.sum((rc - budget) ** 2))


def _solve_with_slsqp(
    cov: np.ndarray,
    budget: np.ndarray,
    bounds,
    max_iter: int,
    tol: float
) -> Optional[np.ndarray]:
    """Solve using SLSQP."""
    n = len(budget)
    x0 = _initial_guess(cov, budget)

    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    try:
        result = minimize(
            _risk_budget_objective,
            x0,
            args=(cov, budget),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": max_iter, "ftol": tol},
        )
        if result.success and result.x is not None:
            w = np.maximum(result.x, 0)
            w = w / w.sum()
            return w
    except Exception:
        pass
    return None


def _solve_with_trust_constr(
    cov: np.ndarray,
    budget: np.ndarray,
    bounds,
    max_iter: int,
    tol: float
) -> Optional[np.ndarray]:
    """Solve using trust-constr (interior point)."""
    n = len(budget)
    x0 = _initial_guess(cov, budget)

    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    try:
        result = minimize(
            _risk_budget_objective,
            x0,
            args=(cov, budget),
            method="trust-constr",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": max_iter, "gtol": tol, "xtol": tol},
        )
        if result.success and result.x is not None:
            w = np.maximum(result.x, 0)
            w = w / w.sum()
            return w
    except Exception:
        pass
    return None


def _solve_unconstrained(
    cov: np.ndarray,
    budget: np.ndarray,
    random_seed: int
) -> Optional[np.ndarray]:
    """
    Solve unconstrained risk budget problem with multi-start.
    """
    np.random.seed(random_seed)
    n = len(budget)
    best_obj = np.inf
    best_w = None

    # Try several initial guesses
    initial_guesses = [
        budget,
        np.ones(n) / n,
        budget / np.sqrt(np.diag(cov) + 1e-12),
    ]

    for x0 in initial_guesses:
        x0 = np.asarray(x0, dtype=float)
        x0 = x0 / x0.sum()
        try:
            result = minimize(
                _risk_budget_objective,
                x0,
                args=(cov, budget),
                method="SLSQP",
                constraints={"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
                bounds=[(0, 1)] * n,
                options={"maxiter": 1000, "ftol": 1e-10},
            )
            if result.success and result.x is not None:
                obj = _risk_budget_objective(result.x, cov, budget)
                if obj < best_obj:
                    best_obj = obj
                    best_w = result.x
        except Exception:
            continue

    if best_w is not None:
        w = np.maximum(best_w, 0)
        w = w / w.sum()
        return w
    return None


def _inverse_volatility_approx(cov: np.ndarray, budget: np.ndarray) -> np.ndarray:
    """
    Inverse-volatility fallback: w_i ∝ b_i / σ_i
    """
    vols = np.sqrt(np.diag(cov))
    raw = budget / (vols + 1e-12)
    w = raw / raw.sum()
    return w


def _initial_guess(cov: np.ndarray, budget: np.ndarray) -> np.ndarray:
    """Generate a reasonable initial guess."""
    vols = np.sqrt(np.diag(cov))
    raw = budget / (vols + 1e-12)
    w = raw / raw.sum()
    return w


def _check_valid(w: np.ndarray, bounds, tol: float = 1e-6) -> bool:
    """Check if weights satisfy bounds and sum to 1."""
    if w is None or np.any(np.isnan(w)):
        return False
    if not np.isclose(w.sum(), 1.0, atol=tol):
        return False
    for i, (lb, ub) in enumerate(bounds):
        if w[i] < lb - tol or w[i] > ub + tol:
            return False
    return True
