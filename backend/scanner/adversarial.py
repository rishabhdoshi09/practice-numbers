"""
Stage 2: Adversarial Bull vs Bear Research Engine.

For each candidate stock, two sides build independent cases:
  - Bull side: every signal / indicator favouring upside
  - Bear side: every risk / contra-indicator arguing for caution

Net conviction score drives the final verdict.
"""
from __future__ import annotations


def run_adversarial(symbol: str, features: dict, decision: dict, risk: dict) -> dict:
    """
    Build bull and bear cases from quantitative evidence.

    Returns:
        bull_arguments, bear_arguments, scores, verdict
    """
    signals    = features["signals"]
    indicators = features["indicators"]
    exp_ret    = features.get("expected_return", {})

    bull_args: list[dict] = []
    bear_args: list[dict] = []
    bull_score = 0.0
    bear_score = 0.0

    def _bull(text: str, weight: float):
        bull_args.append({"arg": text, "weight": round(weight, 3)})
        nonlocal bull_score
        bull_score += weight

    def _bear(text: str, weight: float):
        bear_args.append({"arg": text, "weight": round(weight, 3)})
        nonlocal bear_score
        bear_score += weight

    # ── Trend signal ──────────────────────────────────────────────────────────
    trend = signals["trend"]
    if trend > 0.45:
        _bull(f"Strong uptrend — price well above all EMAs (trend {trend:+.2f})", trend)
    elif trend > 0.15:
        _bull(f"Positive trend — price above short-term moving averages", trend)
    elif trend < -0.45:
        _bear(f"Strong downtrend — price below all EMAs (trend {trend:+.2f})", abs(trend))
    elif trend < -0.15:
        _bear(f"Negative trend — price below key moving averages", abs(trend))

    # ── Momentum (RSI + MACD) ─────────────────────────────────────────────────
    mom  = signals["momentum"]
    rsi  = indicators["rsi"]
    macd = indicators["macd_hist"]

    if mom > 0.30:
        _bull(f"Strong momentum — MACD histogram positive, RSI healthy at {rsi:.0f}", mom)
    elif mom > 0.10:
        _bull(f"Improving momentum — MACD turning positive", mom)
    elif mom < -0.30:
        _bear(f"Momentum fading — MACD bearish, RSI at {rsi:.0f}", abs(mom))
    elif mom < -0.10:
        _bear(f"Weakening momentum — MACD histogram turning negative", abs(mom))

    if rsi > 72:
        _bear(f"RSI overbought at {rsi:.0f} — short-term exhaustion risk, pullback probable", 0.35)
    elif rsi < 30:
        _bull(f"RSI oversold at {rsi:.0f} — statistical bounce likely, mean reversion opportunity", 0.35)

    # ── Bollinger bands ───────────────────────────────────────────────────────
    pct_b = indicators.get("bb_pct_b", 0.5)
    if pct_b > 0.90:
        _bear(f"Price near upper Bollinger Band (B% = {pct_b:.2f}) — breakout or reversal inflection", 0.20)
    elif pct_b < 0.10:
        _bull(f"Price near lower Bollinger Band (B% = {pct_b:.2f}) — compressed; upside coil forming", 0.20)

    # ── ML ensemble ──────────────────────────────────────────────────────────
    ml = signals["ml"]
    if ml > 0.25:
        prob_up = round((0.5 + ml / 2) * 100)
        _bull(f"ML ensemble (RandomForest + LogReg) assigns {prob_up}% upside probability", ml)
    elif ml > 0.10:
        _bull(f"ML models lean bullish — slight positive edge", ml)
    elif ml < -0.25:
        prob_dn = round((0.5 + abs(ml) / 2) * 100)
        _bear(f"ML ensemble assigns {prob_dn}% downside probability — models are bearish", abs(ml))
    elif ml < -0.10:
        _bear(f"ML models lean bearish", abs(ml))

    # ── ARIMA forecast ────────────────────────────────────────────────────────
    arima = signals["arima"]
    if arima > 0.15:
        _bull(f"ARIMA(2,1,2) projects price appreciation over next 5 sessions", arima * 0.8)
    elif arima < -0.15:
        _bear(f"ARIMA projects price decline over next 5 sessions", abs(arima) * 0.8)

    # ── GBM Monte Carlo ───────────────────────────────────────────────────────
    gbm = signals["gbm"]
    if gbm > 0.20:
        _bull(f"GBM Monte Carlo (1000 sims) shows majority of paths end higher", gbm * 0.6)
    elif gbm < -0.20:
        _bear(f"GBM simulations show majority of paths end lower", abs(gbm) * 0.6)

    # ── News Sentiment ────────────────────────────────────────────────────────
    sent = signals["sentiment"]
    if sent > 0.15:
        _bull(f"Positive news sentiment — recent headlines signal improving fundamentals", sent * 0.7)
    elif sent < -0.15:
        _bear(f"Negative news flow — headline risk present; sentiment is cautious", abs(sent) * 0.7)

    # ── Mean reversion ────────────────────────────────────────────────────────
    mr = signals["mean_revert"]
    if mr > 0.35:
        _bull(f"Price is statistically oversold vs 20-day mean — reversion bounce favoured", mr * 0.5)
    elif mr < -0.35:
        _bear(f"Price is extended above 20-day mean — pullback / mean reversion risk", abs(mr) * 0.5)

    # ── GARCH volatility ──────────────────────────────────────────────────────
    vol_sig = signals["volatility"]
    if vol_sig < -0.35:
        _bear(f"GARCH(1,1) detects elevated volatility regime — tail risk is rising", abs(vol_sig) * 0.45)

    # ── Expected return (historical alpha) ────────────────────────────────────
    ann_ret = exp_ret.get("annual_return", 0)
    sharpe  = exp_ret.get("sharpe_ratio", 0)
    if ann_ret > 0.18:
        _bull(f"Historical annual return {ann_ret*100:.1f}% with Sharpe {sharpe:.2f} — proven alpha", 0.25)
    elif ann_ret > 0.08:
        _bull(f"Positive historical alpha ({ann_ret*100:.1f}% annual return)", 0.15)
    elif ann_ret < -0.05:
        _bear(f"Negative historical return ({ann_ret*100:.1f}%) — chronic underperformer", 0.20)

    # ── VaR tail risk ─────────────────────────────────────────────────────────
    var_95 = risk.get("var", {}).get("var_95_pct", 0)
    if abs(var_95) > 4.5:
        _bear(f"VaR 95% = {var_95:.1f}% daily — significant tail risk; position sizing critical", 0.30)

    # ── Net conviction ────────────────────────────────────────────────────────
    net = bull_score - bear_score
    total = bull_score + bear_score + 1e-10
    bull_pct = round(bull_score / total * 100, 1)
    bear_pct = round(100 - bull_pct, 1)

    if net > 0.55:
        verdict = "STRONG BUY"
    elif net > 0.20:
        verdict = "BUY"
    elif net > -0.20:
        verdict = "NEUTRAL"
    elif net > -0.55:
        verdict = "SELL"
    else:
        verdict = "STRONG SELL"

    return {
        "bull_score":     round(bull_score, 3),
        "bear_score":     round(bear_score, 3),
        "bull_pct":       bull_pct,
        "bear_pct":       bear_pct,
        "net_conviction": round(net, 3),
        "verdict":        verdict,
        "bull_arguments": sorted(bull_args, key=lambda x: -x["weight"])[:6],
        "bear_arguments": sorted(bear_args, key=lambda x: -x["weight"])[:6],
    }
