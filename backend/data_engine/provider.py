"""
DataEngine: fetch live market data with a graceful fallback chain.

Priority:  Kite Connect (live, real-time)  →  yFinance (live, 15-min delay)  →  GBM dummy
"""
import logging
from typing import Optional
import pandas as pd

from backend.config import HISTORY_DAYS, INTRADAY_INTERVAL
from .dummy_data import generate_ohlcv, generate_order_book, generate_news

logger = logging.getLogger(__name__)


class DataEngine:
    """Provides OHLCV, order-book, and news data — Kite-first, then yFinance, then dummy."""

    def __init__(self, use_live: bool = True):
        self._use_live   = use_live
        self._cache: dict[str, pd.DataFrame] = {}
        self._kite_provider = None   # set after auth via set_kite()

    def set_kite(self, kite_provider):
        """Inject live Kite provider after authentication."""
        self._kite_provider = kite_provider
        logger.info("Kite live data provider activated")

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_ohlcv(self, symbol: str, days: int = HISTORY_DAYS) -> pd.DataFrame:
        cache_key = f"{symbol}:{days}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        df = None

        # 1. Try Kite (real-time, most reliable)
        if self._kite_provider:
            try:
                df = self._kite_provider.get_ohlcv(symbol, days)
                logger.info("Kite data fetched for %s (%d rows)", symbol, len(df))
            except Exception as e:
                logger.warning("Kite OHLCV failed for %s: %s", symbol, e)

        # 2. Try yFinance (15-min delayed)
        if df is None or df.empty:
            if self._use_live:
                df = self._fetch_yfinance(symbol, days)

        # 3. Fallback: GBM dummy data
        if df is None or df.empty:
            logger.info("Falling back to dummy data for %s", symbol)
            df = generate_ohlcv(symbol, days)

        df.columns = [c.capitalize() for c in df.columns]
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        self._cache[cache_key] = df
        return df

    def get_quote(self, symbol: str) -> dict:
        """Real-time quote — Kite first, yFinance fallback."""
        if self._kite_provider:
            try:
                return self._kite_provider.get_quote(symbol)
            except Exception as e:
                logger.warning("Kite quote failed: %s", e)
        # yFinance fallback
        price = self.get_current_price(symbol)
        return {"symbol": symbol, "last_price": price}

    def get_order_book(self, symbol: str) -> dict:
        df  = self.get_ohlcv(symbol, days=5)
        mid = float(df["Close"].iloc[-1])
        return generate_order_book(symbol, mid)

    def get_news(self, symbol: str) -> list[dict]:
        return generate_news(symbol)

    def get_current_price(self, symbol: str) -> float:
        # Real-time from Kite tick if available
        if self._kite_provider:
            tick = self._kite_provider.get_latest_tick(symbol)
            if tick:
                return float(tick.get("last_price", 0))
            try:
                quote = self._kite_provider.get_quote(symbol)
                return float(quote["last_price"])
            except Exception:
                pass
        df = self.get_ohlcv(symbol, days=5)
        return float(df["Close"].iloc[-1])

    def clear_cache(self):
        self._cache.clear()

    # ── Private ────────────────────────────────────────────────────────────────

    def _fetch_yfinance(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{days}d", interval=INTRADAY_INTERVAL, auto_adjust=True)
            return df if not df.empty else None
        except Exception as exc:
            logger.warning("yFinance fetch failed for %s: %s", symbol, exc)
            return None
