"""
Markowitz Mean-Variance Optimisation for multi-asset portfolios.
Finds the efficient frontier and the max-Sharpe / min-variance portfolios.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from backend.config import RANDOM_STATE


def optimize_portfolio(returns_df: pd.DataFrame,
                       risk_free_rate: float = 0.065,
                       n_frontier_points: int = 100) -> dict:
    """
    Given a DataFrame where each column is a daily return series for one asset,
    compute the Markowitz efficient frontier and identify:
      - Max-Sharpe portfolio
      - Min-Variance portfolio

    Returns weights, expected returns, volatilities, and Sharpe ratios.
    """
    mu  = returns_df.mean() * 252           # annualised expected returns
    cov = returns_df.cov() * 252            # annualised covariance matrix
    n   = len(mu)
    assets = returns_df.columns.tolist()

    def portfolio_stats(w: np.ndarray) -> tuple[float, float]:
        ret = float(w @ mu)
        vol = float(np.sqrt(w @ cov.values @ w))
        return ret, vol

    def neg_sharpe(w: np.ndarray) -> float:
        ret, vol = portfolio_stats(w)
        return -(ret - risk_free_rate) / (vol + 1e-10)

    def portfolio_vol(w: np.ndarray) -> float:
        return portfolio_stats(w)[1]

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0.0, 1.0)] * n
    w0 = np.full(n, 1.0 / n)

    # Max-Sharpe
    res_sharpe = minimize(neg_sharpe, w0, method="SLSQP",
                          bounds=bounds, constraints=constraints,
                          options={"maxiter": 500})
    w_sharpe = res_sharpe.x if res_sharpe.success else w0
    ret_s, vol_s = portfolio_stats(w_sharpe)

    # Min-Variance
    res_minvar = minimize(portfolio_vol, w0, method="SLSQP",
                          bounds=bounds, constraints=constraints,
                          options={"maxiter": 500})
    w_minvar = res_minvar.x if res_minvar.success else w0
    ret_mv, vol_mv = portfolio_stats(w_minvar)

    # Efficient frontier sampling
    target_rets = np.linspace(float(mu.min()), float(mu.max()), n_frontier_points)
    frontier = []
    for target in target_rets:
        constr = constraints + [{"type": "eq", "fun": lambda w, t=target: w @ mu - t}]
        res = minimize(portfolio_vol, w0, method="SLSQP",
                       bounds=bounds, constraints=constr,
                       options={"maxiter": 300})
        if res.success:
            ret_f, vol_f = portfolio_stats(res.x)
            frontier.append({"return": round(ret_f, 4), "volatility": round(vol_f, 4)})

    return {
        "assets": assets,
        "max_sharpe": {
            "weights": {a: round(float(w), 4) for a, w in zip(assets, w_sharpe)},
            "expected_return": round(ret_s, 4),
            "volatility": round(vol_s, 4),
            "sharpe_ratio": round((ret_s - risk_free_rate) / (vol_s + 1e-10), 4),
        },
        "min_variance": {
            "weights": {a: round(float(w), 4) for a, w in zip(assets, w_minvar)},
            "expected_return": round(ret_mv, 4),
            "volatility": round(vol_mv, 4),
            "sharpe_ratio": round((ret_mv - risk_free_rate) / (vol_mv + 1e-10), 4),
        },
        "efficient_frontier": frontier,
    }
