"""
Stage 5: Ongoing Rebalancing Engine.

Compares the currently-built portfolio against the latest scan results and
recommends one of four actions for each position:

  HOLD   — signal intact, conviction still strong
  SELL   — signal has degraded to SELL with >= 55% confidence
  SWAP   — conviction dropped >20 pts; a higher-rated replacement exists
  ADD    — new high-conviction BUY not yet in the portfolio
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

SELL_THRESHOLD_CONF   = 55     # min confidence to trigger a SELL recommendation
SWAP_DROP_THRESHOLD   = 20     # confidence drop (pts) that triggers a swap search
SWAP_MIN_IMPROVEMENT  = 15     # new stock must be this many pts better to qualify
ADD_MIN_CONFIDENCE    = 60     # min confidence for a new ADD recommendation


def generate_rebalance_plan(current_portfolio: dict, scan_result: dict) -> dict:
    """
    Produce a full rebalancing plan.

    Args:
        current_portfolio: dict from ExecutionEngine.portfolio_summary() or
                           portfolio_builder.build_portfolio()
        scan_result:       latest ScanEngine.run() output

    Returns:
        holds, sells, swaps, new_adds, summary
    """
    positions = current_portfolio.get("positions", [])
    all_scanned = {s["symbol"]: s for s in scan_result.get("all", [])}
    top_buys    = scan_result.get("top_buys", [])

    holds: list[dict] = []
    sells: list[dict] = []
    swaps: list[dict] = []

    current_syms = {p["symbol"] for p in positions}

    for pos in positions:
        sym      = pos["symbol"]
        new_data = all_scanned.get(sym)

        if not new_data:
            holds.append({**pos, "reason": "Not in scan universe — hold unchanged"})
            continue

        new_action = new_data.get("action", "HOLD")
        new_conf   = new_data.get("confidence", 0)
        old_conf   = pos.get("confidence", 0)
        conf_delta = old_conf - new_conf

        # ── SELL: signal has clearly degraded ────────────────────────────────
        if new_action == "SELL" and new_conf >= SELL_THRESHOLD_CONF:
            sells.append({
                **pos,
                "new_action":     new_action,
                "new_confidence": new_conf,
                "conf_delta":     round(conf_delta, 1),
                "reason": (
                    f"Signal flipped to SELL ({new_conf:.0f}% confidence). "
                    "Exit position and reallocate capital."
                ),
            })

        # ── SWAP: conviction dropped, better opportunity exists ───────────────
        elif conf_delta > SWAP_DROP_THRESHOLD:
            replacements = [
                s for s in top_buys
                if s["symbol"] not in current_syms
                and s.get("confidence", 0) >= new_conf + SWAP_MIN_IMPROVEMENT
            ]
            if replacements:
                rep = replacements[0]
                swaps.append({
                    "sell": {
                        **pos,
                        "new_confidence": new_conf,
                        "conf_delta":     round(conf_delta, 1),
                        "reason": (
                            f"Conviction dropped {conf_delta:.0f} pts "
                            f"(was {old_conf:.0f}%, now {new_conf:.0f}%)"
                        ),
                    },
                    "buy": {
                        "symbol":      rep["symbol"],
                        "name":        rep["name"],
                        "sector":      rep.get("sector", "—"),
                        "action":      rep["action"],
                        "confidence":  rep["confidence"],
                        "price":       rep["price"],
                        "stop_loss":   rep.get("stop_loss", 0),
                        "top_signal":  rep.get("top_signal", "—"),
                    },
                    "rationale": (
                        f"Swap {pos.get('name', sym)} (conf {new_conf:.0f}%) "
                        f"→ {rep['name']} (conf {rep['confidence']:.0f}%, "
                        f"{rep.get('sector','—')})"
                    ),
                    "expected_improvement_pts": round(rep["confidence"] - new_conf, 1),
                })
            else:
                holds.append({
                    **pos,
                    "new_confidence": new_conf,
                    "conf_delta":     round(conf_delta, 1),
                    "reason": (
                        f"Conviction dipped ({conf_delta:.0f} pts) but no better "
                        "replacement found — hold"
                    ),
                })

        # ── HOLD: signal intact ───────────────────────────────────────────────
        else:
            holds.append({
                **pos,
                "new_confidence": new_conf,
                "conf_delta":     round(conf_delta, 1),
                "reason": (
                    f"Signal intact — {new_action} at {new_conf:.0f}% confidence. Hold."
                ),
            })

    # ── New opportunities not yet in portfolio ────────────────────────────────
    new_adds = [
        {
            "symbol":     s["symbol"],
            "name":       s["name"],
            "sector":     s.get("sector", "—"),
            "action":     s["action"],
            "confidence": s["confidence"],
            "price":      s["price"],
            "stop_loss":  s.get("stop_loss", 0),
            "top_signal": s.get("top_signal", "—"),
        }
        for s in top_buys
        if s["symbol"] not in current_syms
        and s.get("confidence", 0) >= ADD_MIN_CONFIDENCE
    ][:5]

    return {
        "holds":            holds,
        "sells":            sells,
        "swaps":            swaps,
        "new_opportunities": new_adds,
        "summary": {
            "hold_count":  len(holds),
            "sell_count":  len(sells),
            "swap_count":  len(swaps),
            "add_count":   len(new_adds),
            "total_actions": len(sells) + len(swaps),
        },
    }
