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
        for ws in list(self.active):   # copy to avoid mutation-during-iteration race
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.active:
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
    allow_credentials=False,   # cannot be True with wildcard origin (CORS spec violation)
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


# ── Full NSE universe scan ─────────────────────────────────────────────────────

@app.get("/scan/full", tags=["jarvis"])
async def run_full_scan(
    workers:  int  = Query(default=8,   ge=1, le=20,  description="Parallel workers (sector buckets)"),
    limit:    int  = Query(default=0,   ge=0,          description="Cap symbols (0 = all)"),
    sector:   str  = Query(default="",                 description="Filter to one sector"),
):
    """
    Scan the full NSE equity universe (~2000 stocks when Kite authenticated,
    ~200 otherwise) using parallel sector-bucketed workers.

    Each worker handles one sector bucket concurrently.
    Results are pushed to all WebSocket clients on completion.
    """
    from backend.scanner.full_universe import get_full_universe, get_symbols_only
    from backend.scanner.swarm_scan    import run_swarm_scan

    kite = kite_auth.get_kite() if kite_auth.is_authenticated() else None
    universe = get_full_universe(kite=kite)

    if sector:
        universe = [u for u in universe if u["sector"].lower() == sector.lower()]
    if limit and limit > 0:
        universe = universe[:limit]

    progress: list[str] = []

    def on_progress(done, total, label):
        progress.append(f"{done}/{total} [{label}]")
        logger.info("Full scan progress: %d/%d", done, total)

    try:
        result = run_swarm_scan(
            universe, data_engine, feature_engine,
            decision_engine, risk_engine,
            n_workers=workers, on_progress=on_progress,
        )
        await ws_manager.broadcast({"type": "full_scan_result", **result})
        return result
    except Exception as e:
        logger.exception("Full scan failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/universe", tags=["jarvis"])
def get_universe_info():
    """Return the current equity universe (no analysis — just symbol list with metadata)."""
    from backend.scanner.full_universe import get_full_universe, bucket_by_sector

    kite     = kite_auth.get_kite() if kite_auth.is_authenticated() else None
    universe = get_full_universe(kite=kite)
    buckets  = bucket_by_sector(universe, n_workers=8)

    sector_counts: dict[str, int] = {}
    for u in universe:
        sector_counts[u["sector"]] = sector_counts.get(u["sector"], 0) + 1

    return {
        "total":         len(universe),
        "source":        "kite" if kite else "fallback_list",
        "sectors":       sector_counts,
        "bucket_sizes":  [len(b) for b in buckets],
        "symbols":       [u["symbol"] for u in universe],
    }


@app.post("/scan/bucket", tags=["jarvis"])
async def scan_single_bucket(
    symbols: str = Query(description="Comma-separated symbols for this bucket"),
):
    """
    Scan a specific list of symbols.
    Designed for claude-flow agent invocation — each agent calls this endpoint
    for its assigned sector bucket and the coordinator aggregates results.
    """
    from backend.scanner.full_universe import get_full_universe
    from backend.scanner.swarm_scan    import scan_bucket_by_symbols

    kite     = kite_auth.get_kite() if kite_auth.is_authenticated() else None
    universe = get_full_universe(kite=kite)
    meta     = {u["symbol"]: u for u in universe}

    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=400, detail="No symbols provided")

    try:
        results = scan_bucket_by_symbols(
            sym_list, meta, data_engine, feature_engine, decision_engine, risk_engine,
        )
        return {"symbols_scanned": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Market data ────────────────────────────────────────────────────────────────

@app.get("/symbols", tags=["market"])
def list_symbols():
    return {"symbols": DEFAULT_SYMBOLS}


@app.get("/symbols/search", tags=["market"])
def search_symbols(
    q:     str = Query(default="",    description="Search query (name, ticker, sector)"),
    limit: int = Query(default=80,    ge=1, le=5000),
    exchange: str = Query(default="all", description="all | nse | bse"),
):
    """
    Search the full NSE+BSE equity universe by name, ticker or sector.
    Returns up to `limit` matches sorted by relevance.
    Used by the StockSelector typeahead.
    """
    from backend.scanner.full_universe import get_full_universe

    kite     = kite_auth.get_kite() if kite_auth.is_authenticated() else None
    universe = get_full_universe(kite=kite)

    # Add .BO (BSE) equivalents for every NSE symbol — yFinance supports SYMBOL.BO
    bse_extras: list[dict] = []
    for item in universe:
        if item["symbol"].endswith(".NS"):
            bse_sym = item["symbol"].replace(".NS", ".BO")
            bse_extras.append({
                "symbol": bse_sym,
                "name":   item["name"] + " (BSE)",
                "sector": item["sector"],
            })

    combined = universe + bse_extras

    q_lower = q.strip().lower()
    if q_lower:
        def score(item):
            sym  = item["symbol"].lower()
            name = item["name"].lower()
            if sym.startswith(q_lower) or name.startswith(q_lower):
                return 0
            if q_lower in sym or q_lower in name:
                return 1
            if q_lower in (item.get("sector") or "").lower():
                return 2
            return 99
        matched = [i for i in combined if score(i) < 99]
        matched.sort(key=score)
    else:
        matched = combined

    if exchange == "nse":
        matched = [i for i in matched if i["symbol"].endswith(".NS")]
    elif exchange == "bse":
        matched = [i for i in matched if i["symbol"].endswith(".BO")]

    return {
        "total":   len(matched),
        "results": matched[:limit],
    }


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
    try:
        return {"symbol": symbol, "orderbook": data_engine.get_order_book(symbol)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            "stop_loss":     a["risk"].get("stop_loss", {}).get("price"),
            "news_sentiment": (
                a.get("features", {})
                 .get("model_details", {})
                 .get("sentiment", {})
                 .get("label", "neutral")
            ),
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
    Generate the full Daily Street Pulse report with all 8 sections:
    Executive Summary, Index Tables, Global Cues, Stock Spotlights,
    EMA Analysis, Sector Heatmap, Corporate News, Tomorrow Breakouts.
    """
    from backend.scanner.universe import NIFTY50_SYMBOLS
    from backend.scanner.report import generate_full_report

    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] or NIFTY50_SYMBOLS

    cached = scan_engine.last_result()
    if not cached:
        cached = scan_engine.run(sym_list)
        await ws_manager.broadcast({"type": "scan_result", **cached})

    report = generate_full_report(cached)
    return report


# ── 5-Stage Autonomous Investment Pipeline ─────────────────────────────────────

@app.get("/invest/pipeline", tags=["invest"])
async def run_investment_pipeline(
    capital: int = Query(default=500_000, ge=10_000, description="Total capital in INR"),
    symbols: str  = Query(default="",    description="Comma-separated override (default: Nifty 50)"),
):
    """
    Run the full 5-stage autonomous investment pipeline.

    Stage 1 — Screen: Score all Nifty 50 stocks via 8-engine quant analysis.
    Stage 2 — Adversarial: Bull vs Bear debate for top 5 candidates.
    Stage 3 — Scenario Modeling: Bull/Base/Bear price targets at 1m/3m/6m/12m.
    Stage 4 — Portfolio Construction: Markowitz max-Sharpe with sector constraints.
    Stage 5 — Rebalancing: Compare vs existing portfolio; recommend swaps/sells.
    """
    from datetime import datetime as _dt
    from backend.scanner.universe import NIFTY50_SYMBOLS
    from backend.scanner.adversarial import run_adversarial
    from backend.scanner.scenarios import build_scenarios
    from backend.scanner.portfolio_builder import build_portfolio
    from backend.scanner.rebalancer import generate_rebalance_plan

    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] or NIFTY50_SYMBOLS

    # ── Stage 1: Screen ────────────────────────────────────────────────────────
    scan = scan_engine.last_result()
    if not scan:
        scan = scan_engine.run(sym_list)
        await ws_manager.broadcast({"type": "scan_result", **scan})

    top_candidates = scan.get("top_buys", [])[:10]

    # ── Stages 2 & 3: Adversarial + Scenarios for top 5 ───────────────────────
    adversarial_results: list[dict] = []
    scenario_results:    list[dict] = []

    for stock in top_candidates[:5]:
        sym = stock["symbol"]
        try:
            df       = data_engine.get_ohlcv(sym)
            news     = data_engine.get_news(sym)
            price    = float(df["Close"].iloc[-1])
            features = feature_engine.compute(df, news)
            decision = decision_engine.decide(features["signals"], features)
            risk     = risk_engine.compute(
                df, current_price=price,
                atr=features["atr"],
                portfolio_value=capital,
            )

            adv = run_adversarial(sym, features, decision, risk)
            adversarial_results.append({
                "symbol": sym,
                "name":   stock.get("name", sym),
                "sector": stock.get("sector", "—"),
                "price":  price,
                **adv,
            })

            sc = build_scenarios(sym, df["Close"], features)
            scenario_results.append(sc)

        except Exception as e:
            logger.warning("Pipeline analysis failed for %s: %s", sym, e)

    # ── Stage 4: Portfolio Construction ───────────────────────────────────────
    portfolio = build_portfolio(scan, data_engine, capital=capital)

    # ── Stage 5: Rebalancing ───────────────────────────────────────────────────
    prices      = {sym: data_engine.get_current_price(sym)
                   for sym in execution_engine.positions}
    current_pf  = execution_engine.portfolio_summary(prices)

    # Use the freshly-built portfolio if paper portfolio is empty
    rebalance_base = portfolio if not current_pf.get("positions") else current_pf
    rebalance      = generate_rebalance_plan(rebalance_base, scan)

    return {
        "pipeline_time": _dt.now().isoformat(),
        "capital":       capital,

        "stage1_screening": {
            "total_scanned": scan.get("total_scanned", 0),
            "elapsed_sec":   scan.get("elapsed_sec",   0),
            "summary":       scan.get("summary",        {}),
            "top_candidates": [
                {
                    "symbol":     s["symbol"],
                    "name":       s.get("name", s["symbol"]),
                    "sector":     s.get("sector", "—"),
                    "confidence": s["confidence"],
                    "action":     s["action"],
                    "price":      s["price"],
                }
                for s in top_candidates
            ],
        },

        "stage2_adversarial": adversarial_results,
        "stage3_scenarios":   scenario_results,
        "stage4_portfolio":   portfolio,
        "stage5_rebalance":   rebalance,
    }


@app.get("/invest/scorecard/{symbol}", tags=["invest"])
def get_scorecard(symbol: str):
    """
    Institutional risk scorecard — single ticker.
    Returns full financial metrics, 3-component risk score (0-100),
    quarterly table, price history, catalysts, risks, and final verdict.
    """
    from backend.scanner.scorecard import generate_scorecard
    try:
        return generate_scorecard(symbol)
    except Exception as e:
        logger.exception("Scorecard failed for %s", symbol)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/invest/adversarial/{symbol}", tags=["invest"])
def invest_adversarial(symbol: str):
    """Bull vs Bear debate for a single stock."""
    from backend.scanner.adversarial import run_adversarial
    try:
        df       = data_engine.get_ohlcv(symbol)
        news     = data_engine.get_news(symbol)
        price    = float(df["Close"].iloc[-1])
        features = feature_engine.compute(df, news)
        decision = decision_engine.decide(features["signals"], features)
        risk     = risk_engine.compute(df, current_price=price, atr=features["atr"])
        return {"symbol": symbol, "price": price,
                **run_adversarial(symbol, features, decision, risk)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/invest/scenarios/{symbol}", tags=["invest"])
def invest_scenarios(symbol: str):
    """Scenario price targets (bull/base/bear × 1m/3m/6m/12m) for one stock."""
    from backend.scanner.scenarios import build_scenarios
    try:
        df       = data_engine.get_ohlcv(symbol)
        news     = data_engine.get_news(symbol)
        features = feature_engine.compute(df, news)
        return build_scenarios(symbol, df["Close"], features)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vp/{symbol}", tags=["volume-profile"])
def get_volume_profile(
    symbol:    str,
    timeframe: str  = Query(default="1d",  description="5m | 15m | 1d"),
    n_bins:    int  = Query(default=50,    ge=20, le=200),
    lookback:  int  = Query(default=60,    ge=20, le=500),
    backtest:  bool = Query(default=True,  description="Include backtest metrics"),
):
    """
    Full Volume Profile analysis for a symbol.

    Returns:
      - profile: POC, VAH, VAL, HVN/LVN levels, full bin histogram
      - signals: current LONG / SHORT / HOLD signals with entry/SL/TP
      - backtest: historical win-rate, Sharpe, drawdown (optional)
    """
    from backend.feature_engine.volume_profile import calculate_volume_profile, fetch_vp_ohlcv
    from backend.feature_engine.vp_signals     import generate_vp_signals
    from backend.feature_engine.vp_backtest    import run_vp_backtest

    try:
        df = fetch_vp_ohlcv(symbol, timeframe=timeframe, lookback=lookback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data fetch failed: {e}")

    try:
        vp      = calculate_volume_profile(df, n_bins=n_bins)
        signals = generate_vp_signals(df, vp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VP calculation failed: {e}")

    result: dict = {
        "symbol":    symbol,
        "timeframe": timeframe,
        "lookback":  lookback,
        "bars":      len(df),
        "profile":   vp.to_dict(),
        "signals":   signals,
        "backtest":  None,
    }

    if backtest:
        try:
            bt_df = fetch_vp_ohlcv(symbol, timeframe=timeframe, lookback=min(lookback * 4, 500))
            result["backtest"] = run_vp_backtest(bt_df, n_bins=n_bins)
        except Exception as e:
            logger.warning("VP backtest failed for %s: %s", symbol, e)
            result["backtest"] = {"error": str(e)}

    return result


@app.get("/monte-carlo", tags=["analysis"])
def run_monte_carlo(
    symbol: str = Query(default=DEFAULT_SYMBOL),
    simulations: int = Query(default=1000, ge=100, le=5000),
    horizon: int = Query(default=30, ge=5, le=90),
):
    from backend.feature_engine.simulation import monte_carlo
    df = data_engine.get_ohlcv(symbol)
    return {"symbol": symbol, **monte_carlo(df["Close"], n_sims=simulations, horizon=horizon)}
