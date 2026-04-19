"""
Global market data fetcher.
Fetches indices, commodities, and sectoral data via yFinance with dummy fallbacks.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)

# ── Symbol maps ────────────────────────────────────────────────────────────────

GLOBAL_INDICES = {
    # India
    "^NSEI":   {"name": "Nifty 50",         "region": "India",        "flag": "🇮🇳"},
    "^NSEBANK":{"name": "Bank Nifty",        "region": "India",        "flag": "🇮🇳"},
    "^BSESN":  {"name": "Sensex",            "region": "India",        "flag": "🇮🇳"},
    # US
    "^GSPC":   {"name": "S&P 500",           "region": "North America","flag": "🇺🇸"},
    "^DJI":    {"name": "Dow Jones",         "region": "North America","flag": "🇺🇸"},
    "^IXIC":   {"name": "Nasdaq",            "region": "North America","flag": "🇺🇸"},
    "^VIX":    {"name": "VIX",               "region": "North America","flag": "🇺🇸"},
    # Europe
    "^FTSE":   {"name": "FTSE 100",          "region": "Europe",       "flag": "🇬🇧"},
    "^GDAXI":  {"name": "DAX",               "region": "Europe",       "flag": "🇩🇪"},
    "^FCHI":   {"name": "CAC 40",            "region": "Europe",       "flag": "🇫🇷"},
    # Asia
    "^N225":   {"name": "Nikkei 225",        "region": "Asia",         "flag": "🇯🇵"},
    "^HSI":    {"name": "Hang Seng",         "region": "Asia",         "flag": "🇭🇰"},
    "000001.SS":{"name": "Shanghai Comp",   "region": "Asia",         "flag": "🇨🇳"},
    # EM
    "^BVSP":   {"name": "Bovespa",           "region": "South America","flag": "🇧🇷"},
}

COMMODITIES = {
    "GC=F":  {"name": "Gold",    "unit": "USD/oz"},
    "SI=F":  {"name": "Silver",  "unit": "USD/oz"},
    "CL=F":  {"name": "Crude Oil","unit": "USD/bbl"},
    "BZ=F":  {"name": "Brent",   "unit": "USD/bbl"},
    "DX-Y.NYB": {"name": "USD Index", "unit": "pts"},
}

NIFTY_SECTORS = {
    "^CNXAUTO":  "Auto",
    "^CNXBANK":  "Banking",
    "^CNXIT":    "IT",
    "^CNXPHARMA":"Pharma",
    "^CNXFMCG":  "FMCG",
    "^CNXMETAL":  "Metals",
    "^CNXREALTY": "Realty",
    "^CNXENERGY": "Energy",
    "^CNXINFRA":  "Infra",
    "^CNXMEDIA":  "Media",
}

# Dummy close prices for fallback (approximate levels)
_DUMMY_CLOSES = {
    "^NSEI": 22400, "^NSEBANK": 48200, "^BSESN": 73800,
    "^GSPC": 5200,  "^DJI": 38500,     "^IXIC": 16200, "^VIX": 14.5,
    "^FTSE": 8100,  "^GDAXI": 18200,   "^FCHI": 8050,
    "^N225": 38500, "^HSI": 17200,     "000001.SS": 3050,
    "^BVSP": 127000,
    "GC=F": 2340,   "SI=F": 27.5,      "CL=F": 78.5, "BZ=F": 82.0, "DX-Y.NYB": 104.2,
}
for sym in NIFTY_SECTORS:
    _DUMMY_CLOSES[sym] = 15000

def _dummy_quote(symbol: str) -> dict:
    """Generate a plausible dummy quote with random daily change."""
    rng = np.random.default_rng(abs(hash(symbol + str(datetime.today().date()))) % 100_000)
    close = _DUMMY_CLOSES.get(symbol, 1000)
    chg_pct = float(rng.uniform(-1.5, 1.5))
    prev = close / (1 + chg_pct / 100)
    return {
        "close":    round(close, 2),
        "prev":     round(prev, 2),
        "change":   round(close - prev, 2),
        "chg_pct":  round(chg_pct, 2),
        "open":     round(prev * (1 + float(rng.uniform(-0.3, 0.3)) / 100), 2),
        "high":     round(close * (1 + abs(float(rng.uniform(0, 0.5))) / 100), 2),
        "low":      round(close * (1 - abs(float(rng.uniform(0, 0.5))) / 100), 2),
    }


def _yf_quote(symbol: str) -> dict | None:
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        hist = t.history(period="2d")
        if len(hist) < 2:
            return None
        close = float(hist["Close"].iloc[-1])
        prev  = float(hist["Close"].iloc[-2])
        chg   = close - prev
        return {
            "close":   round(close, 2),
            "prev":    round(prev, 2),
            "change":  round(chg, 2),
            "chg_pct": round(chg / prev * 100, 2),
            "open":    round(float(hist["Open"].iloc[-1]), 2),
            "high":    round(float(hist["High"].iloc[-1]), 2),
            "low":     round(float(hist["Low"].iloc[-1]), 2),
        }
    except Exception as e:
        logger.debug("yf_quote failed %s: %s", symbol, e)
        return None


def fetch_quote(symbol: str) -> dict:
    q = _yf_quote(symbol)
    return q or _dummy_quote(symbol)


def fetch_global_indices() -> dict:
    out: dict[str, dict] = {}
    for sym, meta in GLOBAL_INDICES.items():
        q = fetch_quote(sym)
        out[sym] = {**meta, **q, "symbol": sym}
    return out


def fetch_commodities() -> dict:
    out: dict[str, dict] = {}
    for sym, meta in COMMODITIES.items():
        q = fetch_quote(sym)
        out[sym] = {**meta, **q, "symbol": sym}
    return out


def fetch_sectors() -> list[dict]:
    sectors = []
    for sym, name in NIFTY_SECTORS.items():
        q = fetch_quote(sym)
        sectors.append({"symbol": sym, "name": name, **q})
    sectors.sort(key=lambda x: -x["chg_pct"])
    return sectors


def fetch_nifty_ema_data() -> dict:
    """Fetch Nifty 50 close prices for EMA calculation."""
    try:
        import yfinance as yf, pandas as pd
        hist = yf.Ticker("^NSEI").history(period="250d")
        if hist.empty:
            raise ValueError("empty")
        close = hist["Close"]
        return {
            "dates":  [str(d.date()) for d in close.index[-60:]],
            "close":  close.round(2).tolist()[-60:],
            "ema10":  close.ewm(span=10, adjust=False).mean().round(2).tolist()[-60:],
            "ema20":  close.ewm(span=20, adjust=False).mean().round(2).tolist()[-60:],
            "ema50":  close.ewm(span=50, adjust=False).mean().round(2).tolist()[-60:],
            "ema200": close.ewm(span=200, adjust=False).mean().round(2).tolist()[-60:],
            "volume": hist["Volume"].tolist()[-60:],
        }
    except Exception:
        # Dummy GBM Nifty
        from backend.data_engine.dummy_data import generate_ohlcv
        df = generate_ohlcv("^NSEI", 250)
        close = df["Close"]
        return {
            "dates":  [str(d.date()) for d in close.index[-60:]],
            "close":  close.round(2).tolist()[-60:],
            "ema10":  close.ewm(span=10, adjust=False).mean().round(2).tolist()[-60:],
            "ema20":  close.ewm(span=20, adjust=False).mean().round(2).tolist()[-60:],
            "ema50":  close.ewm(span=50, adjust=False).mean().round(2).tolist()[-60:],
            "ema200": close.ewm(span=200, adjust=False).mean().round(2).tolist()[-60:],
            "volume": df["Volume"].tolist()[-60:],
        }
