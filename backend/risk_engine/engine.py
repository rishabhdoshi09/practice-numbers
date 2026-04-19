"""
RiskEngine: quantifies and controls downside risk.

Modules:
  - Kelly Criterion position sizing
  - ATR-based dynamic stop loss
  - Max drawdown monitoring
  - Value at Risk (VaR) — 95 % and 99 % — historical simulation
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from backend.config import (
    KELLY_FRACTION, MAX_POSITION_PCT, MAX_DRAWDOWN_PCT,
    ATR_STOP_MULTIPLIER, VAR_CONFIDENCE_95, VAR_CONFIDENCE_99,
    DEFAULT_PORTFOLIO_VALUE,
)


class RiskEngine:

    def compute(
        self,
        df: pd.DataFrame,
        current_price: float,
        atr: float,
        win_rate: float = 0.55,    # historical win rate estimate
        avg_win_loss: float = 1.4, # average win / average loss ratio
        portfolio_value: float = DEFAULT_PORTFOLIO_VALUE,
        peak_value: float | None = None,
    ) -> dict:
        """
        Full risk assessment for one symbol given current market conditions.

        Args:
            df: OHLCV DataFrame (for VaR calculation from historical returns).
            current_price: Latest traded price.
            atr: Latest Average True Range value.
            win_rate: Estimated probability that next trade is a winner.
            avg_win_loss: Ratio of average winning return to average losing return.
            portfolio_value: Current total portfolio value in ₹.
            peak_value: All-time peak portfolio value (for drawdown tracking).
        """
        close = df["Close"]
        daily_returns = close.pct_change().dropna()

        kelly      = self._kelly_position_size(win_rate, avg_win_loss, portfolio_value)
        stop_price = self._atr_stop_loss(current_price, atr)
        drawdown   = self._max_drawdown(close)
        var_95     = self._var(daily_returns, VAR_CONFIDENCE_95, portfolio_value)
        var_99     = self._var(daily_returns, VAR_CONFIDENCE_99, portfolio_value)
        cvar_95    = self._cvar(daily_returns, VAR_CONFIDENCE_95, portfolio_value)

        current_drawdown = self._current_drawdown(portfolio_value, peak_value or portfolio_value)
        halt_trading     = current_drawdown >= MAX_DRAWDOWN_PCT

        return {
            "position_sizing": kelly,
            "stop_loss": {
                "price": round(stop_price, 2),
                "distance_pct": round((current_price - stop_price) / current_price * 100, 3),
                "atr_used": round(atr, 4),
                "multiplier": ATR_STOP_MULTIPLIER,
            },
            "drawdown": {
                "max_historical_pct": round(drawdown * 100, 3),
                "current_pct": round(current_drawdown * 100, 3),
                "halt_threshold_pct": MAX_DRAWDOWN_PCT * 100,
                "halt_trading": halt_trading,
            },
            "var": {
                "var_95_pct": round(var_95 * 100, 3),
                "var_99_pct": round(var_99 * 100, 3),
                "cvar_95_pct": round(cvar_95 * 100, 3),
                "var_95_inr": round(var_95 * portfolio_value, 2),
                "var_99_inr": round(var_99 * portfolio_value, 2),
                "method": "Historical Simulation",
            },
            "portfolio_value": portfolio_value,
        }

    # ── Position sizing ────────────────────────────────────────────────────────

    def _kelly_position_size(
        self, win_rate: float, avg_win_loss: float, portfolio_value: float
    ) -> dict:
        """
        Half-Kelly criterion.
        Full Kelly f* = (p*(b+1) - 1) / b, where b = avg_win/avg_loss ratio,
        then we apply a 0.5 safety multiplier to halve it.
        """
        b = avg_win_loss
        p = win_rate
        full_kelly = (p * (b + 1) - 1) / b
        full_kelly = max(0.0, full_kelly)          # never short (Phase 1)
        half_kelly = full_kelly * KELLY_FRACTION
        # Cap at maximum position limit
        position_pct = min(half_kelly, MAX_POSITION_PCT)
        position_inr = position_value = portfolio_value * position_pct
        return {
            "full_kelly_pct": round(full_kelly * 100, 3),
            "half_kelly_pct": round(half_kelly * 100, 3),
            "recommended_pct": round(position_pct * 100, 3),
            "recommended_inr": round(position_inr, 2),
            "method": "Half-Kelly",
            "max_position_pct": MAX_POSITION_PCT * 100,
        }

    # ── Stop loss ──────────────────────────────────────────────────────────────

    def _atr_stop_loss(self, price: float, atr_val: float) -> float:
        """Stop price = entry price − (ATR_multiplier × ATR)."""
        return price - ATR_STOP_MULTIPLIER * atr_val

    # ── Drawdown ───────────────────────────────────────────────────────────────

    def _max_drawdown(self, close: pd.Series) -> float:
        """Maximum peak-to-trough drawdown over the entire price history."""
        cumulative = (1 + close.pct_change()).cumprod()
        rolling_max = cumulative.cummax()
        drawdowns = (cumulative - rolling_max) / rolling_max
        return float(abs(drawdowns.min()))

    def _current_drawdown(self, current: float, peak: float) -> float:
        return max(0.0, (peak - current) / (peak + 1e-10))

    # ── Value at Risk ──────────────────────────────────────────────────────────

    def _var(self, returns: pd.Series, confidence: float, portfolio: float) -> float:
        """
        Historical simulation VaR.
        Sorts historical daily P&L and takes the (1-confidence) percentile.
        """
        sorted_rets = np.sort(returns.values)
        idx = int((1 - confidence) * len(sorted_rets))
        var_ret = abs(sorted_rets[max(0, idx)])
        return var_ret   # as a fraction of portfolio

    def _cvar(self, returns: pd.Series, confidence: float, portfolio: float) -> float:
        """Conditional VaR (Expected Shortfall) — mean of losses beyond VaR."""
        sorted_rets = np.sort(returns.values)
        idx = int((1 - confidence) * len(sorted_rets))
        tail = sorted_rets[:max(1, idx)]
        return float(abs(tail.mean())) if len(tail) > 0 else 0.0
