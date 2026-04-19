"""
Stage 3: Scenario Modeling — Bull / Base / Bear price targets.

Builds probability-weighted price projections at 1, 3, 6, and 12 months
using log-normal GBM with scenario-specific drift assumptions.

Probabilities are adjusted by current signal conviction so the model
"debates itself" — high conviction raises bull probability, low conviction
raises bear probability.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def build_scenarios(symbol: str, close: pd.Series, features: dict) -> dict:
    """
    Return bull/base/bear price targets and probability-weighted expected prices
    across four time horizons.

    Args:
        symbol:   NSE ticker
        close:    Historical close price series
        features: FeatureEngine output dict

    Returns:
        Full scenario dict with current price, probabilities, targets per horizon
    """
    price      = float(close.iloc[-1])
    exp_ret    = features.get("expected_return", {})
    annual_ret = exp_ret.get("annual_return",    0.10)
    annual_vol = exp_ret.get("annual_volatility", 0.22)
    signals    = features["signals"]

    # ── Conviction score (average of trend, ML, momentum) ────────────────────
    conviction = (signals["trend"] + signals["ml"] + signals["momentum"]) / 3.0

    # ── Probability weights vary with conviction ──────────────────────────────
    if conviction > 0.40:
        probs = {"bull": 0.42, "base": 0.44, "bear": 0.14}
    elif conviction > 0.20:
        probs = {"bull": 0.34, "base": 0.46, "bear": 0.20}
    elif conviction > 0.05:
        probs = {"bull": 0.28, "base": 0.46, "bear": 0.26}
    elif conviction > -0.10:
        probs = {"bull": 0.22, "base": 0.45, "bear": 0.33}
    elif conviction > -0.30:
        probs = {"bull": 0.16, "base": 0.42, "bear": 0.42}
    else:
        probs = {"bull": 0.10, "base": 0.38, "bear": 0.52}

    # ── Scenario drifts ───────────────────────────────────────────────────────
    bull_drift = annual_ret + 1.5 * annual_vol   # optimistic tail
    base_drift = annual_ret                       # central estimate
    bear_drift = annual_ret - 1.5 * annual_vol   # pessimistic tail

    # ── Project across horizons ───────────────────────────────────────────────
    horizons = {"1m": 21, "3m": 63, "6m": 126, "12m": 252}
    results: dict[str, dict] = {}

    for label, days in horizons.items():
        t = days / 252.0
        half_var = 0.5 * annual_vol ** 2

        p_bull = round(price * np.exp((bull_drift - half_var) * t), 2)
        p_base = round(price * np.exp((base_drift - half_var) * t), 2)
        p_bear = round(price * np.exp((bear_drift - half_var) * t), 2)
        weighted = round(
            probs["bull"] * p_bull +
            probs["base"] * p_base +
            probs["bear"] * p_bear,
            2,
        )

        results[label] = {
            "bull":          p_bull,
            "base":          p_base,
            "bear":          p_bear,
            "weighted":      weighted,
            "bull_pct":      round((p_bull - price) / price * 100, 1),
            "base_pct":      round((p_base - price) / price * 100, 1),
            "bear_pct":      round((p_bear - price) / price * 100, 1),
            "weighted_pct":  round((weighted - price) / price * 100, 1),
        }

    # ── Risk/reward summary ───────────────────────────────────────────────────
    h12 = results["12m"]
    rr_ratio = round(
        abs(h12["bull_pct"]) / (abs(h12["bear_pct"]) + 1e-10), 2
    )

    return {
        "symbol":        symbol,
        "current_price": round(price, 2),
        "annual_return": round(annual_ret * 100, 2),
        "annual_vol":    round(annual_vol * 100, 2),
        "conviction":    round(conviction, 3),
        "probabilities": {k: round(v * 100, 1) for k, v in probs.items()},
        "horizons":      results,
        "risk_reward_12m": rr_ratio,
    }
