"""
Data ingestion layer.

Responsibilities:
  - Fetch OHLCV data from yfinance (free, reliable for NSE/BSE via .NS/.BO suffix)
  - Validate time-series integrity (no gaps, no forward-fill leakage)
  - Return clean, timezone-naive DataFrames indexed by date

Design decisions:
  - We download raw data, then clean — never modify in place before validation
  - Timestamps are converted to date-only (no intraday ambiguity for daily data)
  - Missing data policy: forward-fill up to 3 days (exchange holidays), then drop
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not installed — install with: pip install yfinance")


# ---------------------------------------------------------------------------
# Core fetch
# ---------------------------------------------------------------------------

def fetch_ohlcv(
    symbol: str,
    start: str,
    end: str,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Download OHLCV data for a single symbol.

    Returns a DataFrame with columns: [open, high, low, close, volume]
    Index is DatetimeIndex (date only, UTC-naive).

    Raises ValueError if fewer than 50 rows are returned (insufficient history).
    """
    if not YFINANCE_AVAILABLE:
        raise ImportError("yfinance is required: pip install yfinance")

    logger.info("Fetching %s from %s to %s", symbol, start, end)
    ticker = yf.Ticker(symbol)
    raw = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)

    if raw.empty:
        raise ValueError(f"No data returned for {symbol}. Check symbol or date range.")

    # Normalise column names to lowercase
    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]

    # Strip timezone info — we work in exchange-local date space
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "date"

    df = _clean(df, symbol)

    if len(df) < 50:
        raise ValueError(
            f"{symbol}: only {len(df)} rows after cleaning — need at least 50."
        )

    logger.info("%s: %d rows loaded (%s → %s)", symbol, len(df),
                df.index[0].date(), df.index[-1].date())
    return df


def fetch_universe(
    symbols: List[str],
    start: str,
    end: str,
    interval: str = "1d",
) -> Dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for a list of symbols.
    Symbols that fail are logged and excluded (no crash on partial failure).
    """
    universe: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            universe[sym] = fetch_ohlcv(sym, start, end, interval)
        except Exception as exc:
            logger.error("Skipping %s: %s", sym, exc)

    if not universe:
        raise RuntimeError("All symbols failed to load. Check connectivity and symbols.")

    logger.info("Loaded %d / %d symbols", len(universe), len(symbols))
    return universe


# ---------------------------------------------------------------------------
# Cleaning helpers
# ---------------------------------------------------------------------------

def _clean(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Validate and clean a raw OHLCV DataFrame.

    Steps:
    1. Remove duplicate dates (keep last — some feeds have pre/post market dupes)
    2. Enforce monotonically increasing index (sort if needed)
    3. Remove rows with zero or negative prices/volume
    4. Forward-fill gaps up to 3 consecutive days (exchange holidays)
    5. Drop any remaining NaN rows
    6. Assert OHLC consistency: high >= open/close, low <= open/close
    """
    # 1. Dedup
    n_dupes = df.index.duplicated().sum()
    if n_dupes:
        logger.warning("%s: dropping %d duplicate dates", symbol, n_dupes)
        df = df[~df.index.duplicated(keep="last")]

    # 2. Sort
    df = df.sort_index()

    # 3. Remove bad prices
    bad_price = (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    bad_vol = df["volume"] < 0
    n_bad = (bad_price | bad_vol).sum()
    if n_bad:
        logger.warning("%s: removing %d rows with invalid prices/volume", symbol, n_bad)
        df = df[~(bad_price | bad_vol)]

    # 4. Forward-fill gaps (holiday NaNs introduced after reindex) — max 3 days
    full_idx = pd.date_range(df.index.min(), df.index.max(), freq="B")
    df = df.reindex(full_idx)
    df = df.ffill(limit=3)
    df.index.name = "date"

    # 5. Drop residual NaNs
    n_nan = df.isna().any(axis=1).sum()
    if n_nan:
        logger.warning("%s: dropping %d NaN rows after forward-fill", symbol, n_nan)
        df = df.dropna()

    # 6. OHLC sanity check
    inconsistent = (
        (df["high"] < df["open"]) |
        (df["high"] < df["close"]) |
        (df["low"] > df["open"]) |
        (df["low"] > df["close"])
    )
    n_bad_ohlc = inconsistent.sum()
    if n_bad_ohlc:
        logger.warning("%s: %d rows with inconsistent OHLC — dropping", symbol, n_bad_ohlc)
        df = df[~inconsistent]

    return df


# ---------------------------------------------------------------------------
# Data quality report
# ---------------------------------------------------------------------------

def data_quality_report(universe: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Return a summary DataFrame showing data coverage and basic stats per symbol.
    Useful for spotting thin or suspect data before feeding into the pipeline.
    """
    rows = []
    for sym, df in universe.items():
        rows.append({
            "symbol": sym,
            "rows": len(df),
            "start": df.index[0].date(),
            "end": df.index[-1].date(),
            "missing_pct": round(df.isna().mean().mean() * 100, 3),
            "avg_volume": int(df["volume"].mean()),
            "avg_close": round(df["close"].mean(), 2),
        })
    report = pd.DataFrame(rows).set_index("symbol")
    return report
