"""
NewsData.io news provider for TradingAgents.

Replaces yfinance for stock and global news — much better Indian market coverage.
Output format matches yfinance_news.py exactly so all agents work unchanged.

Env var required:
    NEWSDATA_API_KEY   (free at https://newsdata.io — 200 credits/day, no card)

Note: Free tier uses /latest endpoint — from_date/to_date require a paid plan.
Falls back to yfinance if key is absent.
"""

import logging
import os
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

_LATEST_URL = "https://newsdata.io/api/1/latest"


def _api_key() -> str:
    return os.environ.get("NEWSDATA_API_KEY", "").strip()


def _plain_symbol(ticker: str) -> str:
    """Strip exchange suffix for cleaner search queries."""
    return ticker.upper().replace(".NS", "").replace(".BO", "")


# ── Stock-specific news ────────────────────────────────────────────────────────

def get_news_newsdata(
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    Fetch stock-specific news from NewsData.io.
    Matches signature of get_news_yfinance(ticker, start_date, end_date).
    """
    key = _api_key()
    if not key:
        logger.warning("NEWSDATA_API_KEY not set — falling back to yfinance news")
        from .yfinance_news import get_news_yfinance
        return get_news_yfinance(ticker, start_date, end_date)

    plain = _plain_symbol(ticker)

    try:
        # Free tier: /latest endpoint — from_date/to_date are paid-only params
        params = {
            "apikey":   key,
            "q":        plain,
            "language": "en",
            "country":  "in",
            "category": "business",
        }
        resp = requests.get(_LATEST_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        articles = data.get("results", [])
        if not articles:
            return f"No news found for {plain}"

        news_str = ""
        for art in articles[:15]:
            title    = art.get("title",       "No title")
            desc     = art.get("description", "") or ""
            source   = art.get("source_name", "Unknown")
            link     = art.get("link",        "")
            pub_date = art.get("pubDate",     "")

            news_str += f"### {title} (source: {source})\n"
            if desc:
                news_str += f"{desc[:300]}\n"
            if link:
                news_str += f"Link: {link}\n"
            if pub_date:
                news_str += f"Published: {pub_date}\n"
            news_str += "\n"

        return f"## {plain} News (via NewsData.io), latest:\n\n{news_str}"

    except requests.RequestException as exc:
        logger.warning("NewsData.io stock news failed for %s: %s — falling back", plain, exc)
        from .yfinance_news import get_news_yfinance
        return get_news_yfinance(ticker, start_date, end_date)


# ── Global / macro news ────────────────────────────────────────────────────────

def get_global_news_newsdata(
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 10,
) -> str:
    """
    Fetch global market and macro news from NewsData.io.
    Matches signature of get_global_news_yfinance(curr_date, look_back_days, limit).
    """
    key = _api_key()
    if not key:
        logger.warning("NEWSDATA_API_KEY not set — falling back to yfinance global news")
        from .yfinance_news import get_global_news_yfinance
        return get_global_news_yfinance(curr_date, look_back_days, limit)

    queries = [
        "Nifty Sensex stock market India",
        "RBI interest rate inflation India",
        "global stock market economy",
    ]

    seen_titles: set = set()
    all_articles: list = []

    try:
        for query in queries:
            if len(all_articles) >= limit:
                break
            # Free tier: /latest endpoint without date filtering
            params = {
                "apikey":   key,
                "q":        query,
                "language": "en",
                "category": "business",
            }
            try:
                resp = requests.get(_LATEST_URL, params=params, timeout=10)
                resp.raise_for_status()
                results = resp.json().get("results", [])
                for art in results:
                    title = art.get("title", "")
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        all_articles.append(art)
            except requests.RequestException:
                continue

        if not all_articles:
            return f"No global news found for {curr_date}"

        news_str = ""
        for art in all_articles[:limit]:
            title    = art.get("title",       "No title")
            desc     = art.get("description", "") or ""
            source   = art.get("source_name", "Unknown")
            link     = art.get("link",        "")
            pub_date = art.get("pubDate",     "")

            news_str += f"### {title} (source: {source})\n"
            if desc:
                news_str += f"{desc[:300]}\n"
            if link:
                news_str += f"Link: {link}\n"
            if pub_date:
                news_str += f"Published: {pub_date}\n"
            news_str += "\n"

        return f"## Global Market News (via NewsData.io), latest:\n\n{news_str}"

    except Exception as exc:
        logger.warning("NewsData.io global news failed: %s — falling back", exc)
        from .yfinance_news import get_global_news_yfinance
        return get_global_news_yfinance(curr_date, look_back_days, limit)
