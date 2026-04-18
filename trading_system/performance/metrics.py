"""
Performance metrics and interpretation.

METRICS COMPUTED
----------------
Total Return         — absolute % gain over the period. Context: compare to buy-and-hold.

CAGR                 — compounded annual growth rate. Normalises across different
                       test periods, making results comparable.

Sharpe Ratio         — (mean excess return) / (std of returns). The classic
                       risk-adjusted metric. Rule of thumb: >1.0 is acceptable,
                       >2.0 is excellent for a systematic strategy.

Sortino Ratio        — like Sharpe but penalises only downside volatility. More
                       meaningful for strategies with positive skew (trend-following).

Calmar Ratio         — CAGR / max_drawdown. Measures return per unit of worst pain.
                       >1.0 is good. A strategy with 20% CAGR and 20% max drawdown
                       has Calmar=1.0.

Max Drawdown         — largest peak-to-trough decline. The single most important
                       risk metric from a practitioner standpoint.

Win Rate             — % of trades that are profitable. Trend-following typically
                       has 40–50% win rate with a high win/loss ratio.

Avg Win / Avg Loss   — reward/risk ratio per trade. A win rate of 40% with
                       avg win = 2x avg loss still gives a positive expectancy.

Expectancy           — (win_rate * avg_win) + (loss_rate * avg_loss). The average
                       expected profit per trade. Must be > 0 for the strategy
                       to have edge.

Profit Factor        — gross_profit / |gross_loss|. > 1.5 is solid.

R-multiple stats     — each trade's PnL expressed as multiples of the initial risk.
                       Normalises across different position sizes and volatile regimes.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_metrics(
    equity_series: pd.Series,
    trade_log: pd.DataFrame,
    risk_free_rate: float = 0.065,   # ~RBI repo rate
) -> dict:
    """
    Compute the full set of performance metrics.

    Args:
        equity_series:  daily equity indexed by date
        trade_log:      DataFrame from build_trade_log()
        risk_free_rate: annualised risk-free rate (default 6.5% for India)

    Returns:
        dict of metric_name -> value (rounded appropriately)
    """
    if equity_series.empty:
        logger.warning("Empty equity series — cannot compute metrics")
        return {}

    metrics = {}

    # --- Return metrics ---
    initial = equity_series.iloc[0]
    final = equity_series.iloc[-1]
    total_return = (final / initial - 1) * 100

    n_days = (equity_series.index[-1] - equity_series.index[0]).days
    n_years = max(n_days / 365.25, 1 / 365.25)
    cagr = ((final / initial) ** (1 / n_years) - 1) * 100

    metrics["initial_capital"] = round(initial, 2)
    metrics["final_equity"] = round(final, 2)
    metrics["total_return_pct"] = round(total_return, 2)
    metrics["cagr_pct"] = round(cagr, 2)
    metrics["n_trading_days"] = len(equity_series)
    metrics["period_years"] = round(n_years, 2)

    # --- Daily return series ---
    daily_returns = equity_series.pct_change().dropna()
    rf_daily = risk_free_rate / 252

    # --- Sharpe ---
    excess = daily_returns - rf_daily
    sharpe = (excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0.0
    metrics["sharpe_ratio"] = round(sharpe, 3)

    # --- Sortino ---
    downside = daily_returns[daily_returns < rf_daily] - rf_daily
    sortino_denom = np.sqrt((downside ** 2).mean()) * np.sqrt(252) if len(downside) > 0 else np.nan
    sortino = (excess.mean() * 252 / sortino_denom) if sortino_denom and sortino_denom > 0 else 0.0
    metrics["sortino_ratio"] = round(sortino, 3)

    # --- Drawdown ---
    rolling_peak = equity_series.cummax()
    drawdown_series = (rolling_peak - equity_series) / rolling_peak
    max_dd = drawdown_series.max() * 100

    # Max drawdown duration (consecutive days in drawdown > 1%)
    in_dd = (drawdown_series > 0.01).astype(int)
    dd_streaks = _max_consecutive(in_dd)

    metrics["max_drawdown_pct"] = round(max_dd, 2)
    metrics["max_drawdown_duration_days"] = dd_streaks
    metrics["calmar_ratio"] = round(cagr / max_dd, 3) if max_dd > 0 else np.inf

    # --- Volatility ---
    ann_vol = daily_returns.std() * np.sqrt(252) * 100
    metrics["annual_volatility_pct"] = round(ann_vol, 2)

    # --- Trade-level metrics ---
    if not trade_log.empty:
        _add_trade_metrics(metrics, trade_log, initial)
    else:
        metrics["n_trades"] = 0
        logger.warning("No closed trades to compute trade-level metrics")

    return metrics


def _add_trade_metrics(metrics: dict, trade_log: pd.DataFrame, initial_capital: float) -> None:
    n = len(trade_log)
    winners = trade_log[trade_log["net_pnl"] > 0]
    losers = trade_log[trade_log["net_pnl"] <= 0]

    win_rate = len(winners) / n * 100
    avg_win = winners["net_pnl"].mean() if len(winners) else 0.0
    avg_loss = losers["net_pnl"].mean() if len(losers) else 0.0
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else np.inf

    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

    gross_profit = winners["net_pnl"].sum()
    gross_loss = abs(losers["net_pnl"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

    avg_holding = trade_log["holding_days"].mean()
    total_commission = trade_log["commission"].sum()

    # R-multiples
    if "return_pct" in trade_log.columns:
        r_multiples = trade_log["return_pct"]
        avg_r = r_multiples.mean()
        std_r = r_multiples.std()
    else:
        avg_r = std_r = np.nan

    metrics.update({
        "n_trades": n,
        "win_rate_pct": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "win_loss_ratio": round(win_loss_ratio, 3),
        "expectancy_per_trade": round(expectancy, 2),
        "profit_factor": round(profit_factor, 3),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(-gross_loss, 2),
        "net_profit": round(gross_profit - gross_loss, 2),
        "total_commission_paid": round(total_commission, 2),
        "avg_holding_days": round(avg_holding, 1),
        "avg_return_pct_per_trade": round(avg_r, 3),
        "std_return_pct_per_trade": round(std_r, 3),
        "best_trade_pct": round(trade_log["return_pct"].max(), 2),
        "worst_trade_pct": round(trade_log["return_pct"].min(), 2),
    })


def _max_consecutive(s: pd.Series) -> int:
    """Return the maximum run of consecutive 1s in a binary series."""
    max_run = 0
    current = 0
    for v in s:
        if v:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return max_run


def compare_to_benchmark(
    equity_series: pd.Series,
    benchmark_close: pd.Series,
) -> dict:
    """
    Compare strategy equity curve to a buy-and-hold benchmark.

    Args:
        equity_series:    strategy daily equity
        benchmark_close:  benchmark price series (e.g., NIFTY 50 close)

    Returns:
        dict with alpha, beta, correlation, and relative metrics
    """
    bench_returns = benchmark_close.pct_change().dropna()
    strat_returns = equity_series.pct_change().dropna()

    # Align on common dates
    common = strat_returns.index.intersection(bench_returns.index)
    if len(common) < 10:
        return {"error": "insufficient overlapping data"}

    sr = strat_returns.loc[common]
    br = bench_returns.loc[common]

    beta = np.cov(sr, br)[0, 1] / np.var(br) if np.var(br) > 0 else np.nan
    correlation = sr.corr(br)

    bench_total = (benchmark_close.loc[common].iloc[-1] / benchmark_close.loc[common].iloc[0] - 1) * 100
    strat_total = (equity_series.loc[common].iloc[-1] / equity_series.loc[common].iloc[0] - 1) * 100
    alpha = strat_total - bench_total

    return {
        "benchmark_total_return_pct": round(bench_total, 2),
        "strategy_total_return_pct": round(strat_total, 2),
        "alpha_pct": round(alpha, 2),
        "beta": round(beta, 3) if not np.isnan(beta) else None,
        "correlation_with_benchmark": round(correlation, 3),
    }


def format_report(metrics: dict) -> str:
    """Pretty-print metrics as a formatted report string."""
    lines = [
        "=" * 55,
        "          TRADING SYSTEM PERFORMANCE REPORT",
        "=" * 55,
        "",
        "  RETURNS",
        f"    Initial Capital     : {metrics.get('initial_capital', 0):>15,.2f}",
        f"    Final Equity        : {metrics.get('final_equity', 0):>15,.2f}",
        f"    Total Return        : {metrics.get('total_return_pct', 0):>14.2f}%",
        f"    CAGR                : {metrics.get('cagr_pct', 0):>14.2f}%",
        f"    Annual Volatility   : {metrics.get('annual_volatility_pct', 0):>14.2f}%",
        "",
        "  RISK-ADJUSTED",
        f"    Sharpe Ratio        : {metrics.get('sharpe_ratio', 0):>15.3f}",
        f"    Sortino Ratio       : {metrics.get('sortino_ratio', 0):>15.3f}",
        f"    Calmar Ratio        : {metrics.get('calmar_ratio', 0):>15.3f}",
        f"    Max Drawdown        : {metrics.get('max_drawdown_pct', 0):>14.2f}%",
        f"    Max DD Duration     : {metrics.get('max_drawdown_duration_days', 0):>12d} days",
        "",
        "  TRADE STATISTICS",
        f"    Total Trades        : {metrics.get('n_trades', 0):>15d}",
        f"    Win Rate            : {metrics.get('win_rate_pct', 0):>14.2f}%",
        f"    Avg Win             : {metrics.get('avg_win', 0):>15,.2f}",
        f"    Avg Loss            : {metrics.get('avg_loss', 0):>15,.2f}",
        f"    Win/Loss Ratio      : {metrics.get('win_loss_ratio', 0):>15.3f}",
        f"    Expectancy/Trade    : {metrics.get('expectancy_per_trade', 0):>15,.2f}",
        f"    Profit Factor       : {metrics.get('profit_factor', 0):>15.3f}",
        f"    Avg Holding Days    : {metrics.get('avg_holding_days', 0):>15.1f}",
        f"    Total Commission    : {metrics.get('total_commission_paid', 0):>15,.2f}",
        "",
        "  BEST / WORST TRADE",
        f"    Best Trade          : {metrics.get('best_trade_pct', 0):>14.2f}%",
        f"    Worst Trade         : {metrics.get('worst_trade_pct', 0):>14.2f}%",
        "=" * 55,
    ]
    return "\n".join(lines)
