"""
Trading System — Main Orchestrator

Execution pipeline:
  1. Load config
  2. Fetch OHLCV data for all symbols
  3. Engineer features
  4. Generate signals (no look-ahead)
  5. Run backtest (execution lag = 1 day, with costs/slippage)
  6. Compute performance metrics
  7. Print report + generate plots

Usage:
    python -m trading_system.main               # use defaults from config.py
    python -m trading_system.main --symbols RELIANCE.NS,TCS.NS --start 2020-01-01
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Configure logging before importing submodules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run(cfg=None):
    """
    Main pipeline entry point.

    Args:
        cfg: TradingConfig instance. If None, defaults from config.py are used.
    """
    from trading_system.config import CONFIG, TradingConfig
    from trading_system.data.ingestion import fetch_universe, data_quality_report
    from trading_system.features.engineering import add_features_universe, feature_summary
    from trading_system.strategy.signals import generate_signals_universe, signal_summary
    from trading_system.backtest.engine import BacktestEngine, build_trade_log
    from trading_system.risk.management import RiskManager
    from trading_system.performance.metrics import compute_metrics, format_report, compare_to_benchmark
    from trading_system.utils.plotting import (
        plot_equity_curve, plot_trade_analysis,
        plot_signals, plot_monthly_returns_heatmap,
    )

    if cfg is None:
        cfg = CONFIG

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # 1. DATA INGESTION
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 1: Data Ingestion")
    logger.info("=" * 60)

    universe = fetch_universe(
        cfg.data.symbols,
        cfg.data.start_date,
        cfg.data.end_date,
        cfg.data.interval,
    )

    quality = data_quality_report(universe)
    print("\n[Data Quality Report]")
    print(quality.to_string())
    print()

    # ------------------------------------------------------------------
    # 2. FEATURE ENGINEERING
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 2: Feature Engineering")
    logger.info("=" * 60)

    featured = add_features_universe(universe, cfg.features)

    # Print a quick feature diagnostics for first symbol
    first_sym = list(featured.keys())[0]
    print(f"\n[Feature Summary for {first_sym}]")
    print(feature_summary(featured[first_sym]).head(10).to_string())
    print()

    # ------------------------------------------------------------------
    # 3. SIGNAL GENERATION
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 3: Signal Generation")
    logger.info("=" * 60)

    signaled = generate_signals_universe(
        featured,
        cfg.strategy,
        warmup=cfg.data.warmup_period,
    )

    print("\n[Signal Summary]")
    print(signal_summary(signaled).to_string())
    print()

    # Plot signals for first symbol
    plot_signals(
        signaled[first_sym],
        first_sym,
        save_path=str(output_dir / f"signals_{first_sym.replace('.', '_')}.png"),
    )

    # ------------------------------------------------------------------
    # 4. BACKTEST
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 4: Backtesting")
    logger.info("=" * 60)

    risk_manager = RiskManager(cfg.risk)
    engine = BacktestEngine(cfg.risk, cfg.backtest)
    portfolio, equity_df = engine.run(signaled, risk_manager)

    trade_log = build_trade_log(portfolio)
    print(f"\n[Closed Trades: {len(trade_log)}]")
    if not trade_log.empty:
        display_cols = [
            "symbol", "entry_date", "entry_price", "exit_date",
            "exit_price", "shares", "net_pnl", "return_pct",
            "holding_days", "exit_reason",
        ]
        print(trade_log[display_cols].head(20).to_string(index=False))
        if len(trade_log) > 20:
            print(f"  ... and {len(trade_log) - 20} more trades.")

    # Save trade log to CSV
    if not trade_log.empty:
        trade_log.to_csv(output_dir / "trade_log.csv", index=False)
        logger.info("Trade log saved to outputs/trade_log.csv")

    # ------------------------------------------------------------------
    # 5. PERFORMANCE METRICS
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 5: Performance Metrics")
    logger.info("=" * 60)

    metrics = compute_metrics(
        equity_df["equity"],
        trade_log,
        risk_free_rate=0.065,
    )

    print("\n" + format_report(metrics))

    # Save metrics
    pd.Series(metrics).to_csv(output_dir / "metrics.csv", header=["value"])

    # ------------------------------------------------------------------
    # 6. BENCHMARK COMPARISON (optional — fetch Nifty 50)
    # ------------------------------------------------------------------
    benchmark = _fetch_benchmark(cfg.data.start_date, cfg.data.end_date)
    if benchmark is not None:
        bmark_result = compare_to_benchmark(equity_df["equity"], benchmark)
        print("\n[Benchmark Comparison vs Nifty 50]")
        for k, v in bmark_result.items():
            print(f"  {k:<40}: {v}")

    # ------------------------------------------------------------------
    # 7. PLOTS
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 6: Generating Plots")
    logger.info("=" * 60)

    plot_equity_curve(
        equity_df["equity"],
        benchmark_series=benchmark,
        title="Strategy Equity Curve vs Nifty 50",
        save_path=str(output_dir / "equity_curve.png"),
    )

    if not trade_log.empty:
        plot_trade_analysis(
            trade_log,
            save_path=str(output_dir / "trade_analysis.png"),
        )

    plot_monthly_returns_heatmap(
        equity_df["equity"],
        save_path=str(output_dir / "monthly_returns.png"),
    )

    logger.info("All outputs saved to: %s/", output_dir)
    print(f"\nOutputs saved to: {output_dir.resolve()}/")

    return portfolio, equity_df, trade_log, metrics


def _fetch_benchmark(start: str, end: str) -> pd.Series:
    """Fetch Nifty 50 as benchmark. Returns None on failure."""
    try:
        import yfinance as yf
        ticker = yf.Ticker("^NSEI")
        data = ticker.history(start=start, end=end, interval="1d", auto_adjust=True)
        if data.empty:
            return None
        s = data["Close"]
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
        s.index.name = "date"
        return s
    except Exception as exc:
        logger.warning("Could not fetch benchmark: %s", exc)
        return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Quantitative Trading System")
    parser.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated list of symbols (e.g. RELIANCE.NS,TCS.NS)",
    )
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=None, help="Initial capital")
    parser.add_argument("--risk", type=float, default=None, help="Risk per trade (e.g. 0.01)")
    args = parser.parse_args()

    from trading_system.config import CONFIG

    if args.symbols:
        CONFIG.data.symbols = [s.strip() for s in args.symbols.split(",")]
    if args.start:
        CONFIG.data.start_date = args.start
    if args.end:
        CONFIG.data.end_date = args.end
    if args.capital:
        CONFIG.risk.initial_capital = args.capital
    if args.risk:
        CONFIG.risk.risk_per_trade = args.risk

    try:
        run(CONFIG)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
