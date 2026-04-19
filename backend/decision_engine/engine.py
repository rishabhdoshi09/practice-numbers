"""
DecisionEngine: aggregates all feature signals into a single BUY/SELL/HOLD decision.

Each signal module outputs a score in [-1, +1].
Signals are combined via configurable weights (config.SIGNAL_WEIGHTS).
Final score maps to BUY / SELL / HOLD with a confidence percentage.
"""
from __future__ import annotations
import numpy as np
from enum import Enum

from backend.config import (
    SIGNAL_WEIGHTS, BUY_THRESHOLD, SELL_THRESHOLD, CONFIDENCE_SCALE,
)


class Action(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class RiskLevel(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class DecisionEngine:
    """Aggregates feature signals and produces a final trading decision."""

    def decide(self, signals: dict[str, float], features: dict) -> dict:
        """
        Args:
            signals: dict mapping signal name → score in [-1, +1]
            features: full feature dict from FeatureEngine (for risk context)

        Returns:
            Decision dict with action, confidence, risk level, and breakdown.
        """
        # Validate all expected signals are present; default missing to 0
        weighted_sum = 0.0
        total_weight = 0.0
        breakdown    = {}

        for name, weight in SIGNAL_WEIGHTS.items():
            raw_score = float(signals.get(name, 0.0))
            # Clip each sub-signal to valid range
            clipped = float(np.clip(raw_score, -1, 1))
            contribution = clipped * weight
            weighted_sum += contribution
            total_weight += weight
            breakdown[name] = {
                "raw_signal": round(clipped, 4),
                "weight": weight,
                "contribution": round(contribution, 4),
            }

        # Normalise (in case weights don't sum to exactly 1.0 due to floats)
        final_score = weighted_sum / (total_weight + 1e-10)

        # ── Map score to action ────────────────────────────────────────────────
        if final_score >= BUY_THRESHOLD:
            action = Action.BUY
        elif final_score <= SELL_THRESHOLD:
            action = Action.SELL
        else:
            action = Action.HOLD

        # ── Confidence: |score| scaled to 0–100, boosted by signal agreement ──
        raw_confidence = abs(final_score) * CONFIDENCE_SCALE
        # Agreement bonus: fraction of signals that agree with final direction
        n_agree = sum(
            1 for name in SIGNAL_WEIGHTS
            if np.sign(signals.get(name, 0)) == np.sign(final_score) and signals.get(name, 0) != 0
        )
        agreement_pct = n_agree / len(SIGNAL_WEIGHTS)
        confidence = min(100, raw_confidence * (0.6 + 0.4 * agreement_pct))

        # ── Risk level from GARCH conditional vol ─────────────────────────────
        annual_vol = features.get("model_details", {}).get("garch", {}).get("annual_vol_estimate", 0.25)
        risk_level = self._classify_risk(float(annual_vol))

        return {
            "action": action.value,
            "confidence": round(confidence, 1),
            "final_score": round(final_score, 4),
            "risk_level": risk_level.value,
            "signal_breakdown": breakdown,
            "signals_agree": round(agreement_pct * 100, 1),
            "buy_threshold": BUY_THRESHOLD,
            "sell_threshold": SELL_THRESHOLD,
        }

    @staticmethod
    def _classify_risk(annual_vol: float) -> RiskLevel:
        """Bucketed annualised vol → risk label."""
        if annual_vol < 0.18:
            return RiskLevel.LOW
        elif annual_vol < 0.30:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.HIGH
