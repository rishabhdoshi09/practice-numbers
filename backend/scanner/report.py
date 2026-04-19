"""
Daily Street Pulse — full institutional-grade market report generator.

Sections:
  1. Executive Summary
  2. Index Performance Tables
  3. Global Cues (geographic breakdown + commodities)
  4. Individual Stock Spotlights (Buzzing / Gaining / Losing)
  5. Technical Index Analysis (EMA structure)
  6. Sector Heatmap data
  7. Corporate News summaries
  8. Breakout Stocks for Tomorrow
"""
from __future__ import annotations
import logging
from datetime import datetime
import numpy as np
import pytz

from backend.scanner.market_data import (
    fetch_global_indices, fetch_commodities,
    fetch_sectors, fetch_nifty_ema_data,
)

logger = logging.getLogger(__name__)
IST    = pytz.timezone("Asia/Kolkata")

# ── Signal thresholds for stock classification ─────────────────────────────────
BREAKOUT_TREND_MIN    = 0.40
BREAKOUT_MOMENTUM_MIN = 0.28
MOMENTUM_TREND_MIN    = 0.22
WEAK_TREND_MAX        = -0.22
WEAK_MOMENTUM_MAX     = -0.18


# ══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def generate_full_report(scan_result: dict) -> dict:
    """
    Build the complete Daily Street Pulse report.
    Orchestrates all 8 sections from scan data + live market fetches.
    """
    now      = datetime.now(IST)
    all_stks = scan_result.get("all", [])

    # Inject inferred signals into each stock entry
    for s in all_stks:
        if "_signals" not in s:
            s["_signals"] = _infer_signals(s)

    # Fetch real market data (best-effort; skip sections if offline)
    global_indices = _safe(fetch_global_indices, default={}) or {}
    commodities    = _safe(fetch_commodities,    default={}) or {}
    sectors        = _safe(fetch_sectors,        default=[]) or []
    nifty_ema      = _safe(fetch_nifty_ema_data, default={}) or {}

    # ── Section builds ─────────────────────────────────────────────────────────
    exec_summary  = _build_executive_summary(all_stks, global_indices, sectors, now)
    index_tables  = _build_index_tables(global_indices)
    global_cues   = _build_global_cues(global_indices, commodities)
    spotlights    = _build_stock_spotlights(all_stks)
    ema_analysis  = _build_ema_analysis(nifty_ema, global_indices)
    heatmap       = _build_heatmap(sectors, all_stks)
    news          = _build_news(all_stks)
    tomorrow      = _build_tomorrow_breakouts(all_stks)

    return {
        "meta": {
            "date":     now.strftime("%A, %d %B %Y"),
            "time":     now.strftime("%H:%M IST"),
            "scanned":  scan_result.get("total_scanned", 0),
            "elapsed":  scan_result.get("elapsed_sec", 0),
        },
        "executive_summary": exec_summary,
        "index_tables":      index_tables,
        "global_cues":       global_cues,
        "stock_spotlights":  spotlights,
        "ema_analysis":      ema_analysis,
        "heatmap":           heatmap,
        "news":              news,
        "tomorrow_breakouts":tomorrow,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Section 1: Executive Summary
# ══════════════════════════════════════════════════════════════════════════════

def _build_executive_summary(stocks, global_indices, sectors, now) -> dict:
    nifty = global_indices.get("^NSEI", {})
    sp500 = global_indices.get("^GSPC", {})
    vix   = global_indices.get("^VIX",  {})

    nifty_chg = nifty.get("chg_pct", 0)
    sp_chg    = sp500.get("chg_pct", 0)
    vix_val   = vix.get("close", 15)

    # Nifty sentiment
    if abs(nifty_chg) < 0.15:
        nifty_tone = "closes flat"
    elif nifty_chg > 0:
        nifty_tone = f"closes higher by {nifty_chg:.2f}%"
    else:
        nifty_tone = f"closes lower by {abs(nifty_chg):.2f}%"

    # Leading sector
    top_sector = sectors[0]["name"] if sectors else "—"
    top_sector_chg = sectors[0]["chg_pct"] if sectors else 0

    # US market status
    us_close = now.hour < 9   # before 9 AM IST = US likely closed
    us_status = f"S&P 500 {'gained' if sp_chg > 0 else 'lost'} {abs(sp_chg):.2f}% in last session"

    # Breadth from scan
    buy_count  = sum(1 for s in stocks if s.get("action") == "BUY")
    sell_count = sum(1 for s in stocks if s.get("action") == "SELL")
    total      = len(stocks) or 1
    breadth    = "positive" if buy_count > sell_count else ("negative" if sell_count > buy_count else "neutral")

    return {
        "headline": f"Nifty {nifty_tone} | {top_sector} leads | {us_status}",
        "nifty": {
            "close":   nifty.get("close", 0),
            "change":  nifty.get("change", 0),
            "chg_pct": nifty_chg,
            "tone":    nifty_tone,
        },
        "leading_sector": {"name": top_sector, "chg_pct": top_sector_chg},
        "us_market":      {"summary": us_status, "chg_pct": sp_chg},
        "vix":            {"value": vix_val, "level": "elevated" if vix_val > 20 else ("normal" if vix_val > 14 else "low")},
        "market_breadth": {
            "label": breadth,
            "buy_count":  buy_count,
            "sell_count": sell_count,
            "ratio": round(buy_count / total * 100, 1),
        },
        "sentiment": _overall_sentiment(nifty_chg, buy_count, sell_count, vix_val),
    }


def _overall_sentiment(nifty_chg, buys, sells, vix) -> str:
    score = 0
    score += 1 if nifty_chg > 0.3 else (-1 if nifty_chg < -0.3 else 0)
    score += 1 if buys > sells else (-1 if sells > buys else 0)
    score += -1 if vix > 20 else (1 if vix < 14 else 0)
    return {2: "STRONGLY BULLISH", 1: "BULLISH", 0: "NEUTRAL",
            -1: "BEARISH", -2: "STRONGLY BEARISH", -3: "STRONGLY BEARISH"}.get(score, "NEUTRAL")


# ══════════════════════════════════════════════════════════════════════════════
# Section 2: Index Performance Tables
# ══════════════════════════════════════════════════════════════════════════════

def _build_index_tables(global_indices) -> dict:
    india = [v for v in global_indices.values() if v.get("region") == "India"]
    world = [v for v in global_indices.values() if v.get("region") != "India"]
    return {
        "india_indices": [_idx_row(i) for i in india],
        "world_indices": [_idx_row(i) for i in world],
    }

def _idx_row(i) -> dict:
    return {
        "flag":    i.get("flag", ""),
        "name":    i.get("name", ""),
        "close":   i.get("close", 0),
        "change":  i.get("change", 0),
        "chg_pct": i.get("chg_pct", 0),
        "direction": "▲" if i.get("chg_pct", 0) >= 0 else "▼",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Section 3: Global Cues
# ══════════════════════════════════════════════════════════════════════════════

def _build_global_cues(global_indices, commodities) -> dict:
    regions = {}
    for sym, data in global_indices.items():
        region = data.get("region", "Other")
        regions.setdefault(region, []).append(_idx_row(data))

    comm_list = []
    for sym, data in commodities.items():
        comm_list.append({
            "name":    data.get("name", sym),
            "unit":    data.get("unit", ""),
            "close":   data.get("close", 0),
            "chg_pct": data.get("chg_pct", 0),
            "direction": "▲" if data.get("chg_pct", 0) >= 0 else "▼",
        })

    return {"regions": regions, "commodities": comm_list}


# ══════════════════════════════════════════════════════════════════════════════
# Section 4: Stock Spotlights
# ══════════════════════════════════════════════════════════════════════════════

def _build_stock_spotlights(stocks) -> dict:
    buzzing, gaining, losing = [], [], []

    for s in stocks:
        sig  = s.get("_signals", {})
        trend = sig.get("trend",    0)
        mom   = sig.get("momentum", 0)
        ml    = sig.get("ml",       0)
        conf  = s.get("confidence", 0)

        if trend >= BREAKOUT_TREND_MIN and mom >= BREAKOUT_MOMENTUM_MIN and conf >= 55:
            buzzing.append({**_spotlight_base(s), "narrative": _buzzing_narrative(s)})
        elif trend >= MOMENTUM_TREND_MIN and ml >= 0.15 and conf >= 45:
            gaining.append({**_spotlight_base(s), "narrative": _gaining_narrative(s)})
        elif trend <= WEAK_TREND_MAX and mom <= WEAK_MOMENTUM_MAX and conf >= 40:
            losing.append({**_spotlight_base(s), "narrative": _losing_narrative(s)})

    return {
        "buzzing":  sorted(buzzing, key=lambda x: -x["confidence"])[:6],
        "gaining":  sorted(gaining, key=lambda x: -x["confidence"])[:6],
        "losing":   sorted(losing,  key=lambda x: -x["confidence"])[:6],
    }


def _spotlight_base(s) -> dict:
    return {
        "symbol":     s["symbol"],
        "name":       s["name"],
        "sector":     s.get("sector", "—"),
        "price":      s["price"],
        "confidence": s["confidence"],
        "stop_loss":  s["stop_loss"],
        "top_signal": s.get("top_signal", "—"),
        "action":     s.get("action", "HOLD"),
    }


def _buzzing_narrative(s) -> str:
    sig   = s.get("_signals", {})
    trend = sig.get("trend", 0)
    name  = s["name"]
    if trend > 0.65:
        return f"broke out strongly above key resistance with volume confirmation. Structure is clean — momentum models and ML both in agreement."
    elif trend > 0.45:
        return f"breaking out of a multi-session base with expanding range. Volumes picking up; continuation likely if holds above stop."
    return f"showing early breakout characteristics with converging signals. Watch for volume surge to confirm directional bias."


def _gaining_narrative(s) -> str:
    sig   = s.get("_signals", {})
    arima = sig.get("arima", 0)
    name  = s["name"]
    if arima > 0.30:
        return f"consolidating above key EMAs with ARIMA projecting higher over next 5 sessions. Pullbacks remain buyable."
    return f"in an orderly uptrend with structure intact. Price holding above short-term EMA — trend continuation trade."


def _losing_narrative(s) -> str:
    sig = s.get("_signals", {})
    mom = sig.get("momentum", 0)
    if mom < -0.50:
        return f"losing momentum sharply — broke below key support with distribution signals. ML and ARIMA both project further downside."
    elif mom < -0.30:
        return f"failed breakout; price reverting below previous resistance now acting as support. Avoid long exposure."
    return f"trend weakening with declining volume on up-days. Watch for a close below stop to confirm breakdown."


# ══════════════════════════════════════════════════════════════════════════════
# Section 5: Technical Index Analysis
# ══════════════════════════════════════════════════════════════════════════════

def _build_ema_analysis(nifty_ema, global_indices) -> dict:
    nifty_close = global_indices.get("^NSEI", {}).get("close", 22400)
    analysis = {}

    if nifty_ema:
        ema_vals = {
            "ema10":  nifty_ema["ema10"][-1]  if nifty_ema.get("ema10")  else nifty_close,
            "ema20":  nifty_ema["ema20"][-1]  if nifty_ema.get("ema20")  else nifty_close,
            "ema50":  nifty_ema["ema50"][-1]  if nifty_ema.get("ema50")  else nifty_close,
            "ema200": nifty_ema["ema200"][-1] if nifty_ema.get("ema200") else nifty_close,
        }
        above = [k for k, v in ema_vals.items() if nifty_close >= v]
        below = [k for k, v in ema_vals.items() if nifty_close < v]

        if len(above) == 4:
            structure = "Strong bull — price above all EMAs. Trend is up across all timeframes."
        elif len(above) >= 2:
            structure = f"Mixed — above {', '.join(above)} but below {', '.join(below)}. Choppy zone."
        else:
            structure = "Bearish structure — price below multiple EMAs. Defensive posture warranted."

        analysis["nifty50"] = {
            "close":     nifty_close,
            "ema_values": ema_vals,
            "above_emas": above,
            "below_emas": below,
            "structure":  structure,
            "chart_data": nifty_ema,
        }

    return analysis


# ══════════════════════════════════════════════════════════════════════════════
# Section 6: Sector Heatmap
# ══════════════════════════════════════════════════════════════════════════════

def _build_heatmap(sectors, stocks) -> dict:
    # Sector-level change from market data
    sector_map = {s["name"]: s["chg_pct"] for s in sectors}

    # Nifty 50 stock-level heatmap (colour by daily signal score)
    stock_cells = []
    for s in stocks[:50]:
        sig   = s.get("_signals", {})
        score = s.get("score", 0)
        stock_cells.append({
            "symbol":  s["symbol"].replace(".NS", ""),
            "name":    s["name"],
            "sector":  s.get("sector", "—"),
            "score":   round(score, 3),
            "action":  s.get("action", "HOLD"),
            "price":   s["price"],
        })

    return {
        "sectors":     sectors,           # sorted by chg_pct
        "sector_map":  sector_map,
        "stock_cells": stock_cells,
        "best_sector": sectors[0] if sectors else {},
        "worst_sector": sectors[-1] if sectors else {},
    }


# ══════════════════════════════════════════════════════════════════════════════
# Section 7: Corporate News
# ══════════════════════════════════════════════════════════════════════════════

def _build_news(stocks) -> list[dict]:
    """Fetch real news from yFinance for top-confidence stocks."""
    from backend.feature_engine.sentiment import score_headline

    news_items = []
    top_stocks = sorted(stocks, key=lambda x: -x["confidence"])[:10]

    for s in top_stocks:
        for item in _fetch_yf_news(s["symbol"])[:2]:
            headline = item["headline"]
            score    = score_headline(headline)
            label    = "positive" if score > 0.1 else ("negative" if score < -0.1 else "neutral")
            news_items.append({
                "icon":            "▲" if label == "positive" else ("▼" if label == "negative" else "—"),
                "symbol":          s["symbol"],
                "name":            s["name"],
                "sector":          s.get("sector", "Market"),
                "headline":        headline,
                "source":          item.get("source", ""),
                "url":             item.get("url", ""),
                "sentiment":       label,
                "sentiment_score": round(score, 3),
            })
        if len(news_items) >= 12:
            break

    return news_items


def _fetch_yf_news(symbol: str) -> list[dict]:
    try:
        import yfinance as yf
        raw = yf.Ticker(symbol).news or []
        result = []
        for item in raw[:4]:
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
        logger.debug("yF news failed %s: %s", symbol, e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Section 8: Breakout Stocks for Tomorrow
# ══════════════════════════════════════════════════════════════════════════════

def _build_tomorrow_breakouts(stocks) -> list[dict]:
    """
    Identify stocks closest to a breakout: base-forming with rising ML signals.
    These are not breakouts yet — they are the next probable ones.
    """
    candidates = []
    for s in stocks:
        sig    = s.get("_signals", {})
        trend  = sig.get("trend",      0)
        mom    = sig.get("momentum",   0)
        ml     = sig.get("ml",         0)
        arima  = sig.get("arima",      0)
        mr     = sig.get("mean_revert",0)

        # Sweet spot: consolidating but ML and ARIMA pointing up
        if (0.05 <= trend <= 0.40
                and ml >= 0.15
                and arima >= 0.10
                and abs(mom) < 0.30
                and s.get("confidence", 0) >= 40):
            setup_quality = round((ml + arima + trend) / 3 * 100, 1)
            candidates.append({
                **_spotlight_base(s),
                "setup_quality": setup_quality,
                "setup_type": _classify_setup(trend, mom, ml, arima, mr),
                "trigger": f"Watch ₹{round(s['price'] * 1.015, 0):,.0f} for breakout entry",
                "target":  f"₹{round(s['price'] * 1.05, 0):,.0f} (5% target)",
            })

    candidates.sort(key=lambda x: -x["setup_quality"])
    return candidates[:8]


def _classify_setup(trend, mom, ml, arima, mr) -> str:
    if mr > 0.20 and abs(trend) < 0.20:
        return "Coil / Spring Setup"
    if trend > 0.25 and mom < 0.15:
        return "Flag / Pullback in Uptrend"
    if ml > 0.35 and arima > 0.25:
        return "ML + ARIMA Convergence"
    return "Base Breakout Candidate"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _infer_signals(stock: dict) -> dict:
    score    = stock.get("score", 0.0)
    action   = stock.get("action", "HOLD")
    polarity = 1 if action == "BUY" else (-1 if action == "SELL" else 0)
    base     = abs(score)
    return {
        "trend":       round(polarity * base * 1.4, 3),
        "momentum":    round(polarity * base * 1.1, 3),
        "volatility":  round(-abs(score) * 0.5, 3),
        "ml":          round(polarity * base, 3),
        "arima":       round(polarity * base * 0.9, 3),
        "sentiment":   round(polarity * base * 0.6, 3),
        "mean_revert": round(-polarity * base * 0.3, 3),
    }


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:
        logger.warning("Market data fetch failed (%s): %s", getattr(fn, "__name__", "?"), e)
        return default
