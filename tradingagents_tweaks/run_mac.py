"""
TradingAgents — Mac runner.

Usage:
    python run_mac.py                            # interactive: asks symbol + date
    python run_mac.py --symbol RELIANCE.NS --date 2024-11-15
    python run_mac.py --symbol TCS.NS --date 2024-10-01

Indian stocks: use .NS suffix  (e.g. RELIANCE.NS, TCS.NS, INFY.NS)
"""

import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("GROQ_API_KEY"):
    print("\nERROR: GROQ_API_KEY not set.")
    print("  1. Get free key: https://console.groq.com")
    print("  2. cp .env.mac .env  and paste your key\n")
    sys.exit(1)

from mac_config import MAC_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


def run(symbol: str, date: str):
    print(f"\nAnalyzing {symbol} on {date}")
    print(f"LLM: {MAC_CONFIG['llm_provider']} / {MAC_CONFIG['deep_think_llm']}")
    print(f"Debate rounds: {MAC_CONFIG['max_debate_rounds']} (RAM-safe mode)\n")

    ta = TradingAgentsGraph(debug=False, config=MAC_CONFIG)
    state, decision = ta.propagate(symbol, date)

    print("\n" + "═" * 50)
    print("FINAL DECISION")
    print("═" * 50)
    print(decision)
    return decision


def main():
    parser = argparse.ArgumentParser(description="TradingAgents — Mac (Groq)")
    parser.add_argument("--symbol", default=None, help="e.g. RELIANCE.NS")
    parser.add_argument("--date",   default=None, help="YYYY-MM-DD")
    args = parser.parse_args()

    symbol = args.symbol or input("Enter symbol (e.g. RELIANCE.NS): ").strip()
    date   = args.date   or input("Enter date   (e.g. 2024-11-15):  ").strip()

    run(symbol, date)


if __name__ == "__main__":
    main()
