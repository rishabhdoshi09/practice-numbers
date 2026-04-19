"""
Volume Profile Backtesting Engine.

Sliding-window simulation:
  - Build VP on a lookback window, generate signals on the next bar
  - Execute trades at signal entry, manage with stop-loss and target
  - Collect per-trade PnL, then compute aggregate metrics

Metrics returned:
  total_trades, win_rate, avg_rr, avg_win_pct, avg_loss_pct,
  max_drawdown_pct, sharpe_ratio, profit_factor, total_return_pct
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .volume_profile import calculate_volume_profile
from .vp_signals import generate_vp_signals


# ── Tuneable ───────────────────────────────────────────────────────────────────
DEFAULT_LOOKBACK = 40    # bars used to build the VP
DEFAULT_STEP     = 1     # step size between windows (1 = every bar)
MAX_HOLD_BARS    = 20    # close trade after this many bars if not stopped/targeted


def run_vp_backtest(
    df: pd.DataFrame,
    lookback:  int = DEFAULT_LOOKBACK,
    step:      int = DEFAULT_STEP,
    n_bins:    int = 50,
) -> dict:
    """
    Run a sliding-window backtest of VP signals on OHLCV data.

    Args:
        df:       Full OHLCV DataFrame (must have Open/High/Low/Close/Volume)
        lookback: Bars used to compute the volume profile on each window
        step:     How many bars to advance between windows
        n_bins:   VP resolution (number of price bins)

    Returns:
        dict with per-trade list and aggregate metrics
    """
    if len(df) < lookback + MAX_HOLD_BARS + 5:
        return _empty_result()

    trades: list[dict] = []
    min_start = lookback

    i = min_start
    while i < len(df) - MAX_HOLD_BARS - 1:
        window = df.iloc[i - lookback: i]
        try:
            vp      = calculate_volume_profile(window, n_bins=n_bins)
            signals = generate_vp_signals(window, vp)
        except Exception:
            i += step
            continue

        for sig in signals:
            if sig["action"] == "HOLD":
                continue

            entry    = sig["entry"]
            sl       = sig["stop_loss"]
            target   = sig["target_1"]
            action   = sig["action"]
            if sl is None or target is None:
                continue

            # Simulate trade on the next MAX_HOLD_BARS bars
            future = df.iloc[i: i + MAX_HOLD_BARS + 1]
            result = _simulate_trade(action, entry, sl, target, future)
            if result:
                trades.append({
                    "bar_idx":    i,
                    "date":       str(df.index[i].date()) if hasattr(df.index[i], "date") else str(df.index[i]),
                    "action":     action,
                    "setup":      sig["setup"],
                    "entry":      entry,
                    "stop_loss":  sl,
                    "target":     target,
                    "exit_price": result["exit_price"],
                    "exit_bar":   result["exit_bar"],
                    "pnl_pct":    result["pnl_pct"],
                    "won":        result["won"],
                    "rr_achieved": result["rr_achieved"],
                    "confidence": sig["confidence"],
                })
            break  # one trade per window (highest-confidence already first)

        i += step

    return _compute_metrics(trades)


def _simulate_trade(
    action: str,
    entry:  float,
    sl:     float,
    target: float,
    future: pd.DataFrame,
) -> dict | None:
    """
    Simulate a single trade on future bars.
    Returns a result dict or None if data is too short.
    """
    if len(future) < 2:
        return None

    for bar_num, (_, row) in enumerate(future.iterrows()):
        low  = float(row["Low"])
        high = float(row["High"])

        if action == "LONG":
            if low <= sl:
                exit_price = sl
                pnl_pct    = (exit_price - entry) / entry * 100
                rr         = abs(pnl_pct) / max(abs((sl - entry) / entry * 100), 1e-10)
                return {"exit_price": exit_price, "exit_bar": bar_num, "pnl_pct": round(pnl_pct, 3),
                        "won": False, "rr_achieved": round(-rr, 2)}
            if high >= target:
                exit_price = target
                pnl_pct    = (exit_price - entry) / entry * 100
                rr         = abs(pnl_pct) / max(abs((sl - entry) / entry * 100), 1e-10)
                return {"exit_price": exit_price, "exit_bar": bar_num, "pnl_pct": round(pnl_pct, 3),
                        "won": True, "rr_achieved": round(rr, 2)}
        else:  # SHORT
            if high >= sl:
                exit_price = sl
                pnl_pct    = (entry - exit_price) / entry * 100
                rr         = abs(pnl_pct) / max(abs((sl - entry) / entry * 100), 1e-10)
                return {"exit_price": exit_price, "exit_bar": bar_num, "pnl_pct": round(pnl_pct, 3),
                        "won": False, "rr_achieved": round(-rr, 2)}
            if low <= target:
                exit_price = target
                pnl_pct    = (entry - exit_price) / entry * 100
                rr         = abs(pnl_pct) / max(abs((sl - entry) / entry * 100), 1e-10)
                return {"exit_price": exit_price, "exit_bar": bar_num, "pnl_pct": round(pnl_pct, 3),
                        "won": True, "rr_achieved": round(rr, 2)}

    # Time-based exit: close at the last bar's close
    last_close = float(future["Close"].iloc[-1])
    if action == "LONG":
        pnl_pct = (last_close - entry) / entry * 100
    else:
        pnl_pct = (entry - last_close) / entry * 100
    return {
        "exit_price": last_close,
        "exit_bar":   len(future) - 1,
        "pnl_pct":    round(pnl_pct, 3),
        "won":        pnl_pct > 0,
        "rr_achieved": 0.0,
    }


def _compute_metrics(trades: list[dict]) -> dict:
    if not trades:
        return _empty_result()

    pnl_arr  = np.array([t["pnl_pct"] for t in trades])
    wins     = [t for t in trades if t["won"]]
    losses   = [t for t in trades if not t["won"]]

    win_rate = len(wins) / len(trades) if trades else 0

    avg_win  = float(np.mean([t["pnl_pct"] for t in wins]))  if wins   else 0.0
    avg_loss = float(np.mean([t["pnl_pct"] for t in losses])) if losses else 0.0

    gross_profit = sum(t["pnl_pct"] for t in wins)   if wins   else 0.0
    gross_loss   = abs(sum(t["pnl_pct"] for t in losses)) if losses else 1e-10
    profit_factor = round(gross_profit / gross_loss, 2)

    # Equity curve (cumulative product of 1 + pnl%)
    equity = np.cumprod(1 + pnl_arr / 100)
    peak   = np.maximum.accumulate(equity)
    dd     = (peak - equity) / peak
    max_dd = float(dd.max()) * 100

    total_return = float((equity[-1] - 1) * 100) if len(equity) else 0.0

    # Sharpe (daily pnl_pct as returns proxy, rf=0)
    if len(pnl_arr) > 1 and pnl_arr.std() > 0:
        sharpe = float(np.mean(pnl_arr) / np.std(pnl_arr) * np.sqrt(252))
    else:
        sharpe = 0.0

    avg_rr = float(np.mean([t["rr_achieved"] for t in trades]))

    # Setup breakdown
    setup_stats: dict[str, dict] = {}
    for t in trades:
        s = t["setup"]
        if s not in setup_stats:
            setup_stats[s] = {"trades": 0, "wins": 0, "total_pnl": 0.0}
        setup_stats[s]["trades"]    += 1
        setup_stats[s]["wins"]      += int(t["won"])
        setup_stats[s]["total_pnl"] += t["pnl_pct"]
    for s in setup_stats:
        d = setup_stats[s]
        d["win_rate"]  = round(d["wins"] / d["trades"], 3) if d["trades"] else 0
        d["avg_pnl"]   = round(d["total_pnl"] / d["trades"], 3)

    return {
        "total_trades":      len(trades),
        "win_rate":          round(win_rate, 3),
        "avg_rr":            round(avg_rr, 2),
        "avg_win_pct":       round(avg_win,  3),
        "avg_loss_pct":      round(avg_loss, 3),
        "max_drawdown_pct":  round(max_dd, 2),
        "sharpe_ratio":      round(sharpe, 2),
        "profit_factor":     profit_factor,
        "total_return_pct":  round(total_return, 2),
        "setup_breakdown":   setup_stats,
        "trades":            trades[-50:],  # last 50 trades for UI table
    }


def _empty_result() -> dict:
    return {
        "total_trades":     0,
        "win_rate":         0,
        "avg_rr":           0,
        "avg_win_pct":      0,
        "avg_loss_pct":     0,
        "max_drawdown_pct": 0,
        "sharpe_ratio":     0,
        "profit_factor":    0,
        "total_return_pct": 0,
        "setup_breakdown":  {},
        "trades":           [],
    }
