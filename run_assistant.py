"""
Real-time trading assistant — interactive CLI.

Ask anything mid-session. The assistant remembers context within the session.

Usage:
    python run_assistant.py

Example questions:
    > Is this breakout weak or strong?
    > Volume confirmation valid for RELIANCE at 2850?
    > RSI is 72 and price just made new high — should I trail my stop?
    > What does bearish divergence on MACD mean here?
    > NIFTY gap up 0.5% — fade or follow?

Commands:
    /context   — set live market data for smarter answers
    /clear     — reset conversation
    /quit      — exit
"""

import os
import sys
import logging

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.WARNING)

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


def get_context_from_user() -> dict:
    print(f"\n{YELLOW}Enter current market context (press Enter to skip any field):{RESET}")
    ctx = {}
    fields = [
        ("symbol",       "Symbol (e.g. RELIANCE)"),
        ("close",        "Current price"),
        ("rsi",          "RSI(14)"),
        ("volume_ratio", "Volume ratio (vs avg)"),
        ("ma20",         "MA(20)"),
        ("ma50",         "MA(50)"),
        ("atr",          "ATR(14)"),
        ("bb_pct",       "Bollinger %B"),
        ("notes",        "Any other notes"),
    ]
    for key, label in fields:
        val = input(f"  {label}: ").strip()
        if val:
            ctx[key] = val
    return ctx


def main():
    if not os.environ.get("GROQ_API_KEY"):
        print(f"\n\033[91mERROR: GROQ_API_KEY not set in .env\033[0m")
        sys.exit(1)

    from trading_system.agents.assistant import TradingAssistant

    assistant = TradingAssistant()
    context   = {}

    print(f"\n{BOLD}{'═'*55}{RESET}")
    print(f"{BOLD}   REAL-TIME TRADING ASSISTANT{RESET}")
    print(f"{BOLD}{'═'*55}{RESET}")
    print(f"{DIM}Commands: /context  /clear  /quit{RESET}")
    print(f"{DIM}Model: {assistant.model}  via Groq{RESET}\n")

    while True:
        try:
            user_input = input(f"{GREEN}You>{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print("Goodbye.")
            break

        if user_input.lower() == "/clear":
            assistant.reset()
            context = {}
            print(f"{DIM}Session cleared.{RESET}\n")
            continue

        if user_input.lower() == "/context":
            context = get_context_from_user()
            print(f"{DIM}Context set. Your next question will include this data.{RESET}\n")
            continue

        # Pass context only on the first message after /context
        answer = assistant.ask(user_input, context if context else None)
        context = {}  # context used once, then cleared

        print(f"\n{CYAN}AI>{RESET} {answer}\n")


if __name__ == "__main__":
    main()
