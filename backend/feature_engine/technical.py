"""
Technical analysis indicators computed directly from OHLCV DataFrames.
All functions are pure — no side effects.
"""
import numpy as np
import pandas as pd

from backend.config import (
    SMA_SHORT, SMA_LONG, EMA_SPAN,
    RSI_PERIOD, ATR_PERIOD,
    BOLLINGER_PERIOD, BOLLINGER_STD,
)


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window, min_periods=1).mean()


def ema(close: pd.Series, span: int = EMA_SPAN) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing method)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series) -> dict[str, pd.Series]:
    """MACD line, signal line, and histogram."""
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    macd_line = fast - slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": macd_line - signal_line,
    }


def bollinger_bands(close: pd.Series,
                    period: int = BOLLINGER_PERIOD,
                    n_std: float = BOLLINGER_STD) -> dict[str, pd.Series]:
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    return {
        "upper": mid + n_std * std,
        "middle": mid,
        "lower": mid - n_std * std,
        "pct_b": (close - (mid - n_std * std)) / (2 * n_std * std + 1e-10),
    }


def atr(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = ATR_PERIOD) -> pd.Series:
    """Average True Range — measures volatility and drives stop placement."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume — accumulation/distribution proxy."""
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def trend_signal(close: pd.Series) -> float:
    """
    Aggregate trend score in [-1, +1].
    Combines SMA crossover and EMA slope, normalised.
    """
    s = sma(close, SMA_SHORT).iloc[-1]
    l = sma(close, SMA_LONG).iloc[-1]
    ema_now  = ema(close).iloc[-1]
    ema_prev = ema(close).iloc[-2]

    crossover_score = np.clip((s - l) / (l + 1e-10) * 10, -1, 1)
    slope_score     = np.clip((ema_now - ema_prev) / (ema_prev + 1e-10) * 100, -1, 1)
    return float((crossover_score + slope_score) / 2)


def momentum_signal(close: pd.Series) -> float:
    """
    Momentum score in [-1, +1] from RSI and MACD.
    RSI: 70+ is overbought (-1), 30- is oversold (+1).
    MACD: histogram sign gives direction.
    """
    rsi_val = rsi(close).iloc[-1]
    rsi_score = np.clip((50 - rsi_val) / 50, -1, 1)   # inverted: low RSI → buy

    macd_d = macd(close)
    hist = macd_d["histogram"].iloc[-1]
    macd_score = np.clip(hist / (abs(hist) + 1e-3), -1, 1)

    return float((rsi_score * 0.4 + macd_score * 0.6))
