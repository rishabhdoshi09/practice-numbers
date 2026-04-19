"""
DataEngine: unified market data layer.

When Kite is authenticated → ALL price data comes from Kite (live, real-time).
When not authenticated     → yFinance fallback (delayed, limited).

yFinance is kept ONLY for fundamentals / news (Kite doesn't provide these).
"""
import logging
import time
from typing import Optional
import pandas as pd

from backend.config import HISTORY_DAYS, INTRADAY_INTERVAL, DATA_CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)


class DataEngine:

    def __init__(self, use_live: bool = True):
        self._use_live       = use_live
        self._cache: dict[str, tuple[float, pd.DataFrame]] = {}
        self._kite_provider  = None

    def set_kite(self, kite_provider):
        self._kite_provider = kite_provider
        logger.info("Kite live data provider activated")

    # ── OHLCV ──────────────────────────────────────────────────────────────────

    def get_ohlcv(self, symbol: str, days: int = HISTORY_DAYS) -> pd.DataFrame:
        cache_key = f"{symbol}:{days}"
        cached = self._cache.get(cache_key)
        if cached:
            ts, df = cached
            if time.time() - ts < DATA_CACHE_TTL_SECONDS:
                return df
            del self._cache[cache_key]

        df = None

        if self._kite_provider:
            # Kite is live — use it exclusively, no yFinance fallback
            try:
                df = self._kite_provider.get_ohlcv(symbol, days)
                if df is not None and not df.empty:
                    logger.debug("Kite OHLCV: %s (%d rows)", symbol, len(df))
            except Exception as e:
                logger.error("Kite OHLCV failed for %s: %s", symbol, e)
                raise ValueError(
                    f"Could not fetch data for {symbol} from Kite: {e}. "
                    "Make sure this symbol exists on NSE/BSE."
                )
        else:
            # Not authenticated — yFinance fallback
            if self._use_live:
                df = self._fetch_yfinance(symbol, days)

        if df is None or df.empty:
            raise ValueError(
                f"No market data for {symbol}. "
                + ("Authenticate Kite at /kite/login" if not self._kite_provider
                   else "Symbol may be delisted or misspelled.")
            )

        df.columns = [c.capitalize() for c in df.columns]
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        self._cache[cache_key] = (time.time(), df)
        return df

    # ── Quote ──────────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict:
        if self._kite_provider:
            try:
                return self._kite_provider.get_quote(symbol)
            except Exception as e:
                logger.error("Kite quote failed for %s: %s", symbol, e)
                raise ValueError(f"Could not fetch quote for {symbol}: {e}")
        # Fallback when unauthenticated
        price = self._yfinance_price(symbol)
        return {"symbol": symbol, "last_price": price, "source": "yfinance"}

    # ── Order book ─────────────────────────────────────────────────────────────

    def get_order_book(self, symbol: str) -> dict:
        if self._kite_provider:
            try:
                from backend.data_engine.kite_provider import _kite_symbol
                exchange = "BSE" if symbol.endswith(".BO") else "NSE"
                kite_sym = f"{exchange}:{_kite_symbol(symbol)}"
                quotes = self._kite_provider._kite.quote([kite_sym])
                depth  = quotes[kite_sym]["depth"]
                return {
                    "bids":   [{"price": b["price"], "qty": b["quantity"]} for b in depth["buy"]],
                    "asks":   [{"price": a["price"], "qty": a["quantity"]} for a in depth["sell"]],
                    "source": "kite_live",
                }
            except Exception as e:
                logger.warning("Kite depth failed for %s: %s", symbol, e)
        return {"bids": [], "asks": [], "source": "unavailable"}

    # ── News ───────────────────────────────────────────────────────────────────

    def get_news(self, symbol: str) -> list[dict]:
        """News via yFinance (Kite doesn't provide news)."""
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

    # ── Current price ──────────────────────────────────────────────────────────

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

    # ── Cache helpers ──────────────────────────────────────────────────────────

    def clear_cache(self):
        self._cache.clear()

    def cache_stats(self) -> dict:
        now = time.time()
        return {
            "entries": len(self._cache),
            "live":    sum(1 for ts, _ in self._cache.values() if now - ts < DATA_CACHE_TTL_SECONDS),
            "expired": sum(1 for ts, _ in self._cache.values() if now - ts >= DATA_CACHE_TTL_SECONDS),
        }

    # ── Private ────────────────────────────────────────────────────────────────

    def _fetch_yfinance(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf
            df = yf.Ticker(symbol).history(
                period=f"{days}d", interval=INTRADAY_INTERVAL, auto_adjust=True
            )
            return df if not df.empty else None
        except Exception as exc:
            logger.warning("yFinance fetch failed for %s: %s", symbol, exc)
            return None

    def _yfinance_price(self, symbol: str) -> float:
        try:
            import yfinance as yf
            info = yf.Ticker(symbol).fast_info
            return float(getattr(info, "last_price", 0) or 0)
        except Exception:
            return 0.0
