"""
Kite daily login — generates access token and saves to .env.

Kite tokens expire every day at midnight IST.
Run this every morning before using run_mac.py.

Usage:
    python kite_login.py
"""

import os
import sys
import webbrowser
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv()

def main():
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

    kite      = KiteConnect(api_key=api_key)
    login_url = kite.login_url()

    print("\n── Kite Daily Login ────────────────────────────────")
    print(f"Opening browser: {login_url}\n")
    webbrowser.open(login_url)

    print("After login you will be redirected to a URL like:")
    print("  http://localhost/?request_token=XXXXXX&action=login&status=success\n")

    request_token = input("Paste the request_token here: ").strip()
    data          = kite.generate_session(request_token, api_secret=api_secret)
    access_token  = data["access_token"]

    env_file = Path(".env")
    if not env_file.exists():
        env_file.touch()
    set_key(str(env_file), "KITE_ACCESS_TOKEN", access_token)

    print(f"\nToken saved to .env — valid until midnight IST.")
    print("Now run: python run_mac.py\n")

if __name__ == "__main__":
    main()
