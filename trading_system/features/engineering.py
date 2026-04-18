"""
Feature engineering layer.

WHY each feature:

  daily_return       — raw price change signal; used to compute volatility and momentum
  log_return         — additive across time; better for statistical modelling
  ma_{n}             — trend proxies at different timescales; crossing MAs signal regime change
  ma_ratio_{f}_{s}   — normalised trend strength (avoids price-level dependence)
  rsi                — bounded momentum oscillator; identifies exhaustion / reversal risk
  atr                — volatility-adjusted stop placement; ATR stops adapt to market conditions
  volatility_{n}     — rolling std of returns; regime detection and position sizing
  volume_ratio       — current volume / rolling mean; confirms breakouts with conviction
  volume_spike       — binary flag for unusually high volume days
  price_vs_ma50      — price location relative to longer-term trend; regime filter
  bb_upper/lower     — Bollinger bands; mean-reversion reference levels
  bb_width           — band width (proxy for volatility compression / expansion)

All features are computed with a strict look-back only on past data.
No .shift() games needed for the indicators themselves — they are inherently
lagged by construction. The *signal* layer applies the execution lag.
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd

from trading_system.config import FeatureConfig

logger = logging.getLogger(__name__)


def add_features(df: pd.DataFrame, cfg: FeatureConfig) -> pd.DataFrame:
    """
    Add all technical features to a single-symbol OHLCV DataFrame.
    Returns a new DataFrame (does not mutate input).
    Rows with NaN features (warm-up period) are NOT dropped here —
    the strategy layer handles that via the warmup_period config.
    """
    df = df.copy()

    df = _returns(df)
    df = _moving_averages(df, cfg.ma_windows)
    df = _rsi(df, cfg.rsi_period)
    df = _atr(df, cfg.atr_period)
    df = _volatility(df, cfg.volatility_window)
    df = _volume_features(df, cfg.volume_spike_window, cfg.volume_spike_threshold)
    df = _bollinger_bands(df, window=20, n_std=2.0)

    return df


# ---------------------------------------------------------------------------
# Individual feature builders
# ---------------------------------------------------------------------------

def _returns(df: pd.DataFrame) -> pd.DataFrame:
    df["daily_return"] = df["close"].pct_change()
    df["log_return"] = np.log(df["close"] / df["close"].shift(1))
    return df


def _moving_averages(df: pd.DataFrame, windows: list) -> pd.DataFrame:
    for w in windows:
        df[f"ma_{w}"] = df["close"].rolling(w, min_periods=w).mean()

    # Trend strength ratios for each adjacent pair
    sorted_windows = sorted(windows)
    for fast, slow in zip(sorted_windows, sorted_windows[1:]):
        col = f"ma_ratio_{fast}_{slow}"
        df[col] = df[f"ma_{fast}"] / df[f"ma_{slow}"] - 1.0

    return df


def _rsi(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """
    Wilder's RSI using exponential smoothing (the standard definition).
    Using EWM with alpha=1/period reproduces Wilder's original formula.
    """
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def _atr(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """
    Average True Range — the volatility-normalised unit for stop placement.
    True Range = max(H-L, |H-prev_C|, |L-prev_C|)
    """
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

    df["atr"] = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return df


def _volatility(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    Annualised rolling volatility from log returns.
    Used for regime detection and position sizing.
    """
    df[f"volatility_{window}"] = (
        df["log_return"].rolling(window, min_periods=window).std() * np.sqrt(252)
    )
    return df


def _volume_features(df: pd.DataFrame, window: int, threshold: float) -> pd.DataFrame:
    """
    Volume ratio vs rolling mean — confirms directional moves.
    A ratio > threshold indicates unusual participation (institutional flow proxy).
    """
    rolling_vol_mean = df["volume"].rolling(window, min_periods=window).mean()
    df["volume_ratio"] = df["volume"] / rolling_vol_mean
    df["volume_spike"] = (df["volume_ratio"] >= threshold).astype(int)
    return df


def _bollinger_bands(df: pd.DataFrame, window: int, n_std: float) -> pd.DataFrame:
    """
    Bollinger Bands — useful for mean-reversion regime identification
    and as secondary exit signals when price stretches too far.
    """
    ma = df["close"].rolling(window, min_periods=window).mean()
    std = df["close"].rolling(window, min_periods=window).std()

    df["bb_mid"] = ma
    df["bb_upper"] = ma + n_std * std
    df["bb_lower"] = ma - n_std * std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / ma
    df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    return df


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def add_features_universe(
    universe: Dict[str, pd.DataFrame],
    cfg: FeatureConfig,
) -> Dict[str, pd.DataFrame]:
    """Apply feature engineering to all symbols in the universe."""
    result = {}
    for sym, df in universe.items():
        try:
            result[sym] = add_features(df, cfg)
            logger.info("%s: features added (%d rows)", sym, len(df))
        except Exception as exc:
            logger.error("Feature engineering failed for %s: %s", sym, exc)
    return result


def feature_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Quick diagnostic: mean/std/NaN count for all feature columns."""
    feature_cols = [c for c in df.columns if c not in ("open", "high", "low", "close", "volume")]
    summary = df[feature_cols].agg(["mean", "std", "min", "max"]).T
    summary["nan_count"] = df[feature_cols].isna().sum()
    return summary.round(4)
