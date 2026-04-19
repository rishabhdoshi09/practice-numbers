"""
Institutional Risk Scorecard Engine.

Fetches real financial data via yFinance and computes a 0-100 risk score
across three dimensions:

  Valuation      (35 pts) — P/E, EV/EBITDA, P/B, P/S
  Financial Health (35 pts) — Debt/Equity, FCF yield, current ratio
  Growth          (30 pts) — Revenue growth, profit growth, EPS growth

Also derives catalysts, risks, and a final investment verdict.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Public entry point
# ══════════════════════════════════════════════════════════════════════════════

def generate_scorecard(symbol: str) -> dict:
    """Fetch data from yFinance and build the full scorecard dict."""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    info   = ticker.info or {}

    # ── Price & company basics ─────────────────────────────────────────────
    price     = _val(info, "currentPrice", "regularMarketPrice", "previousClose")
    prev      = _val(info, "previousClose", "regularMarketPreviousClose") or price
    chg_pct   = round((price - prev) / prev * 100, 2) if prev else 0
    mkt_cap   = _val(info, "marketCap") or 0

    company = {
        "name":       info.get("longName") or info.get("shortName") or symbol,
        "symbol":     symbol,
        "sector":     info.get("sector", "—"),
        "industry":   info.get("industry", "—"),
        "price":      round(price, 2),
        "chg_pct":    chg_pct,
        "market_cap": mkt_cap,
        "currency":   info.get("currency", "INR"),
        "exchange":   info.get("exchange", "NSE"),
        "website":    info.get("website", ""),
    }

    # ── Key metrics ────────────────────────────────────────────────────────
    pe        = _val(info, "trailingPE", "forwardPE")
    ev_ebitda = _val(info, "enterpriseToEbitda")
    pb        = _val(info, "priceToBook")
    ps        = _val(info, "priceToSalesTrailing12Months")
    roe       = _val(info, "returnOnEquity")           # decimal
    roce_proxy= _val(info, "returnOnAssets")           # proxy for ROCE
    de_ratio  = _val(info, "debtToEquity")             # as reported by yF (×100 for some)
    if de_ratio and de_ratio > 20:                     # yF sometimes gives as 100× pct
        de_ratio /= 100
    fcf       = _val(info, "freeCashflow") or 0
    rev_growth= _val(info, "revenueGrowth")            # decimal
    earn_growth=_val(info, "earningsGrowth")           # decimal
    eps_trail = _val(info, "trailingEps")
    eps_fwd   = _val(info, "forwardEps")
    div_yield = _val(info, "dividendYield") or 0

    metrics = {
        "pe_ratio":      _safe_round(pe,        2),
        "ev_ebitda":     _safe_round(ev_ebitda, 2),
        "pb_ratio":      _safe_round(pb,        2),
        "ps_ratio":      _safe_round(ps,        2),
        "roe":           _safe_round(roe * 100, 1) if roe else None,
        "roce":          _safe_round(roce_proxy * 100, 1) if roce_proxy else None,
        "debt_equity":   _safe_round(de_ratio,  2),
        "fcf":           fcf,
        "revenue_growth":_safe_round((rev_growth or 0) * 100, 1),
        "profit_growth": _safe_round((earn_growth or 0) * 100, 1),
        "eps_trailing":  _safe_round(eps_trail, 2),
        "eps_forward":   _safe_round(eps_fwd,   2),
        "dividend_yield":_safe_round(div_yield * 100, 2),
    }

    # ── Scoring ────────────────────────────────────────────────────────────
    val_score,  val_detail  = _score_valuation(pe, ev_ebitda, pb, ps)
    fin_score,  fin_detail  = _score_financial_health(de_ratio, fcf, mkt_cap, info)
    grow_score, grow_detail = _score_growth(rev_growth, earn_growth, eps_trail, eps_fwd)

    total_score = round(val_score + fin_score + grow_score, 1)

    if total_score < 30:
        risk_label = "LOW RISK"
        risk_color = "green"
    elif total_score < 60:
        risk_label = "MODERATE RISK"
        risk_color = "amber"
    else:
        risk_label = "HIGH RISK"
        risk_color = "red"

    scoring = {
        "total":   total_score,
        "label":   risk_label,
        "color":   risk_color,
        "valuation": {
            "score": round(val_score,  1),
            "max":   35,
            "pct":   round(val_score  / 35 * 100),
            **val_detail,
        },
        "financial_health": {
            "score": round(fin_score,  1),
            "max":   35,
            "pct":   round(fin_score  / 35 * 100),
            **fin_detail,
        },
        "growth": {
            "score": round(grow_score, 1),
            "max":   30,
            "pct":   round(grow_score / 30 * 100),
            **grow_detail,
        },
    }

    # ── Quarterly financials ───────────────────────────────────────────────
    quarterly = _fetch_quarterly(ticker)

    # ── 12-month price history ─────────────────────────────────────────────
    price_history = _fetch_price_history(ticker)

    # ── News ───────────────────────────────────────────────────────────────
    news_items = []
    try:
        raw_news = ticker.news or []
        for item in raw_news[:5]:
            title = item.get("title", "")
            if title:
                news_items.append({
                    "headline":  title,
                    "source":    item.get("publisher", ""),
                    "url":       item.get("link", ""),
                    "published": item.get("providerPublishTime", 0),
                })
    except Exception:
        pass

    # ── Catalysts & Risks (derived from data) ─────────────────────────────
    catalysts = _derive_catalysts(metrics, scoring)
    risks     = _derive_risks(metrics, scoring, info)

    # ── Verdict ────────────────────────────────────────────────────────────
    verdict = _final_verdict(total_score, metrics)

    return {
        "generated_at": datetime.now().isoformat(),
        "company":       company,
        "metrics":       metrics,
        "scoring":       scoring,
        "quarterly":     quarterly,
        "price_history": price_history,
        "news":          news_items,
        "catalysts":     catalysts,
        "risks":         risks,
        "verdict":       verdict,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Scoring sub-engines
# ══════════════════════════════════════════════════════════════════════════════

def _score_valuation(pe, ev_ebitda, pb, ps) -> tuple[float, dict]:
    """Returns score 0–35 (higher = riskier)."""

    # P/E (0–18)
    if pe is None:
        pe_s = 10  # unknown → moderate risk
    elif pe < 0:
        pe_s = 18  # negative earnings
    elif pe < 12:
        pe_s = 2
    elif pe < 18:
        pe_s = 5
    elif pe < 25:
        pe_s = 9
    elif pe < 35:
        pe_s = 13
    elif pe < 50:
        pe_s = 16
    else:
        pe_s = 18

    # EV/EBITDA (0–10)
    if ev_ebitda is None:
        ev_s = 5
    elif ev_ebitda < 6:
        ev_s = 1
    elif ev_ebitda < 10:
        ev_s = 3
    elif ev_ebitda < 15:
        ev_s = 6
    elif ev_ebitda < 22:
        ev_s = 8
    else:
        ev_s = 10

    # P/B (0–4)
    if pb is None:
        pb_s = 2
    elif pb < 1.5:
        pb_s = 0
    elif pb < 3:
        pb_s = 1
    elif pb < 5:
        pb_s = 2
    elif pb < 10:
        pb_s = 3
    else:
        pb_s = 4

    # P/S (0–3)
    if ps is None:
        ps_s = 1
    elif ps < 1:
        ps_s = 0
    elif ps < 3:
        ps_s = 1
    elif ps < 6:
        ps_s = 2
    else:
        ps_s = 3

    total = min(35, pe_s + ev_s + pb_s + ps_s)

    label = ("Cheap" if total < 10 else
             "Fair Value" if total < 18 else
             "Stretched" if total < 26 else "Overvalued")

    return total, {
        "pe_sub":       pe_s,
        "ev_sub":       ev_s,
        "pb_sub":       pb_s,
        "ps_sub":       ps_s,
        "label":        label,
        "summary": f"P/E {_fmt(pe,'x')} · EV/EBITDA {_fmt(ev_ebitda,'x')} · P/B {_fmt(pb,'x')}",
    }


def _score_financial_health(de_ratio, fcf, mkt_cap, info) -> tuple[float, dict]:
    """Returns score 0–35 (higher = riskier)."""

    # Debt/Equity (0–18)
    if de_ratio is None:
        de_s = 8
    elif de_ratio < 0.1:
        de_s = 0
    elif de_ratio < 0.3:
        de_s = 3
    elif de_ratio < 0.6:
        de_s = 7
    elif de_ratio < 1.0:
        de_s = 11
    elif de_ratio < 1.5:
        de_s = 15
    else:
        de_s = 18

    # FCF yield (0–12)
    fcf_yield = (fcf / mkt_cap) if mkt_cap and mkt_cap > 0 else None
    if fcf_yield is None:
        fcf_s = 6
    elif fcf_yield > 0.07:
        fcf_s = 0
    elif fcf_yield > 0.04:
        fcf_s = 2
    elif fcf_yield > 0.01:
        fcf_s = 5
    elif fcf_yield > 0:
        fcf_s = 8
    else:
        fcf_s = 12   # negative FCF = high risk

    # Current ratio (0–5)
    cr = info.get("currentRatio")
    if cr is None:
        cr_s = 2
    elif cr > 2.0:
        cr_s = 0
    elif cr > 1.5:
        cr_s = 1
    elif cr > 1.0:
        cr_s = 3
    else:
        cr_s = 5

    total = min(35, de_s + fcf_s + cr_s)

    # Debt label
    if de_ratio is None:
        debt_label = "Unknown"
    elif de_ratio < 0.2:
        debt_label = "Debt-Free"
    elif de_ratio < 0.5:
        debt_label = "Low Debt"
    elif de_ratio < 1.0:
        debt_label = "Moderate Debt"
    elif de_ratio < 2.0:
        debt_label = "High Debt"
    else:
        debt_label = "Dangerous Debt"

    fcf_label = ("Strong +FCF" if fcf > 0 else "Negative FCF") if fcf else "Unknown"

    return total, {
        "de_sub":       de_s,
        "fcf_sub":      fcf_s,
        "cr_sub":       cr_s,
        "fcf_yield_pct":round(fcf_yield * 100, 2) if fcf_yield else None,
        "debt_label":   debt_label,
        "fcf_label":    fcf_label,
        "summary": f"D/E {_fmt(de_ratio,'x')} · FCF {_fmt_currency(fcf)} · {fcf_label}",
    }


def _score_growth(rev_growth, earn_growth, eps_trail, eps_fwd) -> tuple[float, dict]:
    """Returns score 0–30 (higher = riskier)."""

    # Revenue growth (0–15)
    rg = (rev_growth or 0)
    if rg > 0.25:
        rg_s = 0
    elif rg > 0.15:
        rg_s = 2
    elif rg > 0.08:
        rg_s = 5
    elif rg > 0.03:
        rg_s = 8
    elif rg > 0:
        rg_s = 11
    else:
        rg_s = 15

    # Earnings/profit growth (0–15)
    eg = (earn_growth or 0)
    if eg > 0.25:
        eg_s = 0
    elif eg > 0.15:
        eg_s = 2
    elif eg > 0.08:
        eg_s = 5
    elif eg > 0:
        eg_s = 8
    elif eg > -0.10:
        eg_s = 11
    else:
        eg_s = 15

    total = min(30, rg_s + eg_s)

    # EPS trend
    eps_trend = None
    if eps_trail and eps_fwd:
        eps_trend = round((eps_fwd - eps_trail) / abs(eps_trail) * 100, 1) if eps_trail != 0 else 0

    label = ("High Growth" if total < 8 else
             "Moderate Growth" if total < 16 else
             "Slow Growth" if total < 23 else "Declining")

    return total, {
        "rev_sub":        rg_s,
        "earn_sub":       eg_s,
        "eps_trend_pct":  eps_trend,
        "label":          label,
        "summary": f"Revenue {_pct(rev_growth)} · Earnings {_pct(earn_growth)}",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Quarterly financials
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_quarterly(ticker) -> list[dict]:
    quarters = []
    try:
        fin = ticker.quarterly_income_stmt
        if fin is not None and not fin.empty:
            cols = fin.columns[:4]
            for col in cols:
                rev    = fin.loc["Total Revenue",         col] if "Total Revenue"         in fin.index else None
                profit = fin.loc["Net Income",            col] if "Net Income"            in fin.index else None
                gross  = fin.loc["Gross Profit",          col] if "Gross Profit"          in fin.index else None
                ebitda = fin.loc["EBITDA",                col] if "EBITDA"                in fin.index else None

                gm  = round(gross / rev * 100, 1)  if (gross and rev)  else None
                npm = round(profit / rev * 100, 1) if (profit and rev) else None

                quarters.append({
                    "quarter":     str(col.date()) if hasattr(col, "date") else str(col),
                    "revenue":     _safe_int(rev),
                    "net_profit":  _safe_int(profit),
                    "gross_margin":gm,
                    "net_margin":  npm,
                    "ebitda":      _safe_int(ebitda),
                })
    except Exception as e:
        logger.debug("Quarterly fetch failed: %s", e)
    return quarters


# ══════════════════════════════════════════════════════════════════════════════
# 12-month price history
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_price_history(ticker) -> dict:
    try:
        hist = ticker.history(period="1y")
        if hist.empty:
            return {}
        # Downsample to ~60 points for the chart
        step = max(1, len(hist) // 60)
        hist = hist.iloc[::step]
        return {
            "dates":  [str(d.date()) for d in hist.index],
            "close":  hist["Close"].round(2).tolist(),
            "volume": hist["Volume"].tolist(),
            "high_52w": round(float(hist["Close"].max()), 2),
            "low_52w":  round(float(hist["Close"].min()), 2),
        }
    except Exception as e:
        logger.debug("Price history failed: %s", e)
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# Catalysts & Risks
# ══════════════════════════════════════════════════════════════════════════════

def _derive_catalysts(metrics: dict, scoring: dict) -> list[str]:
    cats = []
    rg  = metrics["revenue_growth"] or 0
    pg  = metrics["profit_growth"]  or 0
    roe = metrics["roe"]            or 0
    de  = metrics["debt_equity"]    or 1
    fcf = metrics["fcf"]            or 0
    pe  = metrics["pe_ratio"]       or 99
    div = metrics["dividend_yield"] or 0

    if rg > 10:
        cats.append(f"Strong revenue growth of {rg:.1f}% YoY — compounding at above-market rate")
    if pg > 15:
        cats.append(f"Profit expansion {pg:.1f}% — operating leverage driving margin improvement")
    if roe > 20:
        cats.append(f"High ROE of {roe:.1f}% — management generating exceptional returns on equity")
    if (de or 99) < 0.3:
        cats.append("Debt-free / near-zero leverage — full capital flexibility for buybacks or expansion")
    if fcf > 0:
        cats.append(f"Positive free cash flow — business is self-funding with no external capital needed")
    if scoring["total"] < 35:
        cats.append("Attractive overall valuation vs risk profile — margin of safety is present")
    if pe and 0 < pe < 20:
        cats.append(f"P/E of {pe}× is below market average — potential re-rating upside")
    if div > 2:
        cats.append(f"Dividend yield of {div:.1f}% provides floor support and income component")
    if rg > 0 and pg > 0:
        cats.append("Both revenue and profit growing simultaneously — healthy operating model")

    return cats[:6]


def _derive_risks(metrics: dict, scoring: dict, info: dict) -> list[str]:
    risks = []
    rg  = metrics["revenue_growth"] or 0
    pg  = metrics["profit_growth"]  or 0
    de  = metrics["debt_equity"]
    fcf = metrics["fcf"]            or 0
    pe  = metrics["pe_ratio"]
    ev  = metrics["ev_ebitda"]
    tot = scoring["total"]

    if pe and pe > 45:
        risks.append(f"P/E of {pe}× prices in perfection — any earnings miss triggers sharp correction")
    if ev and ev > 20:
        risks.append(f"EV/EBITDA of {ev}× implies elevated growth expectations — valuation risk high")
    if de and de > 1.2:
        risks.append(f"Debt/Equity of {de:.1f}x — high leverage amplifies downside in rate-rising environment")
    if fcf < 0:
        risks.append("Negative free cash flow — company burning cash; may need equity dilution")
    if rg < 0:
        risks.append(f"Revenue declining {abs(rg):.1f}% — top-line contraction is a structural concern")
    if pg < -10:
        risks.append(f"Profit falling {abs(pg):.1f}% — margin compression or one-off charges possible")
    if tot > 65:
        risks.append("Composite risk score is HIGH — consider position sizing carefully")
    if info.get("beta", 1) and info["beta"] > 1.5:
        b = info["beta"]
        risks.append(f"Beta {b:.2f} — highly volatile; drawdowns of 30–50% possible in bear market")
    if not info.get("freeCashflow"):
        risks.append("Free cash flow data unavailable — opacity in cash generation quality")

    return risks[:6]


# ══════════════════════════════════════════════════════════════════════════════
# Final Verdict
# ══════════════════════════════════════════════════════════════════════════════

def _final_verdict(total_score: float, metrics: dict) -> dict:
    rg = metrics["revenue_growth"] or 0
    pg = metrics["profit_growth"]  or 0

    if total_score < 20 and rg > 0 and pg > 0:
        rating = "STRONG BUY"
        color  = "green"
        reason = "Low risk + positive growth + attractive valuation — high conviction long"
    elif total_score < 35:
        rating = "BUY"
        color  = "green"
        reason = "Fundamentals are solid; risk-reward is favourable at current price"
    elif total_score < 55:
        rating = "NEUTRAL"
        color  = "amber"
        reason = "Mixed signals — wait for better entry or earnings clarity before adding"
    elif total_score < 70:
        rating = "SELL"
        color  = "red"
        reason = "Risk factors outweigh catalysts — reduce position or avoid new entry"
    else:
        rating = "STRONG SELL"
        color  = "red"
        reason = "High composite risk — high valuation + weak financials + slowing growth"

    return {
        "rating": rating,
        "color":  color,
        "reason": reason,
        "score":  total_score,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _val(d: dict, *keys) -> Any:
    for k in keys:
        v = d.get(k)
        if v is not None and v == v:   # also catches NaN
            try:
                f = float(v)
                if not (f != f):       # NaN check
                    return f
            except (TypeError, ValueError):
                pass
    return None


def _safe_round(v, decimals=2):
    try:
        return round(float(v), decimals) if v is not None else None
    except Exception:
        return None


def _safe_int(v):
    try:
        return int(v) if v is not None else None
    except Exception:
        return None


def _fmt(v, suffix=""):
    if v is None:
        return "N/A"
    return f"{v:.1f}{suffix}"


def _pct(v):
    if v is None:
        return "N/A"
    return f"{v*100:+.1f}%"


def _fmt_currency(v):
    if v is None:
        return "N/A"
    abs_v = abs(v)
    sign  = "-" if v < 0 else ""
    if abs_v >= 1e9:
        return f"{sign}₹{abs_v/1e9:.1f}B"
    if abs_v >= 1e7:
        return f"{sign}₹{abs_v/1e7:.1f}Cr"
    return f"{sign}₹{abs_v/1e5:.1f}L"
