"""
Probability and simulation: Monte Carlo, GBM price paths, expected return.
"""
import numpy as np
import pandas as pd

from backend.config import MC_SIMULATIONS, MC_HORIZON_DAYS, RANDOM_STATE


def monte_carlo(close: pd.Series,
                n_sims: int = MC_SIMULATIONS,
                horizon: int = MC_HORIZON_DAYS) -> dict:
    """
    GBM-based Monte Carlo simulation.

    Estimates the forward distribution of prices over *horizon* days.
    Returns percentile bands and a probability-weighted signal.
    """
    log_rets = np.log(close / close.shift(1)).dropna()
    mu    = float(log_rets.mean())
    sigma = float(log_rets.std())
    S0    = float(close.iloc[-1])

    rng = np.random.default_rng(RANDOM_STATE)
    Z = rng.standard_normal((horizon, n_sims))

    # Daily GBM step: S(t) = S(t-1) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
    dt = 1.0
    log_steps = (mu - 0.5 * sigma ** 2) * dt + sigma * (dt ** 0.5) * Z
    paths = S0 * np.exp(np.cumsum(log_steps, axis=0))   # shape: (horizon, n_sims)

    terminal = paths[-1, :]
    prob_up   = float(np.mean(terminal > S0))
    median_t  = float(np.median(terminal))
    expected  = float(np.mean(terminal))

    # Signal: P(up > 0.5) on a [-1,+1] scale
    signal = float(np.clip((prob_up - 0.5) * 4, -1, 1))

    # Fan chart percentile bands (for frontend viz)
    percentiles = [5, 25, 50, 75, 95]
    fan = {
        str(p): [round(float(paths[d, :].mean()), 2)   # mean path approximation
                 if False else round(float(np.percentile(paths[d, :], p)), 2)
                 for d in range(horizon)]
        for p in percentiles
    }

    return {
        "prob_up": round(prob_up, 4),
        "expected_price": round(expected, 2),
        "median_price": round(median_t, 2),
        "current_price": round(S0, 2),
        "expected_return_pct": round((expected - S0) / S0 * 100, 3),
        "signal": round(signal, 4),
        "fan_chart": fan,
        "horizon_days": horizon,
        "n_simulations": n_sims,
    }


def gbm_signal(close: pd.Series) -> dict:
    """
    Single-path GBM one-step look-ahead signal.
    Lighter than full MC — used as a quick stochastic indicator.
    """
    log_rets = np.log(close / close.shift(1)).dropna()
    mu    = float(log_rets.mean())
    sigma = float(log_rets.std())
    S0    = float(close.iloc[-1])

    rng = np.random.default_rng(RANDOM_STATE + 1)
    n_fwd = 5
    Z = rng.standard_normal(n_fwd)
    fwd_prices = [S0]
    for z in Z:
        fwd_prices.append(fwd_prices[-1] * np.exp((mu - 0.5 * sigma ** 2) + sigma * z))

    ret_5d = (fwd_prices[-1] - S0) / S0
    signal = float(np.clip(ret_5d / 0.03, -1, 1))   # 3 % move = full signal
    return {
        "fwd_5d_price": round(fwd_prices[-1], 2),
        "fwd_5d_return_pct": round(ret_5d * 100, 3),
        "signal": round(signal, 4),
    }


def expected_return(close: pd.Series, risk_free_rate: float = 0.065) -> dict:
    """
    Annualised expected return and Sharpe proxy from historical data.
    Risk-free rate defaults to approximate Indian 10-yr G-Sec yield.
    """
    daily_rets = close.pct_change().dropna()
    annual_ret = float(daily_rets.mean() * 252)
    annual_vol = float(daily_rets.std() * (252 ** 0.5))
    sharpe = (annual_ret - risk_free_rate) / (annual_vol + 1e-10)
    return {
        "annual_return": round(annual_ret, 4),
        "annual_volatility": round(annual_vol, 4),
        "sharpe_ratio": round(sharpe, 4),
        "risk_free_rate": risk_free_rate,
    }
