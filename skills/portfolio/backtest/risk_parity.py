# skills/portfolio/backtest/risk_parity.py
"""
严格风险平价权重求解器（基于 cvxpy）
"""
import numpy as np
import cvxpy as cp
from typing import Optional


def risk_parity_weights(
    cov_matrix: np.ndarray,
    max_iter: int = 500,
    tol: float = 1e-8,
) -> np.ndarray:
    """
    使用 cvxpy 求解严格风险平价权重

    目标：最小化 sum((w_i * (Σw)_i - target)^2)
    约束：sum(w) = 1, w >= 0

    :param cov_matrix: n×n 协方差矩阵（必须对称正定）
    :param max_iter: cvxpy 求解器最大迭代次数
    :param tol: 收敛容差
    :return: n 维权重向量，和为 1，非负
    """
    n = cov_matrix.shape[0]
    if n == 1:
        return np.array([1.0])

    w = cp.Variable(n)
    sigma_w = cov_matrix @ w
    portfolio_var = cp.quad_form(w, cov_matrix)

    # 风险贡献向量
    # 为避免 portfolio_var 接近 0 时的数值问题，使用如下形式：
    # RC_i = w_i * (Σw)_i
    # 目标是让 RC_i 尽量相等
    rc = cp.multiply(w, sigma_w)
    target = portfolio_var / n

    # 最小化风险贡献的方差
    objective = cp.sum_squares(rc - target)

    constraints = [cp.sum(w) == 1, w >= 0]

    problem = cp.Problem(cp.Minimize(objective), constraints)

    # 尝试多种求解器
    solvers = [cp.OSQP, cp.ECOS, cp.SCS]
    for solver in solvers:
        try:
            problem.solve(solver=solver, verbose=False, max_iter=max_iter, eps_abs=tol, eps_rel=tol)
            if problem.status in ["optimal", "optimal_inaccurate"] and w.value is not None:
                weights = np.array(w.value).flatten()
                weights = np.maximum(weights, 0)
                weights = weights / weights.sum()
                return weights
        except Exception:
            continue

    # 如果 cvxpy 全部失败，fallback 到波动率倒数加权（近似风险平价）
    inv_vol = 1.0 / (np.sqrt(np.diag(cov_matrix)) + 1e-12)
    weights = inv_vol / inv_vol.sum()
    return weights


def risk_parity_with_target_vol(
    cov_matrix: np.ndarray,
    target_volatility: float = 0.06,
    max_leverage: float = 2.0,
    max_iter: int = 500,
    tol: float = 1e-8,
) -> np.ndarray:
    """
    带目标波动率的风险平价权重
    
    实现方式（方案A）：
    1. 先计算严格风险平价权重
    2. 计算当前组合年化波动率
    3. 按 target_vol / current_vol 的比例缩放权重
    4. 权重和可以 > 1（表示杠杆）
    
    :param cov_matrix: n×n 协方差矩阵（必须对称正定）
    :param target_volatility: 目标年化波动率（默认 6%）
    :param max_leverage: 最大杠杆倍数（默认 2.0）
    :param max_iter: cvxpy 求解器最大迭代次数
    :param tol: 收敛容差
    :return: n 维权重向量，sum(w) 可能 > 1（表示杠杆）
    """
    # 1. 计算严格风险平价权重
    w_rp = risk_parity_weights(cov_matrix, max_iter=max_iter, tol=tol)
    
    # 2. 计算当前组合年化波动率
    current_var = w_rp @ cov_matrix @ w_rp
    if current_var <= 0:
        return w_rp
    
    current_vol = np.sqrt(current_var) * np.sqrt(252)
    
    if current_vol < 1e-12:
        return w_rp
    
    # 3. 计算缩放系数
    scale = target_volatility / current_vol
    
    # 4. 限制最大杠杆
    if scale > max_leverage:
        scale = max_leverage
    
    # 5. 缩放权重（允许权重和 > 1，表示杠杆）
    w_new = w_rp * scale
    
    return w_new


def equal_weight_weights(n: int) -> np.ndarray:
    """等权重"""
    return np.ones(n) / n


def build_weights(
    method: str,
    cov_matrix: Optional[np.ndarray],
    user_weights: Optional[np.ndarray] = None,
    target_volatility: Optional[float] = None,
) -> np.ndarray:
    """
    根据方法生成目标权重

    :param method: risk_parity / risk_parity_target_vol / equal_weight / user_defined
    :param cov_matrix: 协方差矩阵（risk_parity 需要）
    :param user_weights: 用户指定权重（user_defined 需要）
    :param target_volatility: 目标年化波动率（risk_parity_target_vol 需要）
    :return: 权重向量
    """
    if method == "equal_weight":
        n = cov_matrix.shape[0] if cov_matrix is not None else len(user_weights)
        return equal_weight_weights(n)

    if method == "user_defined":
        if user_weights is None:
            raise ValueError("user_defined 方法必须提供 user_weights")
        w = np.array(user_weights, dtype=float)
        w = np.maximum(w, 0)
        return w / w.sum()

    if method == "risk_parity":
        if cov_matrix is None:
            raise ValueError("risk_parity 方法必须提供 cov_matrix")
        return risk_parity_weights(cov_matrix)
    
    if method == "risk_parity_target_vol":
        if cov_matrix is None:
            raise ValueError("risk_parity_target_vol 方法必须提供 cov_matrix")
        return risk_parity_with_target_vol(cov_matrix, target_volatility=target_volatility or 0.06)

    raise ValueError(f"未知的组合构建方法: {method}")
