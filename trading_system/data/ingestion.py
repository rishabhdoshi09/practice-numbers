"""
Data ingestion layer.

Sources (auto-detected via environment variables):
  1. Zerodha Kite Connect  — if KITE_API_KEY + KITE_ACCESS_TOKEN are set  (primary)
  2. yfinance              — fallback when Kite credentials are absent

Kite symbols use NSE format: "RELIANCE", "TCS", "INFY"
yfinance symbols use:        "RELIANCE.NS", "TCS.NS", "INFY.NS"

The rest of the pipeline always receives the same clean DataFrame:
  columns : [open, high, low, close, volume]
  index   : DatetimeIndex (date-only, UTC-naive)
"""

import logging
import os
from datetime import datetime, date
from typing import Dict, List

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

try:
    from kiteconnect import KiteConnect
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False


# ── Kite interval map ─────────────────────────────────────────────────────────
_KITE_INTERVAL = {
    "1m": "minute", "3m": "3minute", "5m": "5minute",
    "10m": "10minute", "15m": "15minute", "30m": "30minute",
    "60m": "60minute", "1h": "60minute", "1d": "day",
}

# ── Strip .NS / .BO suffix to get plain NSE symbol for Kite ──────────────────
def _kite_symbol(symbol: str) -> str:
    return symbol.upper().replace(".NS", "").replace(".BO", "")


# ── Build Kite client from env ────────────────────────────────────────────────
def _get_kite_client():
    api_key      = os.environ.get("KITE_API_KEY", "").strip()
    access_token = os.environ.get("KITE_ACCESS_TOKEN", "").strip()
    if not api_key or not access_token:
        return None
    if not KITE_AVAILABLE:
        logger.warning("kiteconnect not installed — pip install kiteconnect")
        return None
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


# ── Instrument token cache (one API call per session) ─────────────────────────
_TOKEN_CACHE: Dict[str, int] = {}

def _get_instrument_token(kite, symbol: str) -> int:
    """Resolve NSE instrument token for a symbol (cached)."""
    if symbol in _TOKEN_CACHE:
        return _TOKEN_CACHE[symbol]
    instruments = kite.instruments("NSE")
    token_map = {i["tradingsymbol"]: i["instrument_token"] for i in instruments}
    if symbol not in token_map:
        raise ValueError(
            f"'{symbol}' not found on NSE via Kite. "
            f"Check spelling (e.g. 'RELIANCE' not 'RELIANCE.NS')."
        )
    _TOKEN_CACHE.update(token_map)
    return token_map[symbol]


# ── Core fetch — Kite ─────────────────────────────────────────────────────────
def _fetch_kite(kite, symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
    kite_sym      = _kite_symbol(symbol)
    kite_interval = _KITE_INTERVAL.get(interval, "day")
    token         = _get_instrument_token(kite, kite_sym)

    logger.info("[Kite] Fetching %s (%d) from %s to %s [%s]",
                kite_sym, token, start, end, kite_interval)

    # Kite historical_data expects datetime objects
    from_dt = datetime.strptime(start, "%Y-%m-%d")
    to_dt   = datetime.strptime(end,   "%Y-%m-%d")

    records = kite.historical_data(token, from_dt, to_dt, kite_interval)
    if not records:
        raise ValueError(f"No data returned from Kite for {kite_sym}.")

    df = pd.DataFrame(records)
    df = df.rename(columns={
        "date": "date", "open": "open", "high": "high",
        "low": "low",   "close": "close", "volume": "volume",
    })
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df.set_index("date")[["open", "high", "low", "close", "volume"]]
    df.index.name = "date"
    return df


# ── Core fetch — yfinance ─────────────────────────────────────────────────────
def _fetch_yfinance(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
    if not YFINANCE_AVAILABLE:
        raise ImportError("yfinance not installed: pip install yfinance")
    logger.info("[yfinance] Fetching %s from %s to %s", symbol, start, end)
    ticker = yf.Ticker(symbol)
    raw    = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)
    if raw.empty:
        raise ValueError(f"No data from yfinance for {symbol}.")
    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index   = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "date"
    return df


# ── Public API ────────────────────────────────────────────────────────────────
def fetch_ohlcv(
    symbol: str,
    start: str,
    end: str,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Fetch OHLCV for one symbol.

    Auto-selects data source:
      • Kite  — when KITE_API_KEY + KITE_ACCESS_TOKEN are in environment
      • yfinance — otherwise (fallback)

    Returns clean DataFrame: columns [open, high, low, close, volume],
    index = DatetimeIndex (date-only, tz-naive).
    """
    kite = _get_kite_client()

    if kite:
        df = _fetch_kite(kite, symbol, start, end, interval)
    else:
        df = _fetch_yfinance(symbol, start, end, interval)

    df = _clean(df, symbol)

    if len(df) < 50:
        raise ValueError(f"{symbol}: only {len(df)} rows — need at least 50.")

    logger.info("%s: %d rows (%s → %s)", symbol,
                len(df), df.index[0].date(), df.index[-1].date())
    return df


def fetch_universe(
    symbols: List[str],
    start: str,
    end: str,
    interval: str = "1d",
) -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV for a list of symbols. Failed symbols are skipped."""
    kite = _get_kite_client()
    source = "Kite" if kite else "yfinance"
    logger.info("Data source: %s", source)
    print(f"  Data source: {source}")

    universe: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            universe[sym] = fetch_ohlcv(sym, start, end, interval)
        except Exception as exc:
            logger.error("Skipping %s: %s", sym, exc)

    if not universe:
        raise RuntimeError("All symbols failed. Check credentials and symbol names.")

    logger.info("Loaded %d / %d symbols", len(universe), len(symbols))
    return universe


# ── Cleaning ──────────────────────────────────────────────────────────────────
def _clean(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    # 1. Dedup
    dupes = df.index.duplicated().sum()
    if dupes:
        logger.warning("%s: dropping %d duplicate dates", symbol, dupes)
        df = df[~df.index.duplicated(keep="last")]

    # 2. Sort
    df = df.sort_index()

    # 3. Remove bad prices/volume
    bad = (df[["open", "high", "low", "close"]] <= 0).any(axis=1) | (df["volume"] < 0)
    if bad.sum():
        logger.warning("%s: removing %d bad rows", symbol, bad.sum())
        df = df[~bad]

    # 4. Forward-fill exchange holidays (max 3 consecutive)
    full_idx = pd.date_range(df.index.min(), df.index.max(), freq="B")
    df = df.reindex(full_idx).ffill(limit=3)
    df.index.name = "date"

    # 5. Drop residual NaNs
    nans = df.isna().any(axis=1).sum()
    if nans:
        logger.warning("%s: dropping %d NaN rows", symbol, nans)
        df = df.dropna()

    # 6. OHLC sanity
    bad_ohlc = (
        (df["high"] < df["open"]) | (df["high"] < df["close"]) |
        (df["low"]  > df["open"]) | (df["low"]  > df["close"])
    )
    if bad_ohlc.sum():
        logger.warning("%s: dropping %d inconsistent OHLC rows", symbol, bad_ohlc.sum())
        df = df[~bad_ohlc]

    return df


# ── Data quality report ───────────────────────────────────────────────────────
def data_quality_report(universe: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for sym, df in universe.items():
        rows.append({
            "symbol":      sym,
            "rows":        len(df),
            "start":       df.index[0].date(),
            "end":         df.index[-1].date(),
            "missing_pct": round(df.isna().mean().mean() * 100, 3),
            "avg_volume":  int(df["volume"].mean()),
            "avg_close":   round(df["close"].mean(), 2),
        })
    return pd.DataFrame(rows).set_index("symbol")
