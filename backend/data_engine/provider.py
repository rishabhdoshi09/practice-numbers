"""
DataEngine: fetch live market data with a graceful fallback chain.

Priority:  Kite Connect (live, real-time)  →  yFinance (live, 15-min delay)
No synthetic/dummy data is used in production.
"""
import logging
from typing import Optional
import pandas as pd

from backend.config import HISTORY_DAYS, INTRADAY_INTERVAL

logger = logging.getLogger(__name__)


class DataEngine:
    """Provides OHLCV, order-book, and news data — Kite-first, then yFinance."""

    def __init__(self, use_live: bool = True):
        self._use_live   = use_live
        self._cache: dict[str, pd.DataFrame] = {}
        self._kite_provider = None

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

        # 2. yFinance (15-min delayed, real data)
        if df is None or df.empty:
            if self._use_live:
                df = self._fetch_yfinance(symbol, days)

        if df is None or df.empty:
            raise ValueError(
                f"No market data available for {symbol}. "
                "Check internet connection or Kite authentication."
            )

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
        price = self.get_current_price(symbol)
        return {"symbol": symbol, "last_price": price}

    def get_order_book(self, symbol: str) -> dict:
        """Live order book — Kite depth first, yFinance bid/ask fallback."""
        # Kite 5-level market depth
        if self._kite_provider:
            try:
                from backend.data_engine.kite_provider import _kite_symbol
                nse_sym = f"NSE:{_kite_symbol(symbol)}"
                quotes = self._kite_provider._kite.quote([nse_sym])
                depth  = quotes[nse_sym]["depth"]
                return {
                    "bids":   [{"price": b["price"], "qty": b["quantity"]} for b in depth["buy"]],
                    "asks":   [{"price": a["price"], "qty": a["quantity"]} for a in depth["sell"]],
                    "source": "kite_live",
                }
            except Exception as e:
                logger.warning("Kite depth failed for %s: %s", symbol, e)

        # yFinance single-level bid/ask
        try:
            import yfinance as yf
            info     = yf.Ticker(symbol).info
            bid      = info.get("bid", 0)
            ask      = info.get("ask", 0)
            bid_size = info.get("bidSize", 0)
            ask_size = info.get("askSize", 0)
            if bid and ask:
                return {
                    "bids":   [{"price": bid, "qty": bid_size}],
                    "asks":   [{"price": ask, "qty": ask_size}],
                    "source": "yfinance",
                }
        except Exception as e:
            logger.warning("yFinance order book failed for %s: %s", symbol, e)

        return {"bids": [], "asks": [], "source": "unavailable"}

    def get_news(self, symbol: str) -> list[dict]:
        """Fetch real news headlines from yFinance."""
        try:
            import yfinance as yf
            news_raw = yf.Ticker(symbol).news or []
            result = []
            for item in news_raw[:8]:
                title = item.get("title", "")
                if title:
                    result.append({
                        "headline":  title,
                        "source":    item.get("publisher", ""),
                        "url":       item.get("link", ""),
                        "published": item.get("providerPublishTime", 0),
                    })
            return result
        except Exception as e:
            logger.warning("News fetch failed for %s: %s", symbol, e)
            return []

    def get_current_price(self, symbol: str) -> float:
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
