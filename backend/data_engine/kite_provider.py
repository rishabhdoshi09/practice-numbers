"""
Live market data via Zerodha Kite Connect.
Provides OHLCV history, real-time quotes, and WebSocket tick streaming.
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# NSE symbol → Kite instrument token mapping (top 15 stocks)
# Tokens fetched once and cached; full list at kite.instruments("NSE")
INSTRUMENT_TOKENS: dict[str, int] = {
    "RELIANCE.NS":   738561,
    "TCS.NS":        2953217,
    "INFY.NS":       408065,
    "HDFCBANK.NS":   341249,
    "ICICIBANK.NS":  1270529,
    "HINDUNILVR.NS": 356865,
    "BAJFINANCE.NS": 4268801,
    "WIPRO.NS":      3787777,
    "SBIN.NS":       779521,
    "TATAMOTORS.NS": 884737,
    "ADANIPORTS.NS": 3861249,
    "ASIANPAINT.NS": 60417,
    "AXISBANK.NS":   1510401,
    "BHARTIARTL.NS": 2714625,
    "ITC.NS":        424961,
}

# NSE symbol → Kite tradingsymbol (without .NS)
def _kite_symbol(symbol: str) -> str:
    return symbol.replace(".NS", "").replace(".BSE", "")


class KiteDataProvider:
    """Wraps Kite REST + WebSocket for live market data."""

    def __init__(self, kite):
        self._kite = kite
        self._tick_callbacks: list[Callable] = []
        self._latest_ticks: dict[str, dict] = {}
        self._ws = None

    # ── REST: Historical OHLCV ─────────────────────────────────────────────────

    def get_ohlcv(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """Fetch historical OHLCV from Kite (day candles)."""
        token = INSTRUMENT_TOKENS.get(symbol)
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

        tokens = [INSTRUMENT_TOKENS[s] for s in symbols if s in INSTRUMENT_TOKENS]
        if not tokens:
            logger.warning("No valid instrument tokens for WebSocket")
            return

        token_to_symbol = {v: k for k, v in INSTRUMENT_TOKENS.items()}

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
        from kiteconnect import KiteConnect

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
