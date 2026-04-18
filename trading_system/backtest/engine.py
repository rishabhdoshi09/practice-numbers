"""
Backtesting engine.

Architecture: event-driven simulation over a sorted time series.

Key realism features:
  1. Execution on next-bar OPEN — signals from bar t execute at bar t+1 open.
     This is the single most important bias-prevention rule.
  2. Slippage: execution price = open * (1 + slippage_pct) for buys,
                                 open * (1 - slippage_pct) for sells.
  3. Commission: charged as a % of trade value on both entry and exit.
  4. Fractional vs integer shares: controlled by BacktestConfig.fractional_shares.
  5. Position sizing: delegated to RiskManager (see risk/management.py).

Trade object captures full lifecycle:
  entry_date, entry_price (after slippage), shares
  exit_date, exit_price (after slippage)
  gross_pnl, net_pnl (after costs), return_pct, holding_days, exit_reason

Portfolio state tracks:
  cash, open_positions, closed_trades, equity_curve (daily)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from trading_system.config import RiskConfig, BacktestConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    symbol: str
    entry_date: pd.Timestamp
    entry_price: float         # after slippage
    shares: float
    stop_price: float
    target_price: float

    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""

    @property
    def is_open(self) -> bool:
        return self.exit_date is None

    @property
    def gross_pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) * self.shares

    @property
    def net_pnl(self) -> float:
        """PnL after commission (slippage already baked into prices)."""
        return self.gross_pnl - self.total_commission

    @property
    def total_commission(self) -> float:
        """Placeholder — filled by engine after trade closes."""
        return getattr(self, "_commission", 0.0)

    @property
    def return_pct(self) -> float:
        if self.exit_price is None or self.entry_price == 0:
            return 0.0
        return (self.exit_price / self.entry_price - 1) * 100

    @property
    def holding_days(self) -> int:
        if self.exit_date is None:
            return 0
        return (self.exit_date - self.entry_date).days

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "entry_date": self.entry_date,
            "entry_price": round(self.entry_price, 4),
            "shares": self.shares,
            "stop_price": round(self.stop_price, 4),
            "target_price": round(self.target_price, 4),
            "exit_date": self.exit_date,
            "exit_price": round(self.exit_price, 4) if self.exit_price else None,
            "exit_reason": self.exit_reason,
            "gross_pnl": round(self.gross_pnl, 2),
            "net_pnl": round(self.net_pnl, 2),
            "return_pct": round(self.return_pct, 3),
            "holding_days": self.holding_days,
            "commission": round(self.total_commission, 2),
        }


@dataclass
class Portfolio:
    initial_capital: float
    cash: float = 0.0
    open_trades: List[Trade] = field(default_factory=list)
    closed_trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Tuple[pd.Timestamp, float]] = field(default_factory=list)
    # drawdown control
    peak_equity: float = 0.0
    trading_halted: bool = False

    def __post_init__(self):
        self.cash = self.initial_capital
        self.peak_equity = self.initial_capital

    def open_position_value(self, current_prices: Dict[str, float]) -> float:
        return sum(
            t.shares * current_prices.get(t.symbol, t.entry_price)
            for t in self.open_trades
        )

    def total_equity(self, current_prices: Dict[str, float]) -> float:
        return self.cash + self.open_position_value(current_prices)

    def current_risk_deployed(self, current_prices: Dict[str, float]) -> float:
        """Sum of (entry - stop) * shares for all open trades, as fraction of equity."""
        equity = self.total_equity(current_prices)
        if equity == 0:
            return 0.0
        risk = sum(
            max(0, (t.entry_price - t.stop_price) * t.shares)
            for t in self.open_trades
        )
        return risk / equity


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class BacktestEngine:
    """
    Single-pass event-driven backtester.

    Usage:
        engine = BacktestEngine(risk_cfg, backtest_cfg)
        result = engine.run(universe_with_signals, risk_manager)
    """

    def __init__(self, risk_cfg: RiskConfig, backtest_cfg: BacktestConfig):
        self.rcfg = risk_cfg
        self.bcfg = backtest_cfg

    def run(
        self,
        universe: Dict[str, pd.DataFrame],
        risk_manager,  # RiskManager — avoids circular import
    ) -> Tuple[Portfolio, pd.DataFrame]:
        """
        Run the backtest across all symbols.

        Returns:
            portfolio  — final Portfolio object with all trades
            equity_df  — daily equity curve as a DataFrame
        """
        portfolio = Portfolio(initial_capital=self.rcfg.initial_capital)

        # Build a unified daily timeline across all symbols
        all_dates = sorted(set().union(*[set(df.index) for df in universe.values()]))

        for date in all_dates:
            if portfolio.trading_halted:
                # Still record equity on halted days using last known prices
                prices = self._spot_prices(universe, date)
                equity = portfolio.total_equity(prices)
                portfolio.equity_curve.append((date, equity))
                continue

            prices = self._spot_prices(universe, date)
            current_equity = portfolio.total_equity(prices)

            # Update peak and check drawdown limit
            portfolio.peak_equity = max(portfolio.peak_equity, current_equity)
            drawdown = (portfolio.peak_equity - current_equity) / portfolio.peak_equity
            if drawdown >= self.rcfg.max_drawdown_limit:
                logger.warning(
                    "Max drawdown %.1f%% hit on %s — halting trading",
                    drawdown * 100, date.date()
                )
                portfolio.trading_halted = True
                portfolio.equity_curve.append((date, current_equity))
                continue

            # --- Process exits first (to free cash for new entries) ---
            self._process_exits(portfolio, universe, date, prices)

            # --- Process entries ---
            self._process_entries(portfolio, universe, date, prices, risk_manager, current_equity)

            # Record end-of-day equity
            eod_prices = self._spot_prices(universe, date)
            eod_equity = portfolio.total_equity(eod_prices)
            portfolio.equity_curve.append((date, eod_equity))

        # Close any remaining open trades at last available price
        self._force_close_open_trades(portfolio, universe)

        equity_df = pd.DataFrame(portfolio.equity_curve, columns=["date", "equity"])
        equity_df = equity_df.set_index("date")

        logger.info(
            "Backtest complete: %d closed trades, final equity %.2f",
            len(portfolio.closed_trades),
            equity_df["equity"].iloc[-1] if not equity_df.empty else 0,
        )
        return portfolio, equity_df

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _spot_prices(self, universe: Dict[str, pd.DataFrame], date) -> Dict[str, float]:
        prices = {}
        for sym, df in universe.items():
            if date in df.index:
                prices[sym] = df.loc[date, "close"]
        return prices

    def _execution_price(self, open_price: float, direction: str) -> float:
        slip = self.rcfg.slippage_pct
        if direction == "buy":
            return open_price * (1 + slip)
        return open_price * (1 - slip)

    def _commission(self, trade_value: float) -> float:
        return trade_value * self.rcfg.commission_pct

    def _process_entries(
        self,
        portfolio: Portfolio,
        universe: Dict[str, pd.DataFrame],
        date,
        prices: Dict[str, float],
        risk_manager,
        current_equity: float,
    ) -> None:
        open_syms = {t.symbol for t in portfolio.open_trades}

        for sym, df in universe.items():
            if sym in open_syms:
                continue
            if date not in df.index:
                continue
            if len(portfolio.open_trades) >= self.rcfg.max_positions:
                break

            row = df.loc[date]
            # signal == 1 means: buy at today's open (set by yesterday's bar)
            if row.get("signal", 0) != 1:
                continue

            # Check portfolio heat limit
            risk_deployed = portfolio.current_risk_deployed(prices)
            if risk_deployed >= self.rcfg.max_portfolio_heat:
                logger.debug("Portfolio heat limit reached on %s", date.date())
                break

            open_price = row["open"]
            exec_price = self._execution_price(open_price, "buy")

            stop = row.get("stop_price", exec_price * 0.98)
            target = row.get("target_price", exec_price * 1.06)

            if np.isnan(stop):
                stop = exec_price * 0.98
            if np.isnan(target):
                target = exec_price * 1.06

            shares = risk_manager.position_size(
                equity=current_equity,
                entry_price=exec_price,
                stop_price=stop,
                fractional=self.bcfg.fractional_shares,
            )

            if shares <= 0:
                continue

            trade_value = shares * exec_price
            commission = self._commission(trade_value)
            total_cost = trade_value + commission

            if total_cost > portfolio.cash:
                # Reduce shares to fit available cash
                max_affordable = (portfolio.cash - commission) / (exec_price * (1 + self.rcfg.commission_pct))
                shares = int(max_affordable) if not self.bcfg.fractional_shares else max_affordable
                if shares <= 0:
                    continue
                trade_value = shares * exec_price
                commission = self._commission(trade_value)
                total_cost = trade_value + commission

            portfolio.cash -= total_cost

            trade = Trade(
                symbol=sym,
                entry_date=date,
                entry_price=exec_price,
                shares=shares,
                stop_price=stop,
                target_price=target,
            )
            portfolio.open_trades.append(trade)
            logger.debug(
                "ENTRY %s @ %.2f x%.0f shares on %s (stop=%.2f, target=%.2f)",
                sym, exec_price, shares, date.date(), stop, target,
            )

    def _process_exits(
        self,
        portfolio: Portfolio,
        universe: Dict[str, pd.DataFrame],
        date,
        prices: Dict[str, float],
    ) -> None:
        remaining = []
        for trade in portfolio.open_trades:
            sym = trade.symbol
            df = universe.get(sym)
            if df is None or date not in df.index:
                remaining.append(trade)
                continue

            row = df.loc[date]
            open_price = row["open"]
            low_price = row["low"]
            signal = row.get("signal", 0)

            # Determine if we should exit and why
            exit_reason = None

            # Stop hit: check if low pierced stop (intraday)
            if low_price <= trade.stop_price:
                exit_reason = "stop_loss"
                exec_price = self._execution_price(trade.stop_price, "sell")
            # Signal says sell
            elif signal == -1:
                exit_reason = "signal_exit"
                exec_price = self._execution_price(open_price, "sell")
            # Target hit
            elif row["high"] >= trade.target_price:
                exit_reason = "profit_target"
                exec_price = self._execution_price(trade.target_price, "sell")
            else:
                remaining.append(trade)
                continue

            # Settle the trade
            trade.exit_date = date
            trade.exit_price = exec_price
            trade.exit_reason = exit_reason

            trade_value = trade.shares * exec_price
            entry_commission = self._commission(trade.shares * trade.entry_price)
            exit_commission = self._commission(trade_value)
            trade._commission = entry_commission + exit_commission

            proceeds = trade_value - exit_commission
            portfolio.cash += proceeds

            portfolio.closed_trades.append(trade)
            logger.debug(
                "EXIT %s @ %.2f on %s | reason=%s | pnl=%.2f",
                sym, exec_price, date.date(), exit_reason, trade.net_pnl,
            )

        portfolio.open_trades = remaining

    def _force_close_open_trades(
        self,
        portfolio: Portfolio,
        universe: Dict[str, pd.DataFrame],
    ) -> None:
        """Close any trades still open at end of backtest at last available close."""
        remaining = []
        for trade in portfolio.open_trades:
            df = universe.get(trade.symbol)
            if df is None or df.empty:
                remaining.append(trade)
                continue
            last_price = df["close"].iloc[-1]
            exec_price = self._execution_price(last_price, "sell")
            trade.exit_date = df.index[-1]
            trade.exit_price = exec_price
            trade.exit_reason = "end_of_backtest"
            entry_commission = self._commission(trade.shares * trade.entry_price)
            exit_commission = self._commission(trade.shares * exec_price)
            trade._commission = entry_commission + exit_commission
            portfolio.cash += trade.shares * exec_price - exit_commission
            portfolio.closed_trades.append(trade)

        portfolio.open_trades = remaining  # should be empty


# ---------------------------------------------------------------------------
# Trade log builder
# ---------------------------------------------------------------------------

def build_trade_log(portfolio: Portfolio) -> pd.DataFrame:
    """Convert closed trades to a DataFrame for analysis."""
    if not portfolio.closed_trades:
        return pd.DataFrame()
    rows = [t.to_dict() for t in portfolio.closed_trades]
    df = pd.DataFrame(rows)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    return df.sort_values("entry_date").reset_index(drop=True)
