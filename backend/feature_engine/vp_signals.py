"""
Volume Profile Signal Generator.

Rules:
  LONG  — price enters LVN from below with bullish momentum + volume expansion
  SHORT — price enters LVN from above with bearish momentum + volume expansion
  MEAN REVERSION LONG  — price > 3% below POC in an uptrend
  MEAN REVERSION SHORT — price > 3% above POC in a downtrend
  HOLD  — price inside dense HVN (choppy) or no setup present

Each signal carries:
  entry, stop_loss, target_1, target_2, confidence (0–1), risk_reward
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .volume_profile import VolumeProfile


# ── Tuneable parameters ────────────────────────────────────────────────────────
VOL_EXPANSION_MULT  = 1.3    # current vol must be >1.3× 20-bar average
LVN_PROXIMITY_PCT   = 0.012  # price within 1.2% of LVN → "entering LVN"
HVN_PROXIMITY_PCT   = 0.015  # price within 1.5% of HVN → "inside HVN"
POC_DEVIATION_PCT   = 0.030  # 3% from POC → mean reversion trigger
SL_BUFFER_BINS      = 2      # stop is placed N bins beyond the LVN
MIN_RR              = 1.5    # minimum risk/reward to emit a signal
TREND_EMA_PERIOD    = 50


def generate_vp_signals(df: pd.DataFrame, vp: VolumeProfile) -> list[dict]:
    """
    Generate actionable trading signals from the volume profile.

    Returns a list of signal dicts sorted by confidence descending.
    Always returns at least one HOLD signal if no trade setup found.
    """
    signals: list[dict] = []
    price  = float(df["Close"].iloc[-1])
    open_  = float(df["Open"].iloc[-1])

    # ── Market context ─────────────────────────────────────────────────────
    ema50      = float(df["Close"].ewm(span=TREND_EMA_PERIOD, adjust=False).mean().iloc[-1])
    in_uptrend = price > ema50
    avg_vol    = float(df["Volume"].rolling(20).mean().iloc[-1])
    cur_vol    = float(df["Volume"].iloc[-1])
    vol_exp    = cur_vol > avg_vol * VOL_EXPANSION_MULT
    vol_ratio  = cur_vol / (avg_vol + 1e-10)

    bullish_candle = price > open_
    bearish_candle = price < open_
    candle_body_pct = abs(price - open_) / (open_ + 1e-10)

    # POC deviation
    poc_dev = (price - vp.poc) / (vp.poc + 1e-10)

    # ── 1. BREAKOUT through LVN (momentum trade) ──────────────────────────
    lvn_above = vp.nearest_lvn_above(price)
    lvn_below = vp.nearest_lvn_below(price)

    # LONG: price just broke into LVN from below
    if lvn_above is not None:
        dist_pct = abs(price - lvn_above) / lvn_above
        if dist_pct < LVN_PROXIMITY_PCT and bullish_candle and vol_exp:
            hvn_target = vp.nearest_hvn_above(lvn_above)
            target1    = hvn_target if hvn_target else vp.vah
            target2    = vp.vah if target1 < vp.vah else vp.vah * 1.01
            sl         = lvn_above - vp.bin_size * SL_BUFFER_BINS
            rr         = _rr(price, target1, sl)
            conf       = _confidence("LVN_LONG", vol_ratio, in_uptrend,
                                     dist_pct, candle_body_pct, rr)
            if rr >= MIN_RR and conf >= 0.30:
                signals.append(_signal(
                    action="LONG",
                    entry=price, sl=sl, t1=target1, t2=target2, rr=rr,
                    confidence=conf, vol_ratio=vol_ratio,
                    reason=f"Price entering LVN {lvn_above:.1f} from below — "
                           f"breakout with {vol_ratio:.1f}× volume. "
                           f"Target: HVN {target1:.1f}",
                    setup="LVN Breakout Long",
                ))

    # SHORT: price just broke into LVN from above
    if lvn_below is not None:
        dist_pct = abs(price - lvn_below) / lvn_below
        if dist_pct < LVN_PROXIMITY_PCT and bearish_candle and vol_exp:
            hvn_target = vp.nearest_hvn_below(lvn_below)
            target1    = hvn_target if hvn_target else vp.val
            target2    = vp.val if target1 > vp.val else vp.val * 0.99
            sl         = lvn_below + vp.bin_size * SL_BUFFER_BINS
            rr         = _rr(price, target1, sl, short=True)
            conf       = _confidence("LVN_SHORT", vol_ratio, not in_uptrend,
                                     dist_pct, candle_body_pct, rr)
            if rr >= MIN_RR and conf >= 0.30:
                signals.append(_signal(
                    action="SHORT",
                    entry=price, sl=sl, t1=target1, t2=target2, rr=rr,
                    confidence=conf, vol_ratio=vol_ratio,
                    reason=f"Price entering LVN {lvn_below:.1f} from above — "
                           f"breakdown with {vol_ratio:.1f}× volume. "
                           f"Target: HVN {target1:.1f}",
                    setup="LVN Breakdown Short",
                ))

    # ── 2. Value Area breakout ────────────────────────────────────────────
    # Price just cleared VAH with expansion → targeting next HVN
    if price > vp.vah and (price - vp.vah) / vp.vah < 0.015 and bullish_candle and vol_exp:
        hvn_t = vp.nearest_hvn_above(vp.vah)
        target1 = hvn_t if hvn_t else vp.vah * 1.03
        sl      = vp.vah - vp.bin_size
        rr      = _rr(price, target1, sl)
        conf    = _confidence("VA_BREAK_LONG", vol_ratio, in_uptrend,
                              0.01, candle_body_pct, rr)
        if rr >= MIN_RR:
            signals.append(_signal(
                action="LONG",
                entry=price, sl=sl, t1=target1, t2=target1 * 1.02, rr=rr,
                confidence=conf, vol_ratio=vol_ratio,
                reason=f"Value Area Breakout above VAH {vp.vah:.1f} — "
                       f"expect acceleration into next HVN",
                setup="VAH Breakout",
            ))

    # Price just broke below VAL
    if price < vp.val and (vp.val - price) / vp.val < 0.015 and bearish_candle and vol_exp:
        hvn_t = vp.nearest_hvn_below(vp.val)
        target1 = hvn_t if hvn_t else vp.val * 0.97
        sl      = vp.val + vp.bin_size
        rr      = _rr(price, target1, sl, short=True)
        conf    = _confidence("VA_BREAK_SHORT", vol_ratio, not in_uptrend,
                              0.01, candle_body_pct, rr)
        if rr >= MIN_RR:
            signals.append(_signal(
                action="SHORT",
                entry=price, sl=sl, t1=target1, t2=target1 * 0.98, rr=rr,
                confidence=conf, vol_ratio=vol_ratio,
                reason=f"Value Area Breakdown below VAL {vp.val:.1f} — "
                       f"expect acceleration into next HVN",
                setup="VAL Breakdown",
            ))

    # ── 3. Mean Reversion back to POC ─────────────────────────────────────
    if poc_dev < -POC_DEVIATION_PCT and in_uptrend:
        sl      = price * (1 - 0.015)
        target1 = vp.poc
        target2 = vp.vah
        rr      = _rr(price, target1, sl)
        conf    = _confidence("MEAN_REV_LONG", vol_ratio, in_uptrend,
                              abs(poc_dev), candle_body_pct, rr) * 0.85
        if rr >= 1.2:
            signals.append(_signal(
                action="LONG",
                entry=price, sl=sl, t1=target1, t2=target2, rr=rr,
                confidence=conf, vol_ratio=vol_ratio,
                reason=f"Price {abs(poc_dev)*100:.1f}% below POC {vp.poc:.1f} "
                       f"in uptrend — mean reversion to POC expected",
                setup="Mean Reversion Long",
            ))

    if poc_dev > POC_DEVIATION_PCT and not in_uptrend:
        sl      = price * (1 + 0.015)
        target1 = vp.poc
        target2 = vp.val
        rr      = _rr(price, target1, sl, short=True)
        conf    = _confidence("MEAN_REV_SHORT", vol_ratio, not in_uptrend,
                              abs(poc_dev), candle_body_pct, rr) * 0.85
        if rr >= 1.2:
            signals.append(_signal(
                action="SHORT",
                entry=price, sl=sl, t1=target1, t2=target2, rr=rr,
                confidence=conf, vol_ratio=vol_ratio,
                reason=f"Price {poc_dev*100:.1f}% above POC {vp.poc:.1f} "
                       f"in downtrend — mean reversion to POC expected",
                setup="Mean Reversion Short",
            ))

    # ── 4. HVN Rejection (fade from HVN towards POC) ─────────────────────
    hvn_near = vp.nearest_hvn_above(price - 0.001)
    if hvn_near and abs(price - hvn_near) / hvn_near < HVN_PROXIMITY_PCT:
        # Price is at HVN — if bearish candle, fade back towards POC
        if bearish_candle and poc_dev > 0.01:
            sl      = hvn_near + vp.bin_size * 1.5
            target1 = vp.poc
            rr      = _rr(price, target1, sl, short=True)
            if rr >= 1.5:
                signals.append(_signal(
                    action="SHORT",
                    entry=price, sl=sl, t1=target1, t2=vp.val, rr=rr,
                    confidence=0.45, vol_ratio=vol_ratio,
                    reason=f"HVN Rejection at {hvn_near:.1f} — "
                           f"price accepted here before; mean reversion to POC",
                    setup="HVN Rejection Short",
                ))

    # ── Filter out trades inside dense HVN (choppy) ───────────────────────
    signals = [s for s in signals if not vp.in_hvn(s["entry"], tolerance=0.005)]

    # ── Sort by confidence ────────────────────────────────────────────────
    signals.sort(key=lambda x: -x["confidence"])

    # ── HOLD fallback ─────────────────────────────────────────────────────
    if not signals:
        zone    = vp.price_zone(price)
        poc_gap = poc_dev * 100

        if vp.in_hvn(price, tolerance=HVN_PROXIMITY_PCT):
            reason = f"Price inside HVN — avoid trading in choppy acceptance zone"
        elif zone == "INSIDE_VA":
            reason = f"Price inside Value Area ({vp.val:.1f}–{vp.vah:.1f}) — no edge"
        elif zone == "ABOVE_VA":
            reason = f"Above VAH {vp.vah:.1f}; POC {poc_gap:+.1f}% away — wait for LVN or VA test"
        else:
            reason = f"Below VAL {vp.val:.1f}; POC {poc_gap:+.1f}% away — wait for LVN or VA test"

        signals.append({
            "action":      "HOLD",
            "setup":       "No Setup",
            "entry":       round(price, 2),
            "stop_loss":   None,
            "target_1":    None,
            "target_2":    None,
            "risk_reward": None,
            "confidence":  0.0,
            "vol_ratio":   round(vol_ratio, 2),
            "reason":      reason,
            "context": {
                "poc": round(vp.poc, 2), "vah": round(vp.vah, 2),
                "val": round(vp.val, 2), "zone": zone,
                "ema50": round(ema50, 2), "trend": "UP" if in_uptrend else "DOWN",
            },
        })
    else:
        # Add context to all emitted signals
        for s in signals:
            s["context"] = {
                "poc": round(vp.poc, 2), "vah": round(vp.vah, 2),
                "val": round(vp.val, 2), "zone": vp.price_zone(price),
                "ema50": round(ema50, 2), "trend": "UP" if in_uptrend else "DOWN",
            }

    return signals


# ── Signal builder helpers ─────────────────────────────────────────────────────

def _signal(*, action, entry, sl, t1, t2, rr, confidence, vol_ratio, reason, setup) -> dict:
    return {
        "action":      action,
        "setup":       setup,
        "entry":       round(entry, 2),
        "stop_loss":   round(sl,    2),
        "target_1":    round(t1,    2),
        "target_2":    round(t2,    2),
        "risk_reward": round(rr,    2),
        "confidence":  round(min(confidence, 0.95), 3),
        "vol_ratio":   round(vol_ratio,      2),
        "reason":      reason,
        "context":     {},
    }


def _rr(entry: float, target: float, sl: float, short: bool = False) -> float:
    if short:
        reward = entry - target
        risk   = sl - entry
    else:
        reward = target - entry
        risk   = entry - sl
    if risk <= 0:
        return 0.0
    return round(abs(reward) / abs(risk), 2)


def _confidence(
    signal_type: str,
    vol_ratio:   float,
    trend_ok:    bool,
    prox:        float,
    body_pct:    float,
    rr:          float,
) -> float:
    score = 0.0

    # Volume expansion (max 0.30)
    score += min(0.30, (vol_ratio - 1.0) * 0.20)

    # Trend alignment (0.20)
    if trend_ok:
        score += 0.20

    # Price proximity to level (tighter = better, max 0.20)
    score += max(0, 0.20 - prox * 10)

    # Strong candle body (max 0.15)
    score += min(0.15, body_pct * 10)

    # Risk/reward quality (max 0.15)
    score += min(0.15, (rr - 1.0) * 0.05) if rr > 1 else 0

    return round(min(0.95, max(0.0, score)), 3)
