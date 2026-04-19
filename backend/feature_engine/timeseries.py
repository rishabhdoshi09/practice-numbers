"""
Time-series modelling: ARIMA forecasting and GARCH volatility estimation.
Uses statsmodels for ARIMA and the arch library for GARCH.
"""
import logging
import warnings
import numpy as np
import pandas as pd

from backend.config import (
    ARIMA_ORDER, ARIMA_FORECAST_DAYS,
    GARCH_P, GARCH_Q,
)

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")   # suppress convergence noise in prod logs


def fit_arima(close: pd.Series) -> dict:
    """
    Fit ARIMA(p,d,q) to log-price series and return N-day ahead forecast.
    Falls back to naive drift if the model fails to converge.
    """
    log_prices = np.log(close.dropna())
    try:
        from statsmodels.tsa.arima.model import ARIMA
        model = ARIMA(log_prices, order=ARIMA_ORDER)
        result = model.fit()
        forecast_log = result.forecast(steps=ARIMA_FORECAST_DAYS)
        forecast_prices = np.exp(forecast_log)
        last_price = float(close.iloc[-1])
        forecast_return = float((forecast_prices.iloc[-1] - last_price) / last_price)
        # Normalise to [-1, +1] — a 5 % move in 5 days is considered "strong"
        signal = float(np.clip(forecast_return / 0.05, -1, 1))
        return {
            "forecast_prices": forecast_prices.tolist(),
            "forecast_return": round(forecast_return * 100, 3),
            "signal": round(signal, 4),
            "model": "ARIMA",
            "order": ARIMA_ORDER,
        }
    except Exception as exc:
        logger.warning("ARIMA failed: %s — using naive drift", exc)
        return _naive_drift(close)


def fit_garch(close: pd.Series) -> dict:
    """
    Fit GARCH(1,1) to percentage returns to estimate conditional volatility.
    Returns annualised vol estimate and a volatility-based signal.
    """
    pct_returns = close.pct_change().dropna() * 100   # GARCH prefers %
    try:
        from arch import arch_model
        model = arch_model(pct_returns, vol="GARCH", p=GARCH_P, q=GARCH_Q,
                           dist="Normal", rescale=False)
        result = model.fit(disp="off", show_warning=False)
        last_vol = float(result.conditional_volatility.iloc[-1])
        annual_vol = last_vol * (252 ** 0.5) / 100   # convert % to decimal, annualise
        # High vol → wider confidence band → dampen signal (negative score)
        vol_signal = float(np.clip(-annual_vol / 0.4, -1, 1))
        return {
            "conditional_vol_daily_pct": round(last_vol, 4),
            "annual_vol_estimate": round(annual_vol, 4),
            "signal": round(vol_signal, 4),
            "model": "GARCH(1,1)",
        }
    except Exception as exc:
        logger.warning("GARCH failed: %s — using rolling std", exc)
        std = float(pct_returns.rolling(20).std().iloc[-1])
        annual_vol = std * (252 ** 0.5) / 100
        vol_signal = float(np.clip(-annual_vol / 0.4, -1, 1))
        return {
            "conditional_vol_daily_pct": round(std, 4),
            "annual_vol_estimate": round(annual_vol, 4),
            "signal": round(vol_signal, 4),
            "model": "RollingStd fallback",
        }


def _naive_drift(close: pd.Series) -> dict:
    """Mean log-return drift as ARIMA fallback."""
    log_rets = np.diff(np.log(close.dropna().values))
    mean_ret = float(log_rets.mean())
    last_price = float(close.iloc[-1])
    fwd = [last_price * np.exp(mean_ret * (i + 1)) for i in range(ARIMA_FORECAST_DAYS)]
    ret = (fwd[-1] - last_price) / last_price
    return {
        "forecast_prices": [round(p, 2) for p in fwd],
        "forecast_return": round(ret * 100, 3),
        "signal": round(np.clip(ret / 0.05, -1, 1), 4),
        "model": "NaiveDrift",
        "order": None,
    }
