"""
Zerodha Kite Connect data provider for TradingAgents.

Replaces yfinance for OHLCV and technical indicators using live NSE data.
Output format matches yfinance exactly so all agents work without changes.

Env vars required (set in .env):
    KITE_API_KEY
    KITE_ACCESS_TOKEN   ← refreshed daily via: python -m trading_system.data.kite_login

Kite symbols: plain NSE format — "RELIANCE", "TCS", "INFY"
              (strip .NS / .BO before passing here)

Falls back to yfinance if Kite credentials are absent.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Annotated

import pandas as pd

from .stockstats_utils import _clean_dataframe

logger = logging.getLogger(__name__)

# ── Instrument token cache (one API call per session) ─────────────────────────
_TOKEN_CACHE: dict = {}


def _kite_client():
    """Return a connected KiteConnect client or None if credentials missing."""
    api_key      = os.environ.get("KITE_API_KEY", "").strip()
    access_token = os.environ.get("KITE_ACCESS_TOKEN", "").strip()
    if not api_key or not access_token:
        return None
    try:
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        return kite
    except ImportError:
        logger.warning("kiteconnect not installed: pip install kiteconnect")
        return None


def _plain_symbol(symbol: str) -> str:
    """Strip exchange suffixes: RELIANCE.NS → RELIANCE"""
    return symbol.upper().replace(".NS", "").replace(".BO", "")


def _get_token(kite, symbol: str) -> int:
    """Resolve NSE instrument token (cached per session)."""
    if symbol in _TOKEN_CACHE:
        return _TOKEN_CACHE[symbol]
    instruments = kite.instruments("NSE")
    for inst in instruments:
        _TOKEN_CACHE[inst["tradingsymbol"]] = inst["instrument_token"]
    if symbol not in _TOKEN_CACHE:
        raise ValueError(
            f"'{symbol}' not found on NSE. "
            f"Check spelling — use plain symbol e.g. 'RELIANCE' not 'RELIANCE.NS'."
        )
    return _TOKEN_CACHE[symbol]


def _fetch_ohlcv(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch OHLCV from Kite and return a clean DataFrame with columns:
    [Date, Open, High, Low, Close, Volume]
    """
    kite        = _kite_client()
    plain_sym   = _plain_symbol(symbol)

    if kite is None:
        # Fallback to yfinance
        logger.warning("Kite credentials missing — falling back to yfinance for %s", symbol)
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        raw    = ticker.history(start=start_date, end=end_date)
        if raw.empty:
            return pd.DataFrame()
        raw = raw.reset_index()
        raw.columns = [c.title() for c in raw.columns]
        raw["Date"] = pd.to_datetime(raw["Date"]).dt.tz_localize(None).dt.normalize()
        return raw[["Date", "Open", "High", "Low", "Close", "Volume"]]

    token   = _get_token(kite, plain_sym)
    from_dt = datetime.strptime(start_date, "%Y-%m-%d")
    to_dt   = datetime.strptime(end_date,   "%Y-%m-%d")

    logger.info("[Kite] Fetching %s (%d) %s → %s", plain_sym, token, start_date, end_date)
    records = kite.historical_data(token, from_dt, to_dt, "day")

    if not records:
        raise ValueError(f"No data from Kite for {plain_sym} ({start_date} → {end_date})")

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df.rename(columns={
        "date":   "Date",
        "open":   "Open",
        "high":   "High",
        "low":    "Low",
        "close":  "Close",
        "volume": "Volume",
    })
    return df[["Date", "Open", "High", "Low", "Close", "Volume"]].sort_values("Date").reset_index(drop=True)


# ── Public functions matching yfinance interface ───────────────────────────────

def get_kite_data(
    symbol:     Annotated[str, "NSE ticker symbol (e.g. RELIANCE or RELIANCE.NS)"],
    start_date: Annotated[str, "Start date yyyy-mm-dd"],
    end_date:   Annotated[str, "End date yyyy-mm-dd"],
) -> str:
    """
    Fetch OHLCV from Kite and return a CSV string.
    Output format identical to yfinance so TradingAgents agents work unchanged.
    """
    plain_sym = _plain_symbol(symbol)
    try:
        df = _fetch_ohlcv(symbol, start_date, end_date)
    except Exception as exc:
        return f"Error fetching Kite data for {plain_sym}: {exc}"

    if df.empty:
        return f"No data found for '{plain_sym}' between {start_date} and {end_date}"

    # Cap to last 15 trading days — keeps Groq free-tier token usage under limit
    df = df.tail(15).reset_index(drop=True)

    df["Open"]  = df["Open"].round(2)
    df["High"]  = df["High"].round(2)
    df["Low"]   = df["Low"].round(2)
    df["Close"] = df["Close"].round(2)

    header = (
        f"# Stock data for {plain_sym} (NSE) from {start_date} to {end_date}\n"
        f"# Source: Zerodha Kite Connect\n"
        f"# Total records: {len(df)}\n"
        f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + df.to_csv(index=False)


_IND_DESCRIPTIONS = {
    "close_50_sma": "50 SMA: Medium-term trend indicator.",
    "close_200_sma": "200 SMA: Long-term trend benchmark.",
    "close_10_ema": "10 EMA: Responsive short-term average.",
    "macd":  "MACD: Momentum via EMA differences; watch crossovers.",
    "macds": "MACD Signal: EMA of MACD line; crossovers trigger trades.",
    "macdh": "MACD Histogram: Gap between MACD and signal; shows momentum.",
    "rsi":   "RSI: Overbought >70, oversold <30.",
    "boll":  "Bollinger Middle: 20 SMA base band.",
    "boll_ub": "Bollinger Upper Band: Overbought / breakout zone.",
    "boll_lb": "Bollinger Lower Band: Oversold / support zone.",
    "atr":   "ATR: Volatility; use for stop-loss sizing.",
    "vwma":  "VWMA: Volume-weighted moving average.",
    "mfi":   "MFI: Money Flow Index; overbought >80, oversold <20.",
}


def get_kite_indicators_window(
    symbol:         Annotated[str, "NSE ticker symbol"],
    indicator:      Annotated[str, "Technical indicator name"],
    curr_date:      Annotated[str, "Current trading date YYYY-MM-DD"],
    look_back_days: Annotated[int, "Number of days to look back"],
) -> str:
    """
    Compute technical indicators on Kite OHLCV data using stockstats.
    Matches the output format of get_stock_stats_indicators_window (yfinance version).
    """
    from stockstats import wrap as stockstats_wrap

    # Cap look_back to 10 days — keeps Groq free-tier token usage under limit
    look_back_days = min(look_back_days, 10)

    end_dt     = datetime.strptime(curr_date, "%Y-%m-%d")
    before_dt  = end_dt - timedelta(days=look_back_days)
    # Extra warmup history so long-period indicators (200 SMA etc.) are valid
    start_dt   = end_dt - timedelta(days=look_back_days + 300)

    try:
        df = _fetch_ohlcv(symbol, start_dt.strftime("%Y-%m-%d"), curr_date)
    except Exception as exc:
        return f"Error fetching Kite indicator data for {symbol}: {exc}"

    if df.empty:
        return f"No Kite data available for {symbol} up to {curr_date}"

    df = _clean_dataframe(df)

    # stockstats needs lowercase column names
    df_ss = df.rename(columns={
        "Date": "date", "Open": "open", "High": "high",
        "Low": "low", "Close": "close", "Volume": "volume",
    })
    df_ss = df_ss.set_index("date")
    wrapped = stockstats_wrap(df_ss)

    try:
        wrapped[indicator]  # trigger calculation
    except Exception as exc:
        return f"Error computing {indicator} for {symbol}: {exc}"

    wrapped = wrapped.reset_index()
    wrapped["date"] = pd.to_datetime(wrapped["date"]).dt.normalize()

    # Filter to look-back window
    mask = (wrapped["date"] >= pd.Timestamp(before_dt)) & (wrapped["date"] <= pd.Timestamp(end_dt))
    window = wrapped[mask].sort_values("date", ascending=False)

    ind_string = ""
    for _, row in window.iterrows():
        val = row.get(indicator, "N/A")
        ind_string += f"{row['date'].strftime('%Y-%m-%d')}: {val}\n"

    if not ind_string:
        ind_string = "N/A: No trading data in this window\n"

    description = _IND_DESCRIPTIONS.get(indicator, "")
    return (
        f"## {indicator} values from {before_dt.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        + ind_string
        + f"\n\n{description}"
    )
