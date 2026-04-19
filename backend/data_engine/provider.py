"""
DataEngine: fetch live market data with a graceful fallback to dummy data.

Priority chain:  yFinance (live)  →  dummy GBM simulation
All callers receive the same standardised DataFrame regardless of source.
"""
import logging
from typing import Optional
import pandas as pd

from backend.config import HISTORY_DAYS, INTRADAY_INTERVAL
from .dummy_data import generate_ohlcv, generate_order_book, generate_news

logger = logging.getLogger(__name__)


class DataEngine:
    """Provides OHLCV, order-book, and news data for a given symbol."""

    def __init__(self, use_live: bool = True):
        self._use_live = use_live
        self._cache: dict[str, pd.DataFrame] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_ohlcv(self, symbol: str, days: int = HISTORY_DAYS) -> pd.DataFrame:
        """Return OHLCV DataFrame indexed by trading date."""
        cache_key = f"{symbol}:{days}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        df = self._fetch_live(symbol, days) if self._use_live else None
        if df is None or df.empty:
            logger.info("Falling back to dummy data for %s", symbol)
            df = generate_ohlcv(symbol, days)

        # Normalise column names
        df.columns = [c.capitalize() for c in df.columns]
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        self._cache[cache_key] = df
        return df

    def get_order_book(self, symbol: str) -> dict:
        """Return simulated order book (live integration omitted for Phase 1)."""
        df = self.get_ohlcv(symbol, days=5)
        mid = float(df["Close"].iloc[-1])
        return generate_order_book(symbol, mid)

    def get_news(self, symbol: str) -> list[dict]:
        return generate_news(symbol)

    def get_current_price(self, symbol: str) -> float:
        df = self.get_ohlcv(symbol, days=5)
        return float(df["Close"].iloc[-1])

    # ── Private ───────────────────────────────────────────────────────────────

    def _fetch_live(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf  # optional dependency
            period = f"{days}d"
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=INTRADAY_INTERVAL, auto_adjust=True)
            if df.empty:
                return None
            return df
        except Exception as exc:
            logger.warning("yFinance fetch failed for %s: %s", symbol, exc)
            return None
