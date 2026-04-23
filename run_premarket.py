"""
Pre-market morning briefing.

Fetches global market data automatically (SGX Nifty, US futures, Crude, Gold, DXY)
and prints a structured briefing with today's market bias.

Usage:
    python run_premarket.py
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.WARNING)

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def fetch_global_data() -> dict:
    """Fetch live global market data via yfinance."""
    try:
        import yfinance as yf
        tickers = {
            "SGX Nifty (approx via ^NSEI)": "^NSEI",
            "S&P 500 Futures":              "ES=F",
            "Nasdaq Futures":               "NQ=F",
            "Nikkei 225":                   "^N225",
            "Hang Seng":                    "^HSI",
            "Crude Oil (WTI)":              "CL=F",
            "Gold":                         "GC=F",
            "Dollar Index (DXY)":           "DX-Y.NYB",
            "USD/INR":                      "INR=X",
            "VIX":                          "^VIX",
        }
        data = {}
        for label, ticker in tickers.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="2d", interval="1d")
                if len(hist) >= 2:
                    prev  = hist["Close"].iloc[-2]
                    curr  = hist["Close"].iloc[-1]
                    chg   = ((curr - prev) / prev) * 100
                    sign  = "+" if chg >= 0 else ""
                    data[label] = f"{curr:.2f}  ({sign}{chg:.2f}%)"
                elif len(hist) == 1:
                    data[label] = f"{hist['Close'].iloc[-1]:.2f}"
            except Exception:
                pass
        return data
    except ImportError:
        return {}


def main():
    if not os.environ.get("GROQ_API_KEY"):
        print(f"\n{RED}ERROR: GROQ_API_KEY not set in .env{RESET}")
        sys.exit(1)

    from trading_system.agents.pre_market import PreMarketAgent

    print(f"\n{BOLD}{'═'*55}{RESET}")
    print(f"{BOLD}   PRE-MARKET BRIEFING{RESET}")
    print(f"{BOLD}{'═'*55}{RESET}")

    print("\nFetching global market data...", end=" ", flush=True)
    raw_data = fetch_global_data()
    print("done.\n")

    if raw_data:
        print(f"{CYAN}── Live Global Snapshot ──────────────────────────────{RESET}")
        for label, val in raw_data.items():
            colour = GREEN if "+" in val else RED if val.count("-") > 0 else RESET
            print(f"  {label:<30} {colour}{val}{RESET}")
        print()

    # Build simplified dict for agent
    agent_data = {k: v for k, v in raw_data.items()} if raw_data else {
        "extra": "Live data unavailable — using general market knowledge"
    }

    print("Generating AI briefing...\n")
    agent = PreMarketAgent()
    result = agent.brief(agent_data)

    # Print formatted briefing
    bias_colour = {"BULLISH": GREEN, "BEARISH": RED, "NEUTRAL": YELLOW}
    bc = bias_colour.get(result.get("bias", "NEUTRAL"), RESET)

    print(f"{BOLD}── AI Analysis ───────────────────────────────────────{RESET}")
    print(result.get("raw", ""))

    print(f"\n{BOLD}── Quick Summary ─────────────────────────────────────{RESET}")
    print(f"  Bias     : {bc}{BOLD}{result.get('bias')}{RESET}  [{result.get('strength')}]")
    print(f"  Open     : {result.get('expected_open')}")
    if result.get("key_watch"):
        print(f"  Watch    : {', '.join(result['key_watch'])}")
    if result.get("summary"):
        print(f"  Summary  : {result['summary']}")
    print(f"{BOLD}{'═'*55}{RESET}\n")


if __name__ == "__main__":
    main()
