"""
Plotting utilities for the trading system.

All plots use matplotlib with a clean, readable style.
Saving to file is preferred over plt.show() for production pipelines.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")   # non-interactive backend — safe for servers/headless
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.dates import DateFormatter
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not installed — plotting disabled")


def _check_mpl():
    if not MATPLOTLIB_AVAILABLE:
        raise ImportError("matplotlib is required for plotting: pip install matplotlib")


def plot_equity_curve(
    equity_series: pd.Series,
    benchmark_series: Optional[pd.Series] = None,
    title: str = "Equity Curve",
    save_path: Optional[str] = None,
) -> None:
    """
    Plot equity curve with drawdown panel.
    Optional benchmark overlay for relative performance.
    """
    _check_mpl()

    fig = plt.figure(figsize=(14, 8))
    gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1], hspace=0.1)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    # Normalise to 100 at start
    norm_equity = equity_series / equity_series.iloc[0] * 100
    ax1.plot(norm_equity.index, norm_equity.values, color="#1f77b4", linewidth=1.5,
             label="Strategy", zorder=3)

    if benchmark_series is not None:
        common = norm_equity.index.intersection(benchmark_series.index)
        if len(common) > 0:
            norm_bench = benchmark_series.loc[common] / benchmark_series.loc[common].iloc[0] * 100
            ax1.plot(norm_bench.index, norm_bench.values, color="#ff7f0e",
                     linewidth=1.2, linestyle="--", label="Benchmark", alpha=0.8)

    ax1.set_ylabel("Normalised Value (base 100)", fontsize=11)
    ax1.set_title(title, fontsize=13, fontweight="bold")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}"))

    # Drawdown panel
    rolling_peak = equity_series.cummax()
    drawdown = (rolling_peak - equity_series) / rolling_peak * 100
    ax2.fill_between(drawdown.index, -drawdown.values, 0, color="#d62728", alpha=0.5)
    ax2.plot(drawdown.index, -drawdown.values, color="#d62728", linewidth=0.8)
    ax2.set_ylabel("Drawdown %", fontsize=10)
    ax2.set_xlabel("Date", fontsize=11)
    ax2.grid(True, alpha=0.3)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))

    plt.setp(ax1.get_xticklabels(), visible=False)

    plt.tight_layout()
    _save_or_show(fig, save_path)


def plot_trade_analysis(trade_log: pd.DataFrame, save_path: Optional[str] = None) -> None:
    """
    4-panel trade analysis chart:
      1. PnL per trade (bar chart)
      2. Return % distribution (histogram)
      3. Holding period distribution
      4. Cumulative trade PnL
    """
    _check_mpl()
    if trade_log.empty:
        logger.warning("No trades to plot")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("Trade Analysis", fontsize=14, fontweight="bold")

    # 1. PnL per trade
    ax = axes[0, 0]
    colors = ["#2ca02c" if p > 0 else "#d62728" for p in trade_log["net_pnl"]]
    ax.bar(range(len(trade_log)), trade_log["net_pnl"].values, color=colors, alpha=0.8)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Net PnL per Trade")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("PnL")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    # 2. Return % distribution
    ax = axes[0, 1]
    returns = trade_log["return_pct"].dropna()
    ax.hist(returns, bins=30, color="#1f77b4", alpha=0.8, edgecolor="white")
    ax.axvline(returns.mean(), color="red", linestyle="--", linewidth=1.2,
               label=f"Mean {returns.mean():.1f}%")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Return % Distribution")
    ax.set_xlabel("Return %")
    ax.set_ylabel("Frequency")
    ax.legend()

    # 3. Holding period distribution
    ax = axes[1, 0]
    ax.hist(trade_log["holding_days"].dropna(), bins=20,
            color="#9467bd", alpha=0.8, edgecolor="white")
    ax.set_title("Holding Period Distribution")
    ax.set_xlabel("Days in Trade")
    ax.set_ylabel("Frequency")

    # 4. Cumulative PnL
    ax = axes[1, 1]
    cumulative = trade_log["net_pnl"].cumsum()
    ax.plot(range(len(cumulative)), cumulative.values, color="#1f77b4", linewidth=1.5)
    ax.fill_between(range(len(cumulative)), cumulative.values, 0,
                    where=(cumulative.values > 0), alpha=0.2, color="#2ca02c")
    ax.fill_between(range(len(cumulative)), cumulative.values, 0,
                    where=(cumulative.values <= 0), alpha=0.2, color="#d62728")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Cumulative PnL")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Cumulative PnL")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    plt.tight_layout()
    _save_or_show(fig, save_path)


def plot_signals(
    df: pd.DataFrame,
    symbol: str,
    save_path: Optional[str] = None,
    last_n_days: int = 252,
) -> None:
    """
    Plot price with MA overlays, buy/sell markers, RSI and volume panel.
    Shows the last `last_n_days` trading days for readability.
    """
    _check_mpl()
    df = df.tail(last_n_days).copy()

    fig = plt.figure(figsize=(14, 10))
    gs = gridspec.GridSpec(3, 1, height_ratios=[4, 1.5, 1.5], hspace=0.1)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax3 = fig.add_subplot(gs[2], sharex=ax1)

    # Price + MAs
    ax1.plot(df.index, df["close"], color="#444", linewidth=1.2, label="Close", zorder=2)
    ma_colors = {"ma_5": "#aec7e8", "ma_10": "#ffbb78", "ma_20": "#1f77b4", "ma_50": "#d62728"}
    for col, color in ma_colors.items():
        if col in df.columns:
            ax1.plot(df.index, df[col], color=color, linewidth=0.9,
                     alpha=0.8, label=col.upper())

    # Entry / exit markers
    if "signal" in df.columns:
        buys = df[df["signal"] == 1]
        sells = df[df["signal"] == -1]
        ax1.scatter(buys.index, buys["close"], marker="^", color="#2ca02c",
                    s=80, zorder=5, label="Buy")
        ax1.scatter(sells.index, sells["close"], marker="v", color="#d62728",
                    s=80, zorder=5, label="Sell")

    ax1.set_title(f"{symbol} — Price & Signals", fontsize=13, fontweight="bold")
    ax1.set_ylabel("Price")
    ax1.legend(loc="upper left", fontsize=8, ncol=3)
    ax1.grid(True, alpha=0.3)

    # RSI
    if "rsi" in df.columns:
        ax2.plot(df.index, df["rsi"], color="#9467bd", linewidth=1.0)
        ax2.axhline(65, color="orange", linestyle="--", linewidth=0.8, alpha=0.7)
        ax2.axhline(75, color="red", linestyle="--", linewidth=0.8, alpha=0.7)
        ax2.axhline(30, color="green", linestyle="--", linewidth=0.8, alpha=0.7)
        ax2.set_ylim(0, 100)
        ax2.set_ylabel("RSI")
        ax2.grid(True, alpha=0.3)

    # Volume
    if "volume" in df.columns:
        vol_color = ["#2ca02c" if c >= o else "#d62728"
                     for c, o in zip(df["close"], df["open"])]
        ax3.bar(df.index, df["volume"] / 1e6, color=vol_color, alpha=0.7)
        if "volume_ratio" in df.columns:
            ax3_twin = ax3.twinx()
            ax3_twin.plot(df.index, df["volume_ratio"], color="navy",
                          linewidth=0.8, alpha=0.6)
            ax3_twin.axhline(1.5, color="navy", linestyle="--",
                             linewidth=0.7, alpha=0.5)
            ax3_twin.set_ylabel("Vol Ratio", fontsize=8, color="navy")
        ax3.set_ylabel("Volume (M)")
        ax3.set_xlabel("Date")
        ax3.grid(True, alpha=0.3)

    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)

    plt.tight_layout()
    _save_or_show(fig, save_path)


def plot_monthly_returns_heatmap(
    equity_series: pd.Series,
    save_path: Optional[str] = None,
) -> None:
    """Monthly returns heatmap (year x month) — the quant's favourite table."""
    _check_mpl()

    monthly = equity_series.resample("ME").last().pct_change().dropna() * 100
    monthly.index = pd.to_datetime(monthly.index)

    pivot = pd.DataFrame({
        "year": monthly.index.year,
        "month": monthly.index.month,
        "return": monthly.values,
    }).pivot(index="year", columns="month", values="return")

    pivot.columns = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:len(pivot.columns)]

    fig, ax = plt.subplots(figsize=(14, max(4, len(pivot) * 0.6 + 1)))

    vmax = max(abs(pivot.values[~np.isnan(pivot.values)].max()), 1)
    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto",
                   vmin=-vmax, vmax=vmax)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=10)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=10)

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                        fontsize=8, color="black" if abs(val) < vmax * 0.7 else "white")

    plt.colorbar(im, ax=ax, label="Monthly Return %")
    ax.set_title("Monthly Returns Heatmap", fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save_or_show(fig, save_path)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _save_or_show(fig, save_path: Optional[str]) -> None:
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info("Plot saved: %s", save_path)
    plt.close(fig)
