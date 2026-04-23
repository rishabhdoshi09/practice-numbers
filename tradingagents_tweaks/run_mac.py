"""
TradingAgents — Mac runner with Kite data + Groq LLM + NewsData.io news.

Usage:
    python run_mac.py                  # analyzes TODAY automatically
    python run_mac.py RELIANCE         # specific symbol, today's date
    python run_mac.py RELIANCE TCS INFY  # multiple symbols, today

Before first run each day:
    python kite_login.py   ← refreshes Kite access token (expires at midnight IST)
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Credential checks ─────────────────────────────────────────────────────────
missing = []
if not os.environ.get("GROQ_API_KEY"):
    missing.append("GROQ_API_KEY      → https://console.groq.com (free)")
if not os.environ.get("KITE_API_KEY"):
    missing.append("KITE_API_KEY      → https://developers.kite.trade/apps")
if not os.environ.get("KITE_ACCESS_TOKEN"):
    missing.append("KITE_ACCESS_TOKEN → run: python kite_login.py")
if not os.environ.get("NEWSDATA_API_KEY"):
    missing.append("NEWSDATA_API_KEY  → https://newsdata.io (free, optional)")

if missing:
    print("\nMissing credentials in .env:")
    for m in missing:
        print(f"  ✗ {m}")
    if "KITE_ACCESS_TOKEN" in "\n".join(missing) or "GROQ_API_KEY" in "\n".join(missing):
        print("\nSetup: cp .env.mac .env  then fill in values\n")
        sys.exit(1)
    print()  # newsdata is optional — continue anyway

from mac_config import MAC_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


def analyze(symbol: str, date: str):
    print(f"\n{'═'*54}")
    print(f"  Symbol  : {symbol} (NSE via Kite)")
    print(f"  Date    : {date}  ← today")
    print(f"  LLM     : {MAC_CONFIG['llm_provider']} / {MAC_CONFIG['deep_think_llm']}")
    print(f"  Data    : Kite (price) · NewsData.io (news)")
    print(f"{'═'*54}\n")

    ta = TradingAgentsGraph(debug=False, config=MAC_CONFIG)
    _, decision = ta.propagate(symbol, date)

    print(f"\n{'═'*54}")
    print(f"  FINAL DECISION — {symbol}")
    print(f"{'═'*54}")
    print(decision)
    return decision


def main():
    today = datetime.today().strftime("%Y-%m-%d")

    # Symbols from CLI args, or prompt user
    symbols = [s.upper() for s in sys.argv[1:]] if len(sys.argv) > 1 else []
    if not symbols:
        raw = input("Symbol(s) (e.g. RELIANCE  or  RELIANCE TCS INFY): ").strip().upper()
        symbols = raw.split() if raw else ["NIFTY 50"]

    for symbol in symbols:
        analyze(symbol, today)


if __name__ == "__main__":
    main()
