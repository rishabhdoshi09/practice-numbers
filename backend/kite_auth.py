"""
Zerodha Kite Connect authentication flow.

Daily flow:
  1. GET /kite/login        → redirects user to Zerodha login page
  2. Zerodha redirects to   → GET /kite/callback?request_token=xxx
  3. Backend exchanges token → stores access_token in memory + .env
  4. All subsequent API calls use the access_token
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv, set_key

ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=True)   # explicit path, overrides any stale env
logger = logging.getLogger(__name__)

API_KEY    = os.getenv("KITE_API_KEY", "")
API_SECRET = os.getenv("KITE_API_SECRET", "")

# In-memory token store (persisted to .env for restarts)
_access_token: str = os.getenv("KITE_ACCESS_TOKEN", "")


def get_kite():
    """Return an authenticated KiteConnect instance, or None if not authed."""
    try:
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=API_KEY)
        token = get_access_token()
        if token:
            kite.set_access_token(token)
            return kite
        return None
    except Exception as e:
        logger.warning("Kite not available: %s", e)
        return None


def get_login_url() -> str:
    """Generate the Zerodha login URL for the user to authenticate."""
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=API_KEY)
    return kite.login_url()


def exchange_token(request_token: str) -> str:
    """
    Exchange request_token for access_token.
    Called once per day after user logs in via Zerodha.
    """
    global _access_token
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=API_KEY)
    session = kite.generate_session(request_token, api_secret=API_SECRET)
    _access_token = session["access_token"]
    # Persist to .env so it survives server restarts within the same day
    set_key(str(ENV_FILE), "KITE_ACCESS_TOKEN", _access_token)
    logger.info("Kite access token refreshed successfully")
    return _access_token


def get_access_token() -> str:
    return _access_token


def is_authenticated() -> bool:
    return bool(_access_token)
