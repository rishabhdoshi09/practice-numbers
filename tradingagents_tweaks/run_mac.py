"""
TradingAgents — Mac runner with Kite data + Groq LLM.

Usage:
    python run_mac.py                             # interactive
    python run_mac.py --symbol RELIANCE --date 2024-11-15
    python run_mac.py --symbol TCS --date 2024-10-01

Symbols: plain NSE format — RELIANCE, TCS, INFY, HDFCBANK
(No .NS suffix needed — Kite uses direct NSE symbols)

Before first run each day:
    python kite_login.py   ← refreshes access token
"""

import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ── Credential checks ─────────────────────────────────────────────────────────
missing = []
if not os.environ.get("GROQ_API_KEY"):
    missing.append("GROQ_API_KEY  (get free key at https://console.groq.com)")
if not os.environ.get("KITE_API_KEY"):
    missing.append("KITE_API_KEY  (from https://developers.kite.trade/apps)")
if not os.environ.get("KITE_ACCESS_TOKEN"):
    missing.append("KITE_ACCESS_TOKEN  (run: python kite_login.py)")

if missing:
    print("\nERROR: Missing credentials in .env:")
    for m in missing:
        print(f"  - {m}")
    print("\nSetup: cp .env.mac .env  then fill in values\n")
    sys.exit(1)

# ── Run ───────────────────────────────────────────────────────────────────────
from mac_config import MAC_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


def run(symbol: str, date: str):
    print(f"\n{'═'*52}")
    print(f"  Symbol : {symbol} (NSE via Kite)")
    print(f"  Date   : {date}")
    print(f"  LLM    : {MAC_CONFIG['llm_provider']} / {MAC_CONFIG['deep_think_llm']}")
    print(f"  Data   : Kite (OHLCV) + yfinance (fundamentals/news)")
    print(f"{'═'*52}\n")

    ta = TradingAgentsGraph(debug=False, config=MAC_CONFIG)
    _, decision = ta.propagate(symbol, date)

    print(f"\n{'═'*52}")
    print("  FINAL DECISION")
    print(f"{'═'*52}")
    print(decision)
    return decision


def main():
    parser = argparse.ArgumentParser(description="TradingAgents — Mac (Kite + Groq)")
    parser.add_argument("--symbol", default=None, help="NSE symbol e.g. RELIANCE")
    parser.add_argument("--date",   default=None, help="Date YYYY-MM-DD")
    args = parser.parse_args()

    symbol = args.symbol or input("Symbol (e.g. RELIANCE): ").strip().upper()
    date   = args.date   or input("Date   (e.g. 2024-11-15): ").strip()

    run(symbol, date)


if __name__ == "__main__":
    main()
