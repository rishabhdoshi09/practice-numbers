"""
Live market data via Zerodha Kite Connect.
Provides OHLCV history, real-time quotes, and WebSocket tick streaming.

Instrument tokens are loaded dynamically from kite.instruments("NSE") on
first use and cached to disk (refreshed daily).  This gives access to ALL
~2000 NSE-listed equities, not just a hard-coded subset.
"""
from __future__ import annotations
import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", ".kite_instruments.json")
_CACHE_FILE = os.path.normpath(_CACHE_FILE)

# In-memory token map: "RELIANCE.NS" → 738561
_token_map:  dict[str, int] = {}
# In-memory meta map: "RELIANCE.NS" → {"name": ..., "lot_size": ..., "tick_size": ...}
_meta_map:   dict[str, dict] = {}
_map_lock = threading.Lock()


def _kite_symbol(symbol: str) -> str:
    return symbol.replace(".NS", "").replace(".BSE", "")


def _cache_fresh() -> bool:
    """Return True if the cache file exists and is from today."""
    if not os.path.exists(_CACHE_FILE):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(_CACHE_FILE))
    return mtime.date() == datetime.today().date()


def load_instruments(kite, force: bool = False) -> dict[str, int]:
    """
    Build the full NSE equity token map from Kite's instrument master.

    Results are cached to .kite_instruments.json and refreshed once per day.
    Returns mapping: "SYMBOL.NS" → instrument_token (int)
    """
    global _token_map, _meta_map

    with _map_lock:
        if _token_map and not force:
            return _token_map

        # Try disk cache first
        if _cache_fresh() and not force:
            try:
                with open(_CACHE_FILE) as f:
                    cached = json.load(f)
                _token_map = {k: v["token"] for k, v in cached.items()}
                _meta_map  = cached
                logger.info("Loaded %d instruments from cache", len(_token_map))
                return _token_map
            except Exception as e:
                logger.warning("Cache read failed: %s — refetching", e)

        # Fetch from Kite API
        try:
            instruments = kite.instruments("NSE")
            logger.info("Fetched %d raw NSE instruments from Kite", len(instruments))
        except Exception as e:
            logger.error("kite.instruments() failed: %s", e)
            return _token_map  # return whatever we have

        new_tokens: dict[str, int]  = {}
        new_meta:   dict[str, dict] = {}

        for inst in instruments:
            if inst.get("instrument_type") != "EQ":
                continue
            ts     = inst.get("tradingsymbol", "")
            token  = inst.get("instrument_token")
            name   = inst.get("name", ts)
            if not ts or not token:
                continue
            sym = f"{ts}.NS"
            new_tokens[sym] = token
            new_meta[sym] = {
                "token":     token,
                "name":      name,
                "lot_size":  inst.get("lot_size", 1),
                "tick_size": inst.get("tick_size", 0.05),
            }

        _token_map = new_tokens
        _meta_map  = new_meta

        # Persist to disk
        try:
            with open(_CACHE_FILE, "w") as f:
                json.dump(new_meta, f)
            logger.info("Cached %d NSE EQ instruments to disk", len(new_tokens))
        except Exception as e:
            logger.warning("Cache write failed: %s", e)

        return _token_map


def get_all_equity_symbols() -> list[str]:
    """Return all NSE equity symbols we know about (from in-memory map)."""
    return sorted(_token_map.keys())


def get_instrument_token(symbol: str) -> Optional[int]:
    return _token_map.get(symbol)


def get_instrument_meta(symbol: str) -> dict:
    return _meta_map.get(symbol, {})


class KiteDataProvider:
    """Wraps Kite REST + WebSocket for live market data."""

    def __init__(self, kite):
        self._kite = kite
        self._tick_callbacks: list[Callable] = []
        self._latest_ticks: dict[str, dict] = {}
        self._ws = None
        # Load full instrument map in background so startup is non-blocking
        threading.Thread(target=load_instruments, args=(kite,), daemon=True).start()

    # ── REST: Historical OHLCV ─────────────────────────────────────────────────

    def get_ohlcv(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """Fetch historical OHLCV from Kite (day candles)."""
        token = get_instrument_token(symbol)
        if not token:
            # Instruments may not be loaded yet — try a blocking load
            load_instruments(self._kite)
            token = get_instrument_token(symbol)
        if not token:
            raise ValueError(f"Instrument token not found for {symbol}")

        to_date   = datetime.now()
        from_date = to_date - timedelta(days=days)

        records = self._kite.historical_data(
            instrument_token=token,
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
            interval="day",
            continuous=False,
        )

        df = pd.DataFrame(records)
        df.rename(columns={
            "date":   "Date",
            "open":   "Open",
            "high":   "High",
            "low":    "Low",
            "close":  "Close",
            "volume": "Volume",
        }, inplace=True)
        df.set_index("Date", inplace=True)
        df.index = pd.to_datetime(df.index)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()

    # ── REST: Live quote ───────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict:
        """Fetch real-time quote snapshot via REST."""
        nse_symbol = f"NSE:{_kite_symbol(symbol)}"
        try:
            quotes = self._kite.quote([nse_symbol])
            q = quotes[nse_symbol]
            return {
                "symbol":        symbol,
                "last_price":    q["last_price"],
                "open":          q["ohlc"]["open"],
                "high":          q["ohlc"]["high"],
                "low":           q["ohlc"]["low"],
                "close":         q["ohlc"]["close"],
                "volume":        q["volume"],
                "bid":           q["depth"]["buy"][0]["price"] if q["depth"]["buy"] else None,
                "ask":           q["depth"]["sell"][0]["price"] if q["depth"]["sell"] else None,
                "change_pct":    q["net_change"],
                "timestamp":     str(q.get("timestamp", datetime.now())),
            }
        except Exception as e:
            logger.error("Quote fetch failed for %s: %s", symbol, e)
            raise

    # ── WebSocket: Real-time tick streaming ────────────────────────────────────

    def start_ticker(self, symbols: list[str], on_tick: Callable):
        """
        Start a WebSocket connection for real-time tick data.

        on_tick(symbol, price) is called on every tick.
        Runs in a background daemon thread.
        """
        from kiteconnect import KiteTicker

        tokens = [_token_map[s] for s in symbols if s in _token_map]
        if not tokens:
            logger.warning("No valid instrument tokens for WebSocket")
            return

        token_to_symbol = {v: k for k, v in _token_map.items()}

        ticker = KiteTicker(
            api_key=self._kite.api_key,
            access_token=self._kite.access_token,
        )

        def _on_ticks(ws, ticks):
            for tick in ticks:
                sym = token_to_symbol.get(tick["instrument_token"])
                if sym:
                    price = tick.get("last_price", 0)
                    self._latest_ticks[sym] = tick
                    on_tick(sym, price)

        def _on_connect(ws, response):
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_FULL, tokens)
            logger.info("Kite WebSocket connected — streaming %d symbols", len(tokens))

        def _on_error(ws, code, reason):
            logger.error("WebSocket error %s: %s", code, reason)

        def _on_close(ws, code, reason):
            logger.warning("WebSocket closed: %s %s", code, reason)

        ticker.on_ticks   = _on_ticks
        ticker.on_connect = _on_connect
        ticker.on_error   = _on_error
        ticker.on_close   = _on_close

        self._ws = ticker
        # Run in daemon thread so it doesn't block the FastAPI server
        t = threading.Thread(target=ticker.connect, kwargs={"threaded": True}, daemon=True)
        t.start()
        logger.info("Kite ticker thread started")

    def get_latest_tick(self, symbol: str) -> Optional[dict]:
        return self._latest_ticks.get(symbol)

    def stop_ticker(self):
        if self._ws:
            self._ws.close()

    # ── Order placement ────────────────────────────────────────────────────────

    def place_order(self, symbol: str, side: str, qty: int,
                    order_type: str = "MARKET",
                    price: float = 0.0) -> dict:
        """
        Place a real order via Kite.

        Args:
            symbol: NSE ticker e.g. 'RELIANCE.NS'
            side: 'BUY' or 'SELL'
            qty: number of shares
            order_type: 'MARKET' | 'LIMIT' | 'SL-M'
            price: limit price (only for LIMIT/SL orders)
        """
        if qty <= 0:
            raise ValueError(f"Invalid order quantity: {qty}")

        tradingsymbol = _kite_symbol(symbol)
        transaction   = self._kite.TRANSACTION_TYPE_BUY if side == "BUY" \
                        else self._kite.TRANSACTION_TYPE_SELL

        order_id = self._kite.place_order(
            variety=self._kite.VARIETY_REGULAR,
            exchange=self._kite.EXCHANGE_NSE,
            tradingsymbol=tradingsymbol,
            transaction_type=transaction,
            quantity=qty,
            product=self._kite.PRODUCT_CNC,        # Cash & Carry (delivery)
            order_type=self._kite.ORDER_TYPE_MARKET if order_type == "MARKET"
                       else self._kite.ORDER_TYPE_LIMIT,
            price=price if order_type == "LIMIT" else None,
            tag="simplequant",
        )
        logger.info("Real order placed: %s %s %d — order_id=%s", side, symbol, qty, order_id)
        return {"order_id": order_id, "symbol": symbol, "side": side, "qty": qty, "status": "placed"}
