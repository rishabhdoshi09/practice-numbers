"""
Strategy: Dual-MA Crossover with RSI Filter and ATR Trailing Stop

RATIONALE
---------
We implement a TREND-FOLLOWING strategy rather than mean-reversion because:
  1. Equity markets exhibit momentum at the 1–12 month horizon (well-documented)
  2. Trend-following has positive skew (small losses, large gains) — fits risk profile
  3. Mean-reversion fails badly in strong trending regimes (2020, 2023 bull runs)

ENTRY LOGIC
-----------
  Buy when ALL of the following are true ON THE SAME BAR:
    (a) fast_ma crosses above slow_ma  (trend confirmation)
    (b) RSI < rsi_entry_max            (not already overbought — avoids chasing tops)
    (c) volume_ratio >= 1.0            (at least average volume — conviction filter)
    (d) close > ma_50                  (price is above long-term average — bull regime)

  The crossover is detected as:
    prev_bar: fast_ma <= slow_ma
    curr_bar: fast_ma >  slow_ma

EXIT LOGIC (precedence order)
-------------------------------
  1. STOP LOSS (hard):  close < entry_price - atr_stop_multiplier * ATR_at_entry
  2. PROFIT TARGET:     close > entry_price + profit_target_r * initial_risk
  3. TREND EXIT:        fast_ma crosses below slow_ma
  4. OVERBOUGHT EXIT:   RSI > rsi_exit_overbought

ANTI-OVERFITTING MEASURES
--------------------------
  - No parameter optimised in-sample — all values have economic justification
  - Signals are evaluated on t+1 open (execution lag = 1 day)
  - Stop loss is ATR-based (adapts to volatility, not a fixed % picked to maximise returns)
  - RSI filter prevents entries at parabolic tops

SIGNAL VALUES
-------------
  +1  = BUY (go long)
   0  = HOLD / FLAT
  -1  = SELL (exit long)

IMPORTANT: raw_signal is generated on bar t.
           The execution signal is raw_signal.shift(1) — traded at bar t+1 open.
           This prevents look-ahead bias.
"""

import logging
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from trading_system.config import StrategyConfig, FeatureConfig

logger = logging.getLogger(__name__)

# Convenience type alias
SignalDF = pd.DataFrame  # DataFrame with a 'signal' column among others


def generate_signals(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """
    Generate BUY/SELL/HOLD signals for a single-symbol feature DataFrame.

    Returns the input DataFrame with additional columns:
      raw_signal      — signal computed on bar t (0/+1/-1)
      signal          — raw_signal shifted by 1 (executed on t+1 open; no look-ahead)
      stop_price      — stop loss level at time of entry (carried forward while in trade)
      target_price    — profit target at time of entry (carried forward while in trade)
      in_trade        — 1 if a position is currently open, else 0
    """
    fast_col = f"ma_{cfg.fast_ma}"
    slow_col = f"ma_{cfg.slow_ma}"

    _require_columns(df, [fast_col, slow_col, "rsi", "atr", "volume_ratio", "close"])

    n = len(df)
    raw_signal = np.zeros(n, dtype=int)

    fast = df[fast_col].values
    slow = df[slow_col].values
    rsi = df["rsi"].values
    close = df["close"].values
    atr = df["atr"].values
    vol_ratio = df["volume_ratio"].values
    ma50 = df["ma_50"].values

    in_trade = False
    stop_price_arr = np.full(n, np.nan)
    target_price_arr = np.full(n, np.nan)
    in_trade_arr = np.zeros(n, dtype=int)

    entry_price = np.nan
    entry_stop = np.nan
    entry_target = np.nan

    for i in range(1, n):
        # Skip if any indicator is NaN (warm-up)
        if np.isnan(fast[i]) or np.isnan(slow[i]) or np.isnan(rsi[i]) or np.isnan(atr[i]):
            continue

        if not in_trade:
            # --- ENTRY CHECK ---
            bullish_crossover = (fast[i - 1] <= slow[i - 1]) and (fast[i] > slow[i])
            rsi_ok = rsi[i] < cfg.rsi_entry_max
            volume_ok = (not np.isnan(vol_ratio[i])) and (vol_ratio[i] >= 1.0)
            above_trend = (not np.isnan(ma50[i])) and (close[i] > ma50[i])

            if bullish_crossover and rsi_ok and volume_ok and above_trend:
                raw_signal[i] = 1
                in_trade = True
                entry_price = close[i]
                initial_risk = cfg.atr_stop_multiplier * atr[i]
                entry_stop = entry_price - initial_risk
                entry_target = entry_price + cfg.profit_target_r * initial_risk

        else:
            # --- EXIT CHECK ---
            stop_price_arr[i] = entry_stop
            target_price_arr[i] = entry_target
            in_trade_arr[i] = 1

            hit_stop = close[i] < entry_stop
            hit_target = close[i] >= entry_target
            bearish_crossover = (fast[i - 1] >= slow[i - 1]) and (fast[i] < slow[i])
            overbought_exit = rsi[i] > cfg.rsi_exit_overbought

            if hit_stop or hit_target or bearish_crossover or overbought_exit:
                raw_signal[i] = -1
                in_trade = False
                entry_price = np.nan
                entry_stop = np.nan
                entry_target = np.nan

    result = df.copy()
    result["raw_signal"] = raw_signal
    result["stop_price"] = stop_price_arr
    result["target_price"] = target_price_arr
    result["in_trade"] = in_trade_arr

    # Execution lag: signal generated on bar t is acted on bar t+1
    result["signal"] = result["raw_signal"].shift(1).fillna(0).astype(int)

    logger.info(
        "Signals: %d entries, %d exits",
        (result["raw_signal"] == 1).sum(),
        (result["raw_signal"] == -1).sum(),
    )
    return result


def generate_signals_universe(
    universe: Dict[str, pd.DataFrame],
    cfg: StrategyConfig,
    warmup: int = 60,
) -> Dict[str, pd.DataFrame]:
    """Apply signal generation to all symbols, dropping the warm-up period."""
    result = {}
    for sym, df in universe.items():
        try:
            sig_df = generate_signals(df, cfg)
            # Drop warm-up rows where indicators are undefined
            result[sym] = sig_df.iloc[warmup:].copy()
            logger.info("%s: %d signal bars", sym, len(result[sym]))
        except Exception as exc:
            logger.error("Signal generation failed for %s: %s", sym, exc)
    return result


def signal_summary(universe: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Quick summary of signal distribution per symbol."""
    rows = []
    for sym, df in universe.items():
        if "signal" not in df.columns:
            continue
        rows.append({
            "symbol": sym,
            "total_bars": len(df),
            "buy_signals": (df["signal"] == 1).sum(),
            "sell_signals": (df["signal"] == -1).sum(),
            "hold_bars": (df["signal"] == 0).sum(),
        })
    return pd.DataFrame(rows).set_index("symbol")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_columns(df: pd.DataFrame, cols: list) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")
