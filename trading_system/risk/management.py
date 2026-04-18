"""
Risk management module.

PHILOSOPHY
----------
Risk management is not about maximising returns — it is about surviving long
enough to let the strategy's edge compound. Three rules govern every trade:

  1. FIXED FRACTIONAL SIZING: risk exactly R% of current equity per trade.
     "Current equity" uses real-time mark-to-market, not initial capital.
     This means position sizes shrink after losses (protection) and grow
     after gains (compounding) — mathematically optimal for log-wealth growth
     when the edge is positive (Kelly criterion variant).

  2. PORTFOLIO HEAT CAP: never have more than max_portfolio_heat% of equity
     at risk across all open trades simultaneously. This prevents correlated
     losses (e.g., all stocks falling together in a crash) from being fatal.

  3. MAX DRAWDOWN HALT: if the portfolio falls more than max_drawdown_limit%
     from its peak, stop opening new trades. This is a circuit breaker that
     prevents a strategy malfunction from blowing up the account.

POSITION SIZING FORMULA
-----------------------
  risk_amount = equity * risk_per_trade               (e.g., 1% of 1,000,000 = 10,000)
  risk_per_share = entry_price - stop_price
  shares = risk_amount / risk_per_share

  This means: if the stop is hit, you lose exactly risk_amount.
  The position is naturally smaller when stops are wide (high volatility)
  and larger when stops are tight (low volatility). This is desirable —
  volatile markets get smaller bets automatically.
"""

import logging
import math
from typing import Optional

import numpy as np
import pandas as pd

from trading_system.config import RiskConfig

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def position_size(
        self,
        equity: float,
        entry_price: float,
        stop_price: float,
        fractional: bool = False,
    ) -> float:
        """
        Calculate position size (shares) using the fixed-fractional method.

        Args:
            equity:       current portfolio equity (mark-to-market)
            entry_price:  expected fill price (after slippage)
            stop_price:   hard stop loss level
            fractional:   allow fractional shares (for crypto / testing)

        Returns:
            Number of shares to buy (0 if stop is above entry or risk is too small).
        """
        risk_per_share = entry_price - stop_price
        if risk_per_share <= 0:
            logger.debug("Stop price >= entry price — no position taken")
            return 0.0

        risk_amount = equity * self.cfg.risk_per_trade
        raw_shares = risk_amount / risk_per_share

        if fractional:
            return round(raw_shares, 4)
        else:
            shares = math.floor(raw_shares)
            return float(shares)

    def max_position_value(self, equity: float) -> float:
        """
        Hard cap on single position value to prevent concentration.
        Default: 20% of equity (5 positions max at equal weight).
        """
        return equity / self.cfg.max_positions

    # ------------------------------------------------------------------
    # Portfolio heat
    # ------------------------------------------------------------------

    def total_risk_at_risk(
        self,
        open_trades,   # list of Trade objects
        equity: float,
    ) -> float:
        """
        Returns the total fraction of equity currently 'at risk' across all
        open positions (i.e., sum of (entry - stop) * shares / equity).
        """
        if equity <= 0:
            return 0.0
        total_risk = sum(
            max(0, (t.entry_price - t.stop_price) * t.shares)
            for t in open_trades
        )
        return total_risk / equity

    def can_open_new_trade(
        self,
        open_trades,
        equity: float,
        n_open_positions: int,
    ) -> bool:
        """
        Returns True if a new trade is allowed given current heat and position limits.
        """
        if n_open_positions >= self.cfg.max_positions:
            logger.debug("Position limit reached (%d)", self.cfg.max_positions)
            return False
        heat = self.total_risk_at_risk(open_trades, equity)
        if heat >= self.cfg.max_portfolio_heat:
            logger.debug("Portfolio heat limit: %.2f%%", heat * 100)
            return False
        return True

    # ------------------------------------------------------------------
    # Drawdown monitor
    # ------------------------------------------------------------------

    @staticmethod
    def rolling_drawdown(equity_series: pd.Series) -> pd.Series:
        """
        Calculate rolling drawdown from equity curve.
        Drawdown at time t = (peak_so_far - equity_t) / peak_so_far
        """
        rolling_peak = equity_series.cummax()
        drawdown = (rolling_peak - equity_series) / rolling_peak
        return drawdown

    @staticmethod
    def max_drawdown(equity_series: pd.Series) -> float:
        """Return the maximum drawdown as a positive fraction (e.g., 0.15 = 15%)."""
        dd = RiskManager.rolling_drawdown(equity_series)
        return float(dd.max())

    # ------------------------------------------------------------------
    # Trailing stop updater (for live use)
    # ------------------------------------------------------------------

    @staticmethod
    def update_trailing_stop(
        current_stop: float,
        current_price: float,
        atr: float,
        multiplier: float,
    ) -> float:
        """
        Ratchet the trailing stop upward as price moves in our favour.
        Never move the stop down — only up (or keep).
        new_stop = max(current_stop, current_price - multiplier * ATR)
        """
        candidate = current_price - multiplier * atr
        return max(current_stop, candidate)


# ------------------------------------------------------------------
# Risk report helper
# ------------------------------------------------------------------

def risk_report(equity_series: pd.Series, trade_log: pd.DataFrame) -> dict:
    """
    Produce a risk snapshot — useful for post-backtest analysis
    and for live monitoring dashboards.
    """
    dd = RiskManager.rolling_drawdown(equity_series)
    max_dd = float(dd.max())
    max_dd_date = dd.idxmax()

    report = {
        "max_drawdown_pct": round(max_dd * 100, 2),
        "max_drawdown_date": max_dd_date,
        "avg_drawdown_pct": round(dd.mean() * 100, 2),
        "time_in_drawdown_pct": round((dd > 0.01).mean() * 100, 2),
    }

    if not trade_log.empty:
        report["avg_loss"] = round(trade_log.loc[trade_log["net_pnl"] < 0, "net_pnl"].mean(), 2)
        report["max_single_loss"] = round(trade_log["net_pnl"].min(), 2)
        report["avg_risk_per_trade_pct"] = round(
            abs(report["avg_loss"]) / equity_series.iloc[0] * 100, 3
        )

    return report
