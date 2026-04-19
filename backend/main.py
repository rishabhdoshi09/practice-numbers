"""
SimpleQuant FastAPI backend v3 — JARVIS Edition.
Five engines + Kite live data + scheduled market scanning + WebSocket push.
"""
from __future__ import annotations
import json
import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from backend.config import DEFAULT_SYMBOLS, DEFAULT_SYMBOL, DEFAULT_PORTFOLIO_VALUE
from backend.data_engine import DataEngine
from backend.feature_engine import FeatureEngine
from backend.decision_engine import DecisionEngine
from backend.risk_engine import RiskEngine
from backend.execution_engine import ExecutionEngine
from backend.scanner import ScanEngine
from backend import kite_auth

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── WebSocket connection manager ───────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections for scan result broadcasting."""
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info("WS client connected (total: %d)", len(self.active))

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
        logger.info("WS client disconnected (total: %d)", len(self.active))

    async def broadcast(self, data: dict):
        payload = json.dumps(data)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


ws_manager = ConnectionManager()

# ── Engine singletons ──────────────────────────────────────────────────────────
data_engine      = DataEngine(use_live=True)
feature_engine   = FeatureEngine()
decision_engine  = DecisionEngine()
risk_engine      = RiskEngine()
execution_engine = ExecutionEngine(starting_capital=DEFAULT_PORTFOLIO_VALUE)
scan_engine      = ScanEngine(data_engine)

# ── App lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Activate Kite if token saved
    _wire_kite()

    # Start JARVIS scheduler
    from backend.scanner.scheduler import init_scheduler
    scheduler = init_scheduler(scan_engine, ws_broadcast=ws_manager.broadcast)
    logger.info("JARVIS scheduler active — waiting for market open (9:15 IST)")

    yield  # app is running

    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(
    title="SimpleQuant JARVIS API",
    description="Quant trading — Kite live data + JARVIS auto-scan + WebSocket alerts",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _wire_kite():
    """Activate Kite provider from saved access token."""
    kite = kite_auth.get_kite()
    if kite:
        from backend.data_engine.kite_provider import KiteDataProvider
        provider = KiteDataProvider(kite)
        data_engine.set_kite(provider)
        logger.info("Kite live data active (saved token)")


def _analyse(symbol: str) -> dict:
    df    = data_engine.get_ohlcv(symbol)
    news  = data_engine.get_news(symbol)
    price = data_engine.get_current_price(symbol)

    features = feature_engine.compute(df, news)
    decision = decision_engine.decide(features["signals"], features)
    risk     = risk_engine.compute(
        df, current_price=price, atr=features["atr"],
        portfolio_value=execution_engine.cash,
    )
    return {
        "symbol":      symbol,
        "price":       round(price, 2),
        "data_source": "kite_live" if kite_auth.is_authenticated() else "dummy/yfinance",
        "features":    features,
        "decision":    decision,
        "risk":        risk,
        "news":        news,
    }


# ── Models ─────────────────────────────────────────────────────────────────────

class OrderRequest(BaseModel):
    symbol: str
    side: str
    qty: int = 1
    order_type: str = "MARKET"
    price: float = 0.0
    use_real: bool = False


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws/scan")
async def ws_scan(websocket: WebSocket):
    """
    Real-time scan results pushed to frontend.
    Connect once — receive every scan update automatically.
    Also accepts 'ping' messages for keepalive.
    """
    await ws_manager.connect(websocket)
    # Send last cached result immediately on connect
    last = scan_engine.last_result()
    if last:
        await websocket.send_text(json.dumps({"type": "scan_result", **last}))
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── Health & status ────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def health():
    return {
        "status": "ok",
        "version": "3.0.0 JARVIS",
        "kite_authenticated": kite_auth.is_authenticated(),
        "data_source": "kite_live" if kite_auth.is_authenticated() else "yfinance/dummy",
        "ws_clients": len(ws_manager.active),
    }


# ── Kite auth ──────────────────────────────────────────────────────────────────

@app.get("/kite/login", tags=["auth"])
def kite_login():
    """Open in browser once per day to authenticate with Zerodha."""
    return RedirectResponse(url=kite_auth.get_login_url())


@app.get("/kite/callback", tags=["auth"])
async def kite_callback(request_token: str):
    try:
        kite_auth.exchange_token(request_token)
        _wire_kite()
        data_engine.clear_cache()
        kite = kite_auth.get_kite()
        from backend.data_engine.kite_provider import KiteDataProvider
        provider = KiteDataProvider(kite)
        provider.start_ticker(DEFAULT_SYMBOLS[:15],
                              on_tick=lambda s, p: logger.debug("Tick %s %.2f", s, p))
        return {"status": "authenticated", "message": "Kite live data + WebSocket ticker active"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/kite/status", tags=["auth"])
def kite_status():
    return {
        "authenticated": kite_auth.is_authenticated(),
        "data_source": "kite_live" if kite_auth.is_authenticated() else "yfinance/dummy",
        "login_url": "http://localhost:8000/kite/login",
    }


# ── JARVIS scan ────────────────────────────────────────────────────────────────

@app.get("/scan", tags=["jarvis"])
async def run_scan(
    universe: str = Query(default="nifty50", description="nifty50 | custom"),
    symbols: str  = Query(default="", description="Comma-separated override"),
):
    """
    Trigger an on-demand full market scan.
    Results are also pushed to all connected WebSocket clients.
    """
    from backend.scanner.universe import NIFTY50_SYMBOLS
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] or NIFTY50_SYMBOLS

    progress_log: list[str] = []

    def on_progress(done, total, sym):
        progress_log.append(f"{done}/{total} {sym}")

    try:
        result = scan_engine.run(sym_list, on_progress=on_progress)
        await ws_manager.broadcast({"type": "scan_result", **result})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/last", tags=["jarvis"])
def get_last_scan():
    """Return the most recent cached scan result without re-running."""
    result = scan_engine.last_result()
    if not result:
        raise HTTPException(status_code=404, detail="No scan run yet. Call /scan first.")
    return result


@app.get("/scan/schedule", tags=["jarvis"])
def get_schedule():
    """Show JARVIS schedule for today."""
    import pytz
    from datetime import datetime
    IST = pytz.timezone("Asia/Kolkata")
    now = datetime.now(IST)
    return {
        "current_time_ist": now.strftime("%H:%M:%S IST"),
        "scheduled_jobs": [
            {"time": "09:15 IST", "label": "Market Open Scan",  "id": "market_open"},
            {"time": "11:00 IST", "label": "Mid-Morning Rescan", "id": "midmorning"},
            {"time": "13:00 IST", "label": "Midday Pulse",       "id": "midday"},
            {"time": "15:20 IST", "label": "Pre-Close Scan",     "id": "preclose"},
            {"time": "15:30 IST", "label": "End-of-Day Summary", "id": "eod_summary"},
        ],
    }


# ── Market data ────────────────────────────────────────────────────────────────

@app.get("/symbols", tags=["market"])
def list_symbols():
    return {"symbols": DEFAULT_SYMBOLS}


@app.get("/quote", tags=["market"])
def get_quote(symbol: str = Query(default=DEFAULT_SYMBOL)):
    try:
        return data_engine.get_quote(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chart", tags=["market"])
def get_chart_data(symbol: str = Query(default=DEFAULT_SYMBOL),
                   days: int = Query(default=60, ge=5, le=365)):
    try:
        df = data_engine.get_ohlcv(symbol).tail(days)
        return {
            "symbol": symbol,
            "dates":  [str(d.date()) for d in df.index],
            "open":   df["Open"].round(2).tolist(),
            "high":   df["High"].round(2).tolist(),
            "low":    df["Low"].round(2).tolist(),
            "close":  df["Close"].round(2).tolist(),
            "volume": df["Volume"].tolist(),
            "source": "kite_live" if kite_auth.is_authenticated() else "dummy",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/orderbook", tags=["market"])
def get_order_book(symbol: str = Query(default=DEFAULT_SYMBOL)):
    return {"symbol": symbol, "orderbook": data_engine.get_order_book(symbol)}


# ── Analysis ───────────────────────────────────────────────────────────────────

@app.get("/analyse", tags=["analysis"])
def analyse(symbol: str = Query(default=DEFAULT_SYMBOL)):
    try:
        return _analyse(symbol)
    except Exception as e:
        logger.exception("Analysis failed for %s", symbol)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/decision", tags=["analysis"])
def get_decision(symbol: str = Query(default=DEFAULT_SYMBOL)):
    try:
        a = _analyse(symbol)
        return {
            "symbol":        a["symbol"],
            "price":         a["price"],
            "data_source":   a["data_source"],
            "decision":      a["decision"],
            "stop_loss":     a["risk"]["stop_loss"]["price"],
            "news_sentiment": a["features"]["model_details"]["sentiment"]["label"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/risk", tags=["risk"])
def get_risk(symbol: str = Query(default=DEFAULT_SYMBOL)):
    try:
        a = _analyse(symbol)
        return {"symbol": symbol, **a["risk"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Orders ─────────────────────────────────────────────────────────────────────

@app.post("/order", tags=["execution"])
def place_order(req: OrderRequest):
    if req.side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")

    price = data_engine.get_current_price(req.symbol)

    if req.use_real:
        if not kite_auth.is_authenticated():
            raise HTTPException(status_code=401,
                detail="Not authenticated. Visit http://localhost:8000/kite/login")
        from backend.data_engine.kite_provider import KiteDataProvider
        provider = KiteDataProvider(kite_auth.get_kite())
        return provider.place_order(req.symbol, req.side, req.qty, req.order_type, req.price)

    return execution_engine.execute(req.symbol, req.side, price, price * req.qty)


# ── Portfolio ──────────────────────────────────────────────────────────────────

@app.get("/portfolio", tags=["execution"])
def get_portfolio():
    prices = {sym: data_engine.get_current_price(sym) for sym in execution_engine.positions}
    return execution_engine.portfolio_summary(prices)


@app.get("/trades", tags=["execution"])
def get_trade_log():
    return {"trades": execution_engine.get_trade_log()}


# ── Advanced ───────────────────────────────────────────────────────────────────

@app.get("/portfolio/optimize", tags=["portfolio"])
def optimize_portfolio(
    symbols: str = Query(default="RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS"),
):
    from backend.feature_engine.portfolio import optimize_portfolio as _opt
    import pandas as pd
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if len(sym_list) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 symbols")
    try:
        dfs = {sym: data_engine.get_ohlcv(sym)["Close"] for sym in sym_list}
        returns_df = pd.DataFrame({sym: df.pct_change() for sym, df in dfs.items()}).dropna()
        return _opt(returns_df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/daily", tags=["jarvis"])
async def daily_report(
    universe: str = Query(default="nifty50"),
    symbols: str  = Query(default=""),
):
    """
    Generate the Daily Street Pulse price-action report.
    Runs a full scan if no cached result exists, then classifies into
    Breakout / Momentum / Base / Weak buckets and writes trader-style commentary.
    """
    from backend.scanner.universe import NIFTY50_SYMBOLS
    from backend.scanner.report import generate_report

    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] or NIFTY50_SYMBOLS

    # Use cached scan if fresh (< 10 min), else re-scan
    cached = scan_engine.last_result()
    if not cached:
        cached = scan_engine.run(sym_list)
        await ws_manager.broadcast({"type": "scan_result", **cached})

    report = generate_report(cached)
    return report


@app.get("/monte-carlo", tags=["analysis"])
def run_monte_carlo(
    symbol: str = Query(default=DEFAULT_SYMBOL),
    simulations: int = Query(default=1000, ge=100, le=5000),
    horizon: int = Query(default=30, ge=5, le=90),
):
    from backend.feature_engine.simulation import monte_carlo
    df = data_engine.get_ohlcv(symbol)
    return {"symbol": symbol, **monte_carlo(df["Close"], n_sims=simulations, horizon=horizon)}
