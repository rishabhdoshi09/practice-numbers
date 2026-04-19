"""
ExecutionEngine: Phase 1 — Paper Trading Simulator.

Simulates order fills with realistic slippage and commission.
Tracks P&L, win rate, Sharpe ratio, and full trade log.
"""
from __future__ import annotations
import uuid
import logging
from datetime import datetime
from typing import Optional

import numpy as np

from backend.config import (
    PAPER_TRADING_SLIPPAGE_BPS,
    PAPER_TRADING_COMMISSION_BPS,
    SHARPE_ANNUALISE,
    DEFAULT_PORTFOLIO_VALUE,
)

logger = logging.getLogger(__name__)


class OrderSide(str):
    BUY  = "BUY"
    SELL = "SELL"


class Order:
    def __init__(self, symbol: str, side: str, qty: int, price: float):
        self.id        = str(uuid.uuid4())[:8]
        self.symbol    = symbol
        self.side      = side
        self.qty       = qty
        self.price     = price
        self.timestamp = datetime.utcnow().isoformat()


class ExecutionEngine:
    """
    Paper trading engine.
    All orders are filled at last-traded price ± slippage, minus commission.
    """

    def __init__(self, starting_capital: float = DEFAULT_PORTFOLIO_VALUE):
        self.cash          = starting_capital
        self.starting_cash = starting_capital
        self.positions: dict[str, dict] = {}   # symbol → {qty, avg_cost}
        self.trade_log: list[dict] = []
        self.daily_pnl: list[float] = []

    # ── Public API ─────────────────────────────────────────────────────────────

    def execute(self, symbol: str, side: str, price: float,
                position_inr: float) -> dict:
        """
        Submit a paper order.

        Args:
            symbol: NSE ticker string.
            side: 'BUY' or 'SELL'.
            price: Last traded price (pre-slippage).
            position_inr: INR value of position to open/close.

        Returns:
            Order confirmation dict.
        """
        fill_price = self._apply_slippage(price, side)
        commission = fill_price * PAPER_TRADING_COMMISSION_BPS / 10_000
        net_price  = fill_price + (commission if side == "BUY" else -commission)
        qty = max(1, int(position_inr / net_price))

        if side == "BUY":
            cost = net_price * qty
            if cost > self.cash:
                qty   = max(1, int(self.cash / net_price))
                cost  = net_price * qty
            self.cash -= cost
            pos = self.positions.get(symbol, {"qty": 0, "avg_cost": 0.0})
            total_qty  = pos["qty"] + qty
            total_cost = pos["avg_cost"] * pos["qty"] + net_price * qty
            self.positions[symbol] = {"qty": total_qty, "avg_cost": total_cost / total_qty}

        elif side == "SELL":
            pos = self.positions.get(symbol)
            if not pos or pos["qty"] < 1:
                return {"status": "rejected", "reason": "no_position"}
            qty       = min(qty, pos["qty"])
            proceeds  = net_price * qty
            self.cash += proceeds
            realised  = (net_price - pos["avg_cost"]) * qty
            self.daily_pnl.append(realised)
            pos["qty"] -= qty
            if pos["qty"] == 0:
                del self.positions[symbol]
            else:
                self.positions[symbol] = pos

        fill = {
            "order_id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "requested_price": round(price, 2),
            "fill_price": round(fill_price, 2),
            "commission_inr": round(commission * qty, 2),
            "net_price": round(net_price, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "status": "filled",
        }
        self.trade_log.append(fill)
        logger.info("Paper fill: %s %s %d @ ₹%.2f", side, symbol, qty, fill_price)
        return fill

    def portfolio_summary(self, current_prices: dict[str, float]) -> dict:
        """Mark-to-market portfolio summary with performance metrics."""
        mtm_value = self.cash
        positions_detail = []
        for sym, pos in self.positions.items():
            price     = current_prices.get(sym, pos["avg_cost"])
            mkt_val   = price * pos["qty"]
            unrealised = (price - pos["avg_cost"]) * pos["qty"]
            mtm_value += mkt_val
            positions_detail.append({
                "symbol": sym,
                "qty": pos["qty"],
                "avg_cost": round(pos["avg_cost"], 2),
                "current_price": round(price, 2),
                "market_value_inr": round(mkt_val, 2),
                "unrealised_pnl_inr": round(unrealised, 2),
                "unrealised_pnl_pct": round(unrealised / (pos["avg_cost"] * pos["qty"] + 1e-10) * 100, 3),
            })

        total_pnl = mtm_value - self.starting_cash
        metrics   = self._performance_metrics()

        return {
            "cash": round(self.cash, 2),
            "portfolio_value": round(mtm_value, 2),
            "starting_capital": round(self.starting_cash, 2),
            "total_pnl_inr": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / self.starting_cash * 100, 3),
            "positions": positions_detail,
            "metrics": metrics,
            "trade_count": len(self.trade_log),
        }

    def get_trade_log(self) -> list[dict]:
        return self.trade_log

    # ── Private ────────────────────────────────────────────────────────────────

    def _apply_slippage(self, price: float, side: str) -> float:
        """Buy fills slightly higher, sell slightly lower — realistic market impact."""
        slip = price * PAPER_TRADING_SLIPPAGE_BPS / 10_000
        return price + slip if side == "BUY" else price - slip

    def _performance_metrics(self) -> dict:
        """Sharpe ratio and win rate from closed-trade P&L."""
        if len(self.daily_pnl) < 2:
            return {"sharpe_ratio": None, "win_rate": None, "total_trades": len(self.trade_log)}
        pnl = np.array(self.daily_pnl)
        sharpe = (pnl.mean() / (pnl.std() + 1e-10)) * SHARPE_ANNUALISE
        win_rate = float(np.mean(pnl > 0))
        return {
            "sharpe_ratio": round(float(sharpe), 4),
            "win_rate": round(win_rate * 100, 2),
            "avg_win_inr": round(float(pnl[pnl > 0].mean()), 2) if any(pnl > 0) else 0,
            "avg_loss_inr": round(float(abs(pnl[pnl < 0].mean())), 2) if any(pnl < 0) else 0,
            "total_trades": len(self.trade_log),
        }
