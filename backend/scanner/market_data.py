"""
Global market data fetcher.
Fetches indices, commodities, and sectoral data via yFinance.
No dummy/hardcoded fallback data — real data only.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# ── Symbol maps ────────────────────────────────────────────────────────────────

GLOBAL_INDICES = {
    # India
    "^NSEI":    {"name": "Nifty 50",      "region": "India",         "flag": "🇮🇳"},
    "^NSEBANK": {"name": "Bank Nifty",    "region": "India",         "flag": "🇮🇳"},
    "^BSESN":   {"name": "Sensex",        "region": "India",         "flag": "🇮🇳"},
    # US
    "^GSPC":    {"name": "S&P 500",       "region": "North America", "flag": "🇺🇸"},
    "^DJI":     {"name": "Dow Jones",     "region": "North America", "flag": "🇺🇸"},
    "^IXIC":    {"name": "Nasdaq",        "region": "North America", "flag": "🇺🇸"},
    "^VIX":     {"name": "VIX",           "region": "North America", "flag": "🇺🇸"},
    # Europe
    "^FTSE":    {"name": "FTSE 100",      "region": "Europe",        "flag": "🇬🇧"},
    "^GDAXI":   {"name": "DAX",           "region": "Europe",        "flag": "🇩🇪"},
    "^FCHI":    {"name": "CAC 40",        "region": "Europe",        "flag": "🇫🇷"},
    # Asia
    "^N225":    {"name": "Nikkei 225",    "region": "Asia",          "flag": "🇯🇵"},
    "^HSI":     {"name": "Hang Seng",     "region": "Asia",          "flag": "🇭🇰"},
    "000001.SS":{"name": "Shanghai Comp", "region": "Asia",          "flag": "🇨🇳"},
    # EM
    "^BVSP":    {"name": "Bovespa",       "region": "South America", "flag": "🇧🇷"},
}

COMMODITIES = {
    "GC=F":     {"name": "Gold",      "unit": "USD/oz"},
    "SI=F":     {"name": "Silver",    "unit": "USD/oz"},
    "CL=F":     {"name": "Crude Oil", "unit": "USD/bbl"},
    "BZ=F":     {"name": "Brent",     "unit": "USD/bbl"},
    "DX-Y.NYB": {"name": "USD Index", "unit": "pts"},
}

NIFTY_SECTORS = {
    "^CNXAUTO":   "Auto",
    "^CNXBANK":   "Banking",
    "^CNXIT":     "IT",
    "^CNXPHARMA": "Pharma",
    "^CNXFMCG":   "FMCG",
    "^CNXMETAL":  "Metals",
    "^CNXREALTY": "Realty",
    "^CNXENERGY": "Energy",
    "^CNXINFRA":  "Infra",
    "^CNXMEDIA":  "Media",
}


def _yf_quote(symbol: str) -> dict | None:
    try:
        import yfinance as yf
        t    = yf.Ticker(symbol)
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
            "chg_pct": round(chg / prev * 100, 2) if prev else 0,
            "open":    round(float(hist["Open"].iloc[-1]), 2),
            "high":    round(float(hist["High"].iloc[-1]), 2),
            "low":     round(float(hist["Low"].iloc[-1]), 2),
        }
    except Exception as e:
        logger.debug("yf_quote failed %s: %s", symbol, e)
        return None


def fetch_quote(symbol: str) -> dict | None:
    """Returns real yFinance quote or None if unavailable."""
    return _yf_quote(symbol)


def fetch_global_indices() -> dict:
    out: dict[str, dict] = {}
    for sym, meta in GLOBAL_INDICES.items():
        q = fetch_quote(sym)
        if q:
            out[sym] = {**meta, **q, "symbol": sym}
        else:
            logger.debug("Skipping %s — no data", sym)
    return out


def fetch_commodities() -> dict:
    out: dict[str, dict] = {}
    for sym, meta in COMMODITIES.items():
        q = fetch_quote(sym)
        if q:
            out[sym] = {**meta, **q, "symbol": sym}
        else:
            logger.debug("Skipping commodity %s — no data", sym)
    return out


def fetch_sectors() -> list[dict]:
    sectors = []
    for sym, name in NIFTY_SECTORS.items():
        q = fetch_quote(sym)
        if q:
            sectors.append({"symbol": sym, "name": name, **q})
        else:
            logger.debug("Skipping sector %s — no data", sym)
    sectors.sort(key=lambda x: -x["chg_pct"])
    return sectors


def fetch_nifty_ema_data() -> dict:
    """Fetch Nifty 50 close prices for EMA calculation — yFinance only."""
    import yfinance as yf
    hist = yf.Ticker("^NSEI").history(period="250d")
    if hist.empty:
        raise ValueError("No Nifty 50 data from yFinance — check internet connection")
    close = hist["Close"]
    return {
        "dates":  [str(d.date()) for d in close.index[-60:]],
        "close":  close.round(2).tolist()[-60:],
        "ema10":  close.ewm(span=10,  adjust=False).mean().round(2).tolist()[-60:],
        "ema20":  close.ewm(span=20,  adjust=False).mean().round(2).tolist()[-60:],
        "ema50":  close.ewm(span=50,  adjust=False).mean().round(2).tolist()[-60:],
        "ema200": close.ewm(span=200, adjust=False).mean().round(2).tolist()[-60:],
        "volume": hist["Volume"].tolist()[-60:],
    }
