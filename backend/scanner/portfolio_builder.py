"""
Stage 4: Portfolio Construction — constrained Markowitz optimisation.

Constraints enforced:
  • No single sector > 35 % of portfolio
  • Each position must have positive historical expected return
  • Max 25 % per individual position
  • Target: 15 positions (or fewer if candidates insufficient)
  • Objective: maximise Sharpe ratio (beat the benchmark)
"""
from __future__ import annotations
import logging
import numpy as np
import pandas as pd
from scipy.optimize import minimize

logger = logging.getLogger(__name__)

RISK_FREE = 0.065          # Indian 10-yr G-Sec proxy
MAX_SECTOR_PCT = 0.35
MAX_POSITION_PCT = 0.25
MIN_CONFIDENCE = 40
MIN_HISTORY_DAYS = 60


def build_portfolio(
    scan_result: dict,
    data_engine,
    capital: int = 500_000,
    max_positions: int = 15,
) -> dict:
    """
    Build an optimal Nifty 50 sub-portfolio from the latest scan results.

    Args:
        scan_result:   Output of ScanEngine.run()
        data_engine:   DataEngine instance (for OHLCV fetches)
        capital:       Total capital in INR
        max_positions: Maximum number of positions to hold

    Returns:
        positions list with weights + portfolio-level stats
    """
    all_stocks = scan_result.get("all", [])

    # ── Stage 4 Step 1: filter candidates ────────────────────────────────────
    candidates = [
        s for s in all_stocks
        if s.get("action") == "BUY" and s.get("confidence", 0) >= MIN_CONFIDENCE
    ]

    if len(candidates) < 3:
        return {
            "error": "Insufficient BUY candidates. Run a market scan first — need at least 3 BUY signals.",
            "positions": [],
        }

    # Take up to 2× max_positions for the optimiser to choose from
    candidates = candidates[: max_positions * 2]

    # ── Stage 4 Step 2: fetch returns, filter negative expected return ────────
    returns_map: dict[str, pd.Series] = {}
    meta_map:    dict[str, dict]      = {}

    for s in candidates:
        sym = s["symbol"]
        try:
            df      = data_engine.get_ohlcv(sym, days=252)
            if len(df) < MIN_HISTORY_DAYS:
                continue
            rets    = df["Close"].pct_change().dropna()
            ann_ret = float(rets.mean() * 252)
            if ann_ret <= 0:
                logger.debug("Skipping %s — negative expected return (%.2f%%)", sym, ann_ret * 100)
                continue
            returns_map[sym] = rets
            meta_map[sym]    = s
        except Exception as e:
            logger.debug("Skipping %s — data fetch failed: %s", sym, e)

    if len(returns_map) < 3:
        return {
            "error": "Not enough stocks with positive expected return. Market may be broadly bearish.",
            "positions": [],
        }

    # ── Stage 4 Step 3: build returns DataFrame + annualised stats ───────────
    ret_df = pd.DataFrame(returns_map).dropna()
    mu     = ret_df.mean() * 252
    cov    = ret_df.cov()  * 252
    syms   = list(mu.index)
    n      = len(syms)

    sector_map = {sym: meta_map[sym].get("sector", "Other") for sym in syms}

    # ── Stage 4 Step 4: optimise for max Sharpe ───────────────────────────────
    def _stats(w):
        ret = float(w @ mu)
        vol = float(np.sqrt(w @ cov.values @ w))
        return ret, vol

    def _neg_sharpe(w):
        r, v = _stats(w)
        return -(r - RISK_FREE) / (v + 1e-10)

    constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]

    # Sector concentration cap
    for sector in set(sector_map.values()):
        idxs = [i for i, s in enumerate(syms) if sector_map[s] == sector]
        constraints.append({
            "type": "ineq",
            "fun": lambda w, ix=idxs: MAX_SECTOR_PCT - sum(w[i] for i in ix),
        })

    bounds = [(0.0, MAX_POSITION_PCT)] * n
    w0     = np.full(n, 1.0 / n)

    result = minimize(
        _neg_sharpe, w0, method="SLSQP",
        bounds=bounds, constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-9},
    )
    weights = result.x if result.success else w0

    # Zero out negligible positions and renormalise
    weights[weights < 0.015] = 0.0
    total_w = weights.sum()
    if total_w > 0:
        weights = weights / total_w

    # ── Stage 4 Step 5: build position list ──────────────────────────────────
    positions = []
    for i, sym in enumerate(syms):
        w = float(weights[i])
        if w < 0.01:
            continue
        s        = meta_map[sym]
        ann_ret  = float(mu[sym])
        ann_vol  = float(np.sqrt(float(cov[sym][sym])))
        alloc_inr = round(capital * w)
        price    = s.get("price", 0)
        shares   = int(alloc_inr / price) if price > 0 else 0

        positions.append({
            "symbol":               sym,
            "name":                 s.get("name", sym),
            "sector":               s.get("sector", "Other"),
            "action":               s.get("action", "BUY"),
            "confidence":           s.get("confidence", 0),
            "weight_pct":           round(w * 100, 2),
            "alloc_inr":            alloc_inr,
            "shares":               shares,
            "price":                price,
            "expected_return_pct":  round(ann_ret * 100, 2),
            "volatility_pct":       round(ann_vol * 100, 2),
            "sharpe":               round((ann_ret - RISK_FREE) / (ann_vol + 1e-10), 3),
        })

    positions.sort(key=lambda x: -x["weight_pct"])
    positions = positions[:max_positions]

    # ── Stage 4 Step 6: portfolio-level stats ─────────────────────────────────
    final_weights = np.array([w["weight_pct"] / 100 for w in positions])
    final_syms    = [p["symbol"] for p in positions]
    if final_syms:
        sub_mu  = mu[final_syms].values
        sub_cov = cov.loc[final_syms, final_syms].values
        p_ret   = float(final_weights @ sub_mu)
        p_vol   = float(np.sqrt(final_weights @ sub_cov @ final_weights))
    else:
        p_ret, p_vol = 0.0, 0.0

    # Sector allocation
    sector_alloc: dict[str, float] = {}
    for pos in positions:
        sec = pos["sector"]
        sector_alloc[sec] = round(sector_alloc.get(sec, 0) + pos["weight_pct"], 2)

    return {
        "positions":       positions,
        "n_positions":     len(positions),
        "capital":         capital,
        "portfolio_stats": {
            "expected_return_pct": round(p_ret * 100, 2),
            "volatility_pct":      round(p_vol * 100, 2),
            "sharpe_ratio":        round((p_ret - RISK_FREE) / (p_vol + 1e-10), 3),
        },
        "sector_allocation": dict(
            sorted(sector_alloc.items(), key=lambda x: -x[1])
        ),
        "constraints_applied": {
            "max_sector_pct":    MAX_SECTOR_PCT * 100,
            "max_position_pct":  MAX_POSITION_PCT * 100,
            "min_expected_return": "> 0 %",
            "optimizer":          "Markowitz Max-Sharpe (SLSQP)",
        },
        "optimizer_converged": result.success,
    }
