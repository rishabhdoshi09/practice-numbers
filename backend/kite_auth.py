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
load_dotenv(dotenv_path=ENV_FILE, override=True)
logger = logging.getLogger(__name__)

# In-memory token store (persisted to .env for restarts)
_access_token: str = os.getenv("KITE_ACCESS_TOKEN", "")


def _api_key() -> str:
    """Read API key fresh from env every call — avoids stale module-level cache."""
    load_dotenv(dotenv_path=ENV_FILE, override=True)
    return os.getenv("KITE_API_KEY", "")


def _api_secret() -> str:
    load_dotenv(dotenv_path=ENV_FILE, override=True)
    return os.getenv("KITE_API_SECRET", "")


def get_kite():
    """Return an authenticated KiteConnect instance, or None if not authed."""
    try:
        from kiteconnect import KiteConnect
        key = _api_key()
        if not key:
            logger.warning("KITE_API_KEY not set in %s", ENV_FILE)
            return None
        kite = KiteConnect(api_key=key)
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
    key = _api_key()
    if not key:
        raise RuntimeError(f"KITE_API_KEY is empty. Check {ENV_FILE}")
    return KiteConnect(api_key=key).login_url()


def exchange_token(request_token: str) -> str:
    """Exchange request_token for access_token (call once after Zerodha login)."""
    global _access_token
    from kiteconnect import KiteConnect
    key    = _api_key()
    secret = _api_secret()
    kite   = KiteConnect(api_key=key)
    session = kite.generate_session(request_token, api_secret=secret)
    _access_token = session["access_token"]
    set_key(str(ENV_FILE), "KITE_ACCESS_TOKEN", _access_token)
    logger.info("Kite access token refreshed successfully")
    return _access_token


def get_access_token() -> str:
    return _access_token


def is_authenticated() -> bool:
    return bool(_access_token)
