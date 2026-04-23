"""
Kite daily login helper.

Kite access tokens expire every day at midnight IST.
Run this script once each morning before trading to refresh the token.

Usage:
    python -m trading_system.data.kite_login

Steps:
  1. It opens the Kite login URL in your browser
  2. You log in with your Zerodha credentials
  3. You are redirected to a URL like:
       http://localhost/?request_token=XXXXXX&action=login&status=success
  4. Copy the request_token from that URL
  5. Paste it when prompted — script saves it to .env automatically
"""

import os
import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv, set_key

load_dotenv()

ENV_FILE = Path(".env")


def login():
    try:
        from kiteconnect import KiteConnect
    except ImportError:
        print("kiteconnect not installed. Run: pip install kiteconnect")
        sys.exit(1)

    api_key    = os.environ.get("KITE_API_KEY", "").strip()
    api_secret = os.environ.get("KITE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        print("ERROR: KITE_API_KEY and KITE_API_SECRET not set in .env")
        sys.exit(1)

    kite     = KiteConnect(api_key=api_key)
    login_url = kite.login_url()

    print("\n── Kite Daily Login ────────────────────────────────")
    print(f"Opening login URL in browser:\n  {login_url}\n")
    webbrowser.open(login_url)

    print("After login, you will be redirected to a URL like:")
    print("  http://localhost/?request_token=XXXXXX&action=login&status=success\n")

    request_token = input("Paste the request_token here: ").strip()

    data         = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]

    # Save to .env
    if not ENV_FILE.exists():
        ENV_FILE.touch()

    set_key(str(ENV_FILE), "KITE_ACCESS_TOKEN", access_token)

    print(f"\nAccess token saved to .env")
    print(f"Token: {access_token[:10]}...{access_token[-6:]}")
    print("You can now run: python run_llm.py\n")


if __name__ == "__main__":
    login()
