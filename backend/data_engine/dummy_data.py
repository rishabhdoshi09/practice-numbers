"""
TEST-ONLY: GBM-based synthetic OHLCV generator.

Used exclusively in unit tests (backend/tests/).
NOT imported anywhere in production code — all production paths use
yFinance or Zerodha Kite Connect for real market data.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from backend.config import RANDOM_STATE

# Approximate seed prices and annual vol for major Indian equities
_SEED: dict[str, dict] = {
    "RELIANCE.NS":   {"price": 2850.0, "vol": 0.22, "drift": 0.12},
    "TCS.NS":        {"price": 3900.0, "vol": 0.20, "drift": 0.10},
    "INFY.NS":       {"price": 1520.0, "vol": 0.21, "drift": 0.09},
    "HDFCBANK.NS":   {"price": 1680.0, "vol": 0.19, "drift": 0.11},
    "ICICIBANK.NS":  {"price": 1120.0, "vol": 0.23, "drift": 0.13},
    "HINDUNILVR.NS": {"price": 2420.0, "vol": 0.16, "drift": 0.08},
    "BAJFINANCE.NS": {"price": 7200.0, "vol": 0.28, "drift": 0.15},
    "WIPRO.NS":      {"price": 480.0,  "vol": 0.22, "drift": 0.08},
    "SBIN.NS":       {"price": 810.0,  "vol": 0.25, "drift": 0.12},
    "TATAMOTORS.NS": {"price": 960.0,  "vol": 0.30, "drift": 0.14},
    "ADANIPORTS.NS": {"price": 1380.0, "vol": 0.26, "drift": 0.16},
    "ASIANPAINT.NS": {"price": 2960.0, "vol": 0.18, "drift": 0.09},
    "AXISBANK.NS":   {"price": 1240.0, "vol": 0.24, "drift": 0.13},
    "BHARTIARTL.NS": {"price": 1560.0, "vol": 0.20, "drift": 0.14},
    "ITC.NS":        {"price": 450.0,  "vol": 0.15, "drift": 0.10},
}

_DEFAULT_SEED = {"price": 1000.0, "vol": 0.22, "drift": 0.10}


def generate_ohlcv(symbol: str, days: int = 365) -> pd.DataFrame:
    """
    Simulate a realistic OHLCV time series for *symbol* over *days* trading days.

    GBM drives close prices; intraday H/L/O are derived from close with a
    realistic intraday range proportional to daily volatility.
    """
    rng = np.random.default_rng(RANDOM_STATE + hash(symbol) % 10_000)
    params = _SEED.get(symbol, _DEFAULT_SEED)

    S0 = params["price"]
    mu = params["drift"] / 252         # daily drift
    sigma = params["vol"] / (252 ** 0.5)  # daily volatility

    # Generate trading dates first, then match array lengths to actual count
    end_date = datetime.today()
    trading_dates = pd.bdate_range(end=end_date, periods=days)
    n = len(trading_dates)  # use actual length to avoid pandas/numpy mismatch

    # GBM log-returns
    z = rng.standard_normal(n)
    log_returns = (mu - 0.5 * sigma ** 2) + sigma * z
    prices = S0 * np.exp(np.cumsum(log_returns))

    # Intraday range ~ half the daily vol applied as symmetric band
    intraday_range = prices * sigma * rng.uniform(0.5, 1.5, n)

    opens  = prices * (1 + rng.uniform(-0.005, 0.005, n))
    highs  = prices + intraday_range * rng.uniform(0.3, 0.7, n)
    lows   = prices - intraday_range * rng.uniform(0.3, 0.7, n)
    # Ensure OHLC consistency
    highs  = np.maximum(highs, np.maximum(opens, prices))
    lows   = np.minimum(lows,  np.minimum(opens, prices))

    # Volume: mean-reverting around a base, correlated slightly with abs returns
    base_vol = S0 * 1_000
    vol_noise = rng.lognormal(0, 0.5, n)
    volumes = (base_vol * vol_noise * (1 + 3 * np.abs(log_returns))).astype(int)

    df = pd.DataFrame({
        "Date":   trading_dates,
        "Open":   np.round(opens, 2),
        "High":   np.round(highs, 2),
        "Low":    np.round(lows, 2),
        "Close":  np.round(prices, 2),
        "Volume": volumes,
    })
    df.set_index("Date", inplace=True)
    return df


def generate_order_book(symbol: str, mid_price: float) -> dict:
    """Simulate a 5-level order book snapshot."""
    rng = np.random.default_rng(RANDOM_STATE)
    tick = round(mid_price * 0.0005, 2)
    bids = [
        {"price": round(mid_price - i * tick, 2), "qty": int(rng.integers(100, 2000))}
        for i in range(1, 6)
    ]
    asks = [
        {"price": round(mid_price + i * tick, 2), "qty": int(rng.integers(100, 2000))}
        for i in range(1, 6)
    ]
    return {"bids": bids, "asks": asks}


def generate_news(symbol: str) -> list[dict]:
    """Return a curated list of dummy news headlines with pre-scored sentiment."""
    ticker = symbol.split(".")[0]
    return [
        {
            "headline": f"{ticker} Q4 earnings beat estimates; net profit up 18% YoY",
            "source": "Economic Times",
            "sentiment": "positive",
            "score": 0.72,
            "timestamp": (datetime.today() - timedelta(hours=3)).isoformat(),
        },
        {
            "headline": f"Brokerage upgrades {ticker} to 'Buy' with revised target price",
            "source": "Moneycontrol",
            "sentiment": "positive",
            "score": 0.65,
            "timestamp": (datetime.today() - timedelta(hours=8)).isoformat(),
        },
        {
            "headline": "Global markets cautious ahead of US Fed rate decision",
            "source": "Reuters",
            "sentiment": "neutral",
            "score": 0.05,
            "timestamp": (datetime.today() - timedelta(hours=12)).isoformat(),
        },
    ]
