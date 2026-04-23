"""
LLM-enhanced trading analysis pipeline.

Runs the full quant pipeline first, then for every BUY signal passes the bar
through 4 LLM agents (Technical, Sentiment, Risk, Decision) via Groq (free).

Usage:
    # 1. Copy .env.example to .env and add your GROQ_API_KEY
    # 2. Run:
    python run_llm.py
    python run_llm.py --symbols "RELIANCE.NS,TCS.NS" --start 2024-01-01

Requirements:
    pip install openai python-dotenv
    (plus existing: yfinance pandas numpy matplotlib)
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Colour helpers (terminal output) ──────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def _col(text, colour): return f"{colour}{text}{RESET}"


def run(cfg=None):
    from trading_system.config import CONFIG
    from trading_system.data.ingestion import fetch_universe, data_quality_report
    from trading_system.features.engineering import add_features_universe
    from trading_system.strategy.signals import generate_signals_universe
    from trading_system.risk.management import RiskManager
    from trading_system.agents.orchestrator import AgentOrchestrator

    if cfg is None:
        cfg = CONFIG

    if not os.environ.get("GROQ_API_KEY"):
        print(_col("\nERROR: GROQ_API_KEY not set.", RED))
        print("  1. Get a free key at https://console.groq.com")
        print("  2. Copy .env.example to .env and paste your key")
        print("  3. Re-run this script\n")
        sys.exit(1)

    # ── Quant pipeline ────────────────────────────────────────────────────────
    print(_col("\n══ STEP 1: Data Ingestion ══", BOLD))
    universe = fetch_universe(
        cfg.data.symbols, cfg.data.start_date, cfg.data.end_date, cfg.data.interval
    )
    print(data_quality_report(universe).to_string())

    print(_col("\n══ STEP 2: Feature Engineering ══", BOLD))
    featured = add_features_universe(universe, cfg.features)

    print(_col("\n══ STEP 3: Signal Generation ══", BOLD))
    signaled = generate_signals_universe(featured, cfg.strategy, warmup=cfg.data.warmup_period)

    risk_manager = RiskManager(cfg.risk)

    # ── Collect all BUY signals ───────────────────────────────────────────────
    buy_signals = []
    for sym, df in signaled.items():
        buy_bars = df[df["signal"] == 1].copy()
        for date, row in buy_bars.iterrows():
            buy_signals.append((date, sym, row))

    buy_signals.sort(key=lambda x: x[0])

    print(_col(f"\n══ STEP 4: LLM Agent Analysis ({len(buy_signals)} BUY signals) ══", BOLD))

    if not buy_signals:
        print("No BUY signals found in the date range. Try a wider date range.")
        return

    orchestrator = AgentOrchestrator()

    # Analyse the 5 most recent signals to stay within free-tier rate limits
    recent_signals = buy_signals[-5:]
    print(f"Analysing {len(recent_signals)} most recent signals (rate-limit safe)...\n")

    results = []
    equity = cfg.risk.initial_capital
    max_dd = 0.0

    for date, sym, row in recent_signals:
        print(_col(f"─── {sym}  {date.date()} ───────────────────────────────", CYAN))

        try:
            result = orchestrator.analyze(
                symbol=sym,
                row=row,
                quant_signal=1,
                equity=equity,
                portfolio_heat=0.02,
                open_positions=1,
                max_drawdown_pct=max_dd,
                strategy_cfg=cfg.strategy,
            )
        except Exception as exc:
            logger.error("Agent error for %s: %s", sym, exc)
            print(_col(f"  Agent error: {exc}", RED))
            continue

        _print_result(result)
        results.append((date, sym, result))
        print()

    # ── Summary table ─────────────────────────────────────────────────────────
    _print_summary(results)
    return results


def _print_result(r: dict):
    sym = r["symbol"]
    tech = r["technical"]
    sent = r["sentiment"]
    risk = r["risk"]
    dec  = r["decision"]

    view_colour = {
        "BULLISH": GREEN, "BEARISH": RED, "POSITIVE": GREEN,
        "NEGATIVE": RED, "NEUTRAL": YELLOW,
    }
    assess_colour = {"ACCEPTABLE": GREEN, "HIGH": YELLOW, "EXCESSIVE": RED}
    dec_colour    = {"BUY": GREEN, "SELL": RED, "HOLD": YELLOW}

    def vc(val, mapping): return _col(val, mapping.get(val, RESET))

    print(f"  Technical  : {vc(tech.get('view','?'), view_colour)} "
          f"[{tech.get('confidence','?')}]  — {tech.get('reason','')}")
    print(f"  Sentiment  : {vc(sent.get('view','?'), view_colour)} "
          f"[{sent.get('confidence','?')}]  — {sent.get('reason','')}")
    print(f"  Risk       : {vc(risk.get('assessment','?'), assess_colour)} "
          f"[{risk.get('confidence','?')}]  — {risk.get('reason','')}")
    print(f"  {_col('DECISION', BOLD)}   : {vc(dec.get('decision','?'), dec_colour)} "
          f"[{dec.get('confidence','?')}]  — {dec.get('reason','')}")


def _print_summary(results):
    if not results:
        return
    print(_col("══ SUMMARY ══════════════════════════════════════════════", BOLD))
    print(f"  {'Date':<12} {'Symbol':<15} {'Technical':<10} {'Sentiment':<10} "
          f"{'Risk':<12} {'DECISION':<8} {'Confidence'}")
    print("  " + "─" * 78)
    for date, sym, r in results:
        tech_view = r["technical"].get("view", "?")[:7]
        sent_view = r["sentiment"].get("view", "?")[:7]
        risk_val  = r["risk"].get("assessment", "?")[:10]
        decision  = r["decision"].get("decision", "?")
        conf      = r["decision"].get("confidence", "?")
        print(f"  {str(date.date()):<12} {sym:<15} {tech_view:<10} {sent_view:<10} "
              f"{risk_val:<12} {decision:<8} {conf}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LLM-enhanced trading analysis")
    parser.add_argument("--symbols", default=None, help="Comma-separated symbols")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    args = parser.parse_args()

    from trading_system.config import CONFIG

    if args.symbols:
        CONFIG.data.symbols = [s.strip() for s in args.symbols.split(",")]
    if args.start:
        CONFIG.data.start_date = args.start
    if args.end:
        CONFIG.data.end_date = args.end

    try:
        run(CONFIG)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
