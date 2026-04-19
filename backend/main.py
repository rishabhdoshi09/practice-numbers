"""
SimpleQuant FastAPI backend.
All five engines are wired together here and exposed via REST endpoints.
"""
from __future__ import annotations
import logging
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import DEFAULT_SYMBOLS, DEFAULT_SYMBOL, DEFAULT_PORTFOLIO_VALUE
from backend.data_engine import DataEngine
from backend.feature_engine import FeatureEngine
from backend.decision_engine import DecisionEngine
from backend.risk_engine import RiskEngine
from backend.execution_engine import ExecutionEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SimpleQuant API",
    description="Full-stack quantitative trading engine — internally complex, externally simple.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ─────────────────────────────────────────────────────────────────
# DataEngine tries live first; set use_live=False in tests / offline mode
data_engine      = DataEngine(use_live=True)
feature_engine   = FeatureEngine()
decision_engine  = DecisionEngine()
risk_engine      = RiskEngine()
execution_engine = ExecutionEngine(starting_capital=DEFAULT_PORTFOLIO_VALUE)


# ── Request / Response models ──────────────────────────────────────────────────
class OrderRequest(BaseModel):
    symbol: str
    side: str           # "BUY" or "SELL"
    position_inr: float = 50_000.0


# ── Helpers ────────────────────────────────────────────────────────────────────
def _analyse(symbol: str) -> dict:
    """Full analysis pipeline for one symbol — reused across endpoints."""
    df    = data_engine.get_ohlcv(symbol)
    news  = data_engine.get_news(symbol)
    price = float(df["Close"].iloc[-1])

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
        "symbol":   symbol,
        "price":    round(price, 2),
        "features": features,
        "decision": decision,
        "risk":     risk,
        "news":     news,
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "service": "SimpleQuant API v1.0"}


@app.get("/symbols", tags=["market"])
def list_symbols():
    """Return the supported symbol universe."""
    return {"symbols": DEFAULT_SYMBOLS}


@app.get("/analyse", tags=["analysis"])
def analyse(symbol: str = Query(default=DEFAULT_SYMBOL, description="NSE ticker, e.g. RELIANCE.NS")):
    """
    Core endpoint: run the full analysis pipeline for one symbol.
    Returns decision (BUY/SELL/HOLD), confidence, risk metrics, and signal breakdown.
    """
    try:
        return _analyse(symbol)
    except Exception as exc:
        logger.exception("Analysis failed for %s", symbol)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/decision", tags=["analysis"])
def get_decision(symbol: str = Query(default=DEFAULT_SYMBOL)):
    """Lightweight endpoint returning only the decision object — ideal for the home screen."""
    try:
        analysis = _analyse(symbol)
        return {
            "symbol":   analysis["symbol"],
            "price":    analysis["price"],
            "decision": analysis["decision"],
            "stop_loss": analysis["risk"]["stop_loss"]["price"],
            "news_sentiment": analysis["features"]["model_details"]["sentiment"]["label"],
        }
    except Exception as exc:
        logger.exception("Decision failed for %s", symbol)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/chart", tags=["market"])
def get_chart_data(symbol: str = Query(default=DEFAULT_SYMBOL),
                   days: int = Query(default=60, ge=5, le=365)):
    """OHLCV + technical overlay data for the price chart."""
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
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/risk", tags=["risk"])
def get_risk(symbol: str = Query(default=DEFAULT_SYMBOL)):
    """Full risk report for a symbol."""
    try:
        analysis = _analyse(symbol)
        return {"symbol": symbol, **analysis["risk"]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/orderbook", tags=["market"])
def get_order_book(symbol: str = Query(default=DEFAULT_SYMBOL)):
    return {"symbol": symbol, "orderbook": data_engine.get_order_book(symbol)}


@app.post("/order", tags=["execution"])
def place_order(req: OrderRequest):
    """
    Paper-trade an order.
    Side must be 'BUY' or 'SELL'.
    """
    if req.side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")
    price = data_engine.get_current_price(req.symbol)
    fill  = execution_engine.execute(req.symbol, req.side, price, req.position_inr)
    return fill


@app.get("/portfolio", tags=["execution"])
def get_portfolio():
    """Current paper portfolio — cash, positions, P&L, and Sharpe ratio."""
    prices = {sym: data_engine.get_current_price(sym) for sym in execution_engine.positions}
    return execution_engine.portfolio_summary(prices)


@app.get("/trades", tags=["execution"])
def get_trade_log():
    return {"trades": execution_engine.get_trade_log()}


@app.get("/portfolio/optimize", tags=["portfolio"])
def optimize_portfolio(
    symbols: str = Query(
        default="RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS",
        description="Comma-separated tickers",
    )
):
    """Markowitz Mean-Variance portfolio optimisation."""
    from backend.feature_engine.portfolio import optimize_portfolio as _opt
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if len(sym_list) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 symbols")
    try:
        dfs = {sym: data_engine.get_ohlcv(sym)["Close"] for sym in sym_list}
        import pandas as pd
        returns_df = pd.DataFrame({sym: df.pct_change() for sym, df in dfs.items()}).dropna()
        result = _opt(returns_df)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/monte-carlo", tags=["analysis"])
def run_monte_carlo(
    symbol: str = Query(default=DEFAULT_SYMBOL),
    simulations: int = Query(default=1000, ge=100, le=5000),
    horizon: int = Query(default=30, ge=5, le=90),
):
    """Monte Carlo simulation — forward price distribution fan chart."""
    from backend.feature_engine.simulation import monte_carlo
    df = data_engine.get_ohlcv(symbol)
    result = monte_carlo(df["Close"], n_sims=simulations, horizon=horizon)
    return {"symbol": symbol, **result}
