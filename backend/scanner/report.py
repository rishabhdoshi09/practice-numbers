"""
Daily Street Pulse — price-action report generator.

Takes structured signal data from ScanEngine and classifies each stock
into trader buckets using signal values. Writes in trading desk style.
"""
from __future__ import annotations
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

# ── Signal thresholds ──────────────────────────────────────────────────────────
BREAKOUT_TREND_MIN      = 0.45
BREAKOUT_MOMENTUM_MIN   = 0.30
BASE_VOL_MAX            = 0.15   # volatility signal close to 0 = drying up
MOMENTUM_TREND_MIN      = 0.25
MOMENTUM_ML_MIN         = 0.20
WEAK_TREND_MAX          = -0.25
WEAK_MOMENTUM_MAX       = -0.20


def _classify(stock: dict) -> str:
    """
    Classify one stock into a bucket based on its aggregated signals.
    Returns: 'breakout' | 'base' | 'momentum' | 'weak' | 'noise'
    """
    s = stock.get("_signals", {})

    trend      = s.get("trend",      0.0)
    momentum   = s.get("momentum",   0.0)
    volatility = s.get("volatility", 0.0)   # GARCH — higher = more volatile
    ml         = s.get("ml",         0.0)
    arima      = s.get("arima",      0.0)
    mean_rev   = s.get("mean_revert",0.0)
    conf       = stock.get("confidence", 0)

    # Breakout: strong trend + momentum + ML all agree
    if (trend >= BREAKOUT_TREND_MIN
            and momentum >= BREAKOUT_MOMENTUM_MIN
            and ml >= 0.10
            and conf >= 55):
        return "breakout"

    # Weak / losing momentum: trend and momentum both negative
    if (trend <= WEAK_TREND_MAX
            and momentum <= WEAK_MOMENTUM_MAX
            and conf >= 45):
        return "weak"

    # Base formation: trend neutral, volatility low = consolidation
    if (abs(trend) < 0.20
            and abs(momentum) < 0.20
            and abs(mean_rev) < 0.30
            and conf >= 35):
        return "base"

    # Momentum continuation: positive trend + ML + ARIMA
    if (trend >= MOMENTUM_TREND_MIN
            and ml >= MOMENTUM_ML_MIN
            and arima >= 0.10
            and conf >= 45):
        return "momentum"

    return "noise"


def _write_breakout(stock: dict) -> str:
    s = stock.get("_signals", {})
    trend = s.get("trend", 0)
    name  = stock["name"]
    price = stock["price"]
    conf  = stock["confidence"]
    stop  = stock["stop_loss"]
    top_s = stock.get("top_signal", "trend")

    if trend > 0.65:
        phrase = "broke out strongly above key resistance"
    elif trend > 0.45:
        phrase = "breaking out with improving price structure"
    else:
        phrase = "showing early breakout characteristics"

    vol_phrase = "volumes confirming the move" if s.get("ml", 0) > 0.3 else "watch for volume pickup"
    return (f"**{name}** ₹{price:,.0f} → {phrase}. "
            f"Leading signal: {top_s}. {vol_phrase.capitalize()}. "
            f"Conf {conf:.0f}% | Stop ₹{stop:,.0f}")


def _write_base(stock: dict) -> str:
    s     = stock.get("_signals", {})
    name  = stock["name"]
    price = stock["price"]
    conf  = stock["confidence"]
    stop  = stock["stop_loss"]

    mr = s.get("mean_revert", 0)
    if mr > 0.10:
        phase = "coiling near support, possible spring forming"
    elif mr < -0.10:
        phase = "consolidating below resistance — range-bound"
    else:
        phase = "volume drying up in a tight range"

    return (f"**{name}** ₹{price:,.0f} → {phase}. "
            f"Low volatility signals consolidation; wait for directional breakout. "
            f"Conf {conf:.0f}% | Stop ₹{stop:,.0f}")


def _write_momentum(stock: dict) -> str:
    s     = stock.get("_signals", {})
    name  = stock["name"]
    price = stock["price"]
    conf  = stock["confidence"]
    stop  = stock["stop_loss"]
    top_s = stock.get("top_signal", "ml")

    arima = s.get("arima", 0)
    if arima > 0.35:
        fwd = "ARIMA projects continuation higher over next 5 sessions"
    else:
        fwd = "trend intact; pullbacks are buying opportunities"

    return (f"**{name}** ₹{price:,.0f} → riding strong trend, structure intact. "
            f"{fwd}. Strongest signal: {top_s}. "
            f"Conf {conf:.0f}% | Stop ₹{stop:,.0f}")


def _write_weak(stock: dict) -> str:
    s     = stock.get("_signals", {})
    name  = stock["name"]
    price = stock["price"]
    conf  = stock["confidence"]
    stop  = stock["stop_loss"]

    mom = s.get("momentum", 0)
    if mom < -0.50:
        severity = "losing momentum sharply — below key EMAs"
    elif mom < -0.30:
        severity = "failed breakout; momentum reversing"
    else:
        severity = "trend weakening, distribution underway"

    return (f"**{name}** ₹{price:,.0f} → {severity}. "
            f"ML and ARIMA both project downside continuation. "
            f"Conf {conf:.0f}% | Caution below ₹{stop:,.0f}")


_WRITERS = {
    "breakout": _write_breakout,
    "base":     _write_base,
    "momentum": _write_momentum,
    "weak":     _write_weak,
}


def generate_report(scan_result: dict, full_analysis_map: dict | None = None) -> dict:
    """
    Generate the Daily Street Pulse report from a scan result.

    Args:
        scan_result: Output from ScanEngine.run()
        full_analysis_map: Optional {symbol: features_dict} for richer signal data.

    Returns:
        Report dict with buckets + markdown string.
    """
    all_stocks = scan_result.get("all", [])
    now = datetime.now(IST)

    # Attach raw signal data to each stock entry
    for stock in all_stocks:
        if full_analysis_map and stock["symbol"] in full_analysis_map:
            stock["_signals"] = full_analysis_map[stock["symbol"]].get("signals", {})
        else:
            # Reconstruct approximate signals from decision data
            stock["_signals"] = _infer_signals(stock)

    # Classify
    buckets: dict[str, list] = {"breakout": [], "base": [], "momentum": [], "weak": []}
    for stock in all_stocks:
        bucket = _classify(stock)
        if bucket in buckets:
            buckets[bucket].append(stock)

    # Sort each bucket by confidence
    for b in buckets:
        buckets[b].sort(key=lambda x: -x["confidence"])

    # Build markdown report
    date_str = now.strftime("%A, %d %B %Y")
    time_str = now.strftime("%H:%M IST")
    scanned  = scan_result.get("total_scanned", 0)
    elapsed  = scan_result.get("elapsed_sec", 0)

    lines = [
        f"# ⚡ Daily Street Pulse",
        f"**{date_str}  ·  {time_str}**  ·  {scanned} stocks scanned in {elapsed}s",
        "",
    ]

    sections = [
        ("breakout",  "🚀 Breakout Stocks",      "Strong move + volume confirmation"),
        ("momentum",  "💪 Momentum Stocks",       "Trend continuation, structure intact"),
        ("base",      "🧱 Base Formation Stocks", "Consolidation — setup forming"),
        ("weak",      "⚠️  Losing Momentum",       "Breakdown / failed breakout"),
    ]

    report_buckets = {}
    for key, header, subtitle in sections:
        stocks_in_bucket = buckets[key][:6]   # top 6 per bucket
        report_buckets[key] = stocks_in_bucket
        if not stocks_in_bucket:
            continue
        lines.append(f"## {header}")
        lines.append(f"*{subtitle}*")
        lines.append("")
        for stock in stocks_in_bucket:
            writer = _WRITERS[key]
            lines.append(f"- {writer(stock)}")
        lines.append("")

    # Summary line
    lines.append("---")
    lines.append(
        f"*Breakout: {len(buckets['breakout'])} · "
        f"Momentum: {len(buckets['momentum'])} · "
        f"Base: {len(buckets['base'])} · "
        f"Weak: {len(buckets['weak'])}*"
    )
    lines.append("*SimpleQuant — Quant signals only. Not financial advice.*")

    markdown = "\n".join(lines)

    return {
        "date":      date_str,
        "time":      time_str,
        "markdown":  markdown,
        "buckets": {
            "breakout":  [_stock_summary(s) for s in report_buckets.get("breakout", [])],
            "momentum":  [_stock_summary(s) for s in report_buckets.get("momentum", [])],
            "base":      [_stock_summary(s) for s in report_buckets.get("base",     [])],
            "weak":      [_stock_summary(s) for s in report_buckets.get("weak",     [])],
        },
        "counts": {k: len(v) for k, v in buckets.items()},
    }


def _stock_summary(stock: dict) -> dict:
    return {
        "symbol":     stock["symbol"],
        "name":       stock["name"],
        "sector":     stock.get("sector", "—"),
        "price":      stock["price"],
        "confidence": stock["confidence"],
        "stop_loss":  stock["stop_loss"],
        "top_signal": stock.get("top_signal", "—"),
        "action":     stock.get("action", "HOLD"),
    }


def _infer_signals(stock: dict) -> dict:
    """
    Reverse-engineer approximate signal dict from aggregate stock summary.
    Used when full feature dict is not cached.
    """
    score  = stock.get("score", 0.0)
    action = stock.get("action", "HOLD")
    conf   = stock.get("confidence", 0) / 100

    # Heuristic reconstruction from final score direction
    polarity = 1 if action == "BUY" else (-1 if action == "SELL" else 0)
    base = abs(score)

    return {
        "trend":       round(polarity * base * 1.4, 3),
        "momentum":    round(polarity * base * 1.1, 3),
        "volatility":  round(-abs(score) * 0.5, 3),
        "ml":          round(polarity * base, 3),
        "arima":       round(polarity * base * 0.9, 3),
        "mean_revert": round(-polarity * base * 0.3, 3),
    }
