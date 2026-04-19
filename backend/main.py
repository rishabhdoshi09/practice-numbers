"""
SimpleQuant FastAPI backend.
All five engines + Zerodha Kite Connect live data & order placement.
"""
from __future__ import annotations
import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

load_dotenv()

from backend.config import DEFAULT_SYMBOLS, DEFAULT_SYMBOL, DEFAULT_PORTFOLIO_VALUE
from backend.data_engine import DataEngine
from backend.feature_engine import FeatureEngine
from backend.decision_engine import DecisionEngine
from backend.risk_engine import RiskEngine
from backend.execution_engine import ExecutionEngine
from backend import kite_auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SimpleQuant API",
    description="Full-stack quant trading — Zerodha Kite live data + 5-engine analysis",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ─────────────────────────────────────────────────────────────────
data_engine      = DataEngine(use_live=True)
feature_engine   = FeatureEngine()
decision_engine  = DecisionEngine()
risk_engine      = RiskEngine()
execution_engine = ExecutionEngine(starting_capital=DEFAULT_PORTFOLIO_VALUE)

# Wire up Kite if already authenticated (access token in .env)
_kite = kite_auth.get_kite()
if _kite:
    from backend.data_engine.kite_provider import KiteDataProvider
    _kite_provider = KiteDataProvider(_kite)
    data_engine.set_kite(_kite_provider)
    logger.info("Kite Connect: authenticated from saved token")
else:
    logger.info("Kite Connect: not authenticated — using yFinance/dummy fallback")


# ── Models ─────────────────────────────────────────────────────────────────────
class OrderRequest(BaseModel):
    symbol: str
    side: str
    qty: int = 1
    order_type: str = "MARKET"
    price: float = 0.0
    use_real: bool = False      # True → real Kite order, False → paper trade


# ── Helpers ────────────────────────────────────────────────────────────────────
def _analyse(symbol: str) -> dict:
    df    = data_engine.get_ohlcv(symbol)
    news  = data_engine.get_news(symbol)
    price = data_engine.get_current_price(symbol)

    features = feature_engine.compute(df, news)
    decision = decision_engine.decide(features["signals"], features)
    risk     = risk_engine.compute(
        df,
        current_price=price,
        atr=features["atr"],
        win_rate=0.55,
        avg_win_loss=1.4,
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


# ── Health & auth status ───────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def health():
    return {
        "status": "ok",
        "service": "SimpleQuant API v2.0",
        "kite_authenticated": kite_auth.is_authenticated(),
        "data_source": "kite_live" if kite_auth.is_authenticated() else "yfinance/dummy",
    }


# ── Kite auth routes ───────────────────────────────────────────────────────────

@app.get("/kite/login", tags=["auth"])
def kite_login():
    """Redirect user to Zerodha login. Open this URL in browser once per day."""
    url = kite_auth.get_login_url()
    return RedirectResponse(url=url)


@app.get("/kite/callback", tags=["auth"])
def kite_callback(request_token: str):
    """
    Zerodha redirects here after login with request_token.
    Exchanges it for access_token and activates live data.
    """
    global _kite_provider
    try:
        token = kite_auth.exchange_token(request_token)
        kite  = kite_auth.get_kite()
        from backend.data_engine.kite_provider import KiteDataProvider
        _kite_provider = KiteDataProvider(kite)
        data_engine.set_kite(_kite_provider)
        data_engine.clear_cache()
        # Start WebSocket ticker for default symbols
        _kite_provider.start_ticker(
            DEFAULT_SYMBOLS,
            on_tick=lambda sym, price: logger.debug("Tick %s: %.2f", sym, price),
        )
        return {
            "status": "authenticated",
            "message": "Kite live data active. Real-time WebSocket streaming started.",
            "access_token_preview": token[:8] + "...",
        }
    except Exception as e:
        logger.exception("Kite callback failed")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/kite/status", tags=["auth"])
def kite_status():
    return {
        "authenticated": kite_auth.is_authenticated(),
        "data_source":   "kite_live" if kite_auth.is_authenticated() else "yfinance/dummy",
        "login_url":     "http://localhost:8000/kite/login",
    }


# ── Market data ────────────────────────────────────────────────────────────────

@app.get("/symbols", tags=["market"])
def list_symbols():
    return {"symbols": DEFAULT_SYMBOLS}


@app.get("/quote", tags=["market"])
def get_quote(symbol: str = Query(default=DEFAULT_SYMBOL)):
    """Real-time price quote (Kite) or last close (fallback)."""
    try:
        return data_engine.get_quote(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chart", tags=["market"])
def get_chart_data(symbol: str = Query(default=DEFAULT_SYMBOL),
                   days: int = Query(default=60, ge=5, le=365)):
    try:
        df = data_engine.get_ohlcv(symbol)
        df_slice = df.tail(days)
        return {
            "symbol": symbol,
            "dates":  [str(d.date()) for d in df_slice.index],
            "open":   df_slice["Open"].round(2).tolist(),
            "high":   df_slice["High"].round(2).tolist(),
            "low":    df_slice["Low"].round(2).tolist(),
            "close":  df_slice["Close"].round(2).tolist(),
            "volume": df_slice["Volume"].tolist(),
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
    except Exception as exc:
        logger.exception("Analysis failed for %s", symbol)
        raise HTTPException(status_code=500, detail=str(exc))


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
    except Exception as exc:
        logger.exception("Decision failed for %s", symbol)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/risk", tags=["risk"])
def get_risk(symbol: str = Query(default=DEFAULT_SYMBOL)):
    try:
        a = _analyse(symbol)
        return {"symbol": symbol, **a["risk"]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Orders ─────────────────────────────────────────────────────────────────────

@app.post("/order", tags=["execution"])
def place_order(req: OrderRequest):
    """
    Place an order.
    use_real=true → real Kite order (requires authentication).
    use_real=false → paper trade simulation.
    """
    if req.side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")

    price = data_engine.get_current_price(req.symbol)

    # Real order via Kite
    if req.use_real:
        if not kite_auth.is_authenticated():
            raise HTTPException(
                status_code=401,
                detail="Not authenticated. Open http://localhost:8000/kite/login first."
            )
        kite = kite_auth.get_kite()
        from backend.data_engine.kite_provider import KiteDataProvider
        provider = KiteDataProvider(kite)
        return provider.place_order(req.symbol, req.side, req.qty, req.order_type, req.price)

    # Paper trade
    position_inr = price * req.qty
    return execution_engine.execute(req.symbol, req.side, price, position_inr)


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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/monte-carlo", tags=["analysis"])
def run_monte_carlo(
    symbol: str = Query(default=DEFAULT_SYMBOL),
    simulations: int = Query(default=1000, ge=100, le=5000),
    horizon: int = Query(default=30, ge=5, le=90),
):
    from backend.feature_engine.simulation import monte_carlo
    df = data_engine.get_ohlcv(symbol)
    result = monte_carlo(df["Close"], n_sims=simulations, horizon=horizon)
    return {"symbol": symbol, **result}
