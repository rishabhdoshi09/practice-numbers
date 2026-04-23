"""
Central configuration for the trading system.
All tuneable parameters live here — never scatter magic numbers through modules.
"""

import os
from dataclasses import dataclass, field
from typing import List


def _default_symbols() -> List[str]:
    # Kite uses plain NSE symbols; yfinance needs .NS suffix
    if os.environ.get("KITE_API_KEY") and os.environ.get("KITE_ACCESS_TOKEN"):
        return ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
    return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]


@dataclass
class DataConfig:
    symbols: List[str] = field(default_factory=_default_symbols)
    start_date: str = "2019-01-01"
    end_date: str = "2024-12-31"
    interval: str = "1d"
    # Minimum trading days required before first signal
    warmup_period: int = 60


@dataclass
class FeatureConfig:
    ma_windows: List[int] = field(default_factory=lambda: [5, 10, 20, 50])
    rsi_period: int = 14
    atr_period: int = 14
    volatility_window: int = 20
    volume_spike_window: int = 20
    volume_spike_threshold: float = 1.5   # ratio vs rolling mean


@dataclass
class StrategyConfig:
    """
    Dual-MA crossover + RSI filter + ATR-based trailing stop.

    Entry:  fast_ma crosses above slow_ma AND rsi < rsi_entry_max
    Exit:   fast_ma crosses below slow_ma OR rsi > rsi_exit_overbought
            OR price falls below ATR trailing stop
    """
    fast_ma: int = 20
    slow_ma: int = 50
    rsi_entry_max: float = 65.0      # avoid buying into overbought conditions
    rsi_exit_overbought: float = 75.0
    atr_stop_multiplier: float = 2.0  # trailing stop = entry - 2*ATR
    profit_target_r: float = 3.0      # take profit at 3R (3x initial risk)


@dataclass
class RiskConfig:
    initial_capital: float = 1_000_000.0   # INR 10 lakh
    risk_per_trade: float = 0.01           # 1% of equity at risk per trade
    max_portfolio_heat: float = 0.06       # max 6% of equity at risk at once
    max_drawdown_limit: float = 0.20       # halt trading at 20% drawdown
    max_positions: int = 5
    commission_pct: float = 0.001          # 0.1% per side (brokerage + STT approx)
    slippage_pct: float = 0.0005           # 0.05% per side


@dataclass
class BacktestConfig:
    # Whether to allow fractional shares
    fractional_shares: bool = False


@dataclass
class TradingConfig:
    data: DataConfig = field(default_factory=DataConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)


# Default singleton — import this everywhere
CONFIG = TradingConfig()
