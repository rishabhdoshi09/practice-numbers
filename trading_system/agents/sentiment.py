"""
Sentiment analyst agent.

News sources (tried in order, uses first that returns results):
  1. NewsData.io   — best Indian coverage, 200 free credits/day
  2. NewsAPI.org   — global + Indian news, 1000 calls/month free
  3. RSS feeds     — Economic Times, Moneycontrol, Mint (no key needed)
  4. yfinance      — fallback

Set keys in .env:
  NEWSDATA_API_KEY=...   (https://newsdata.io)
  NEWSAPI_KEY=...        (https://newsapi.org)
"""

import logging
import os
import time

from .base import BaseAgent

logger = logging.getLogger(__name__)

_SYSTEM = """You are a financial news analyst specializing in Indian equity markets (NSE/BSE).
Analyze the news headlines below and return a structured sentiment view.
Always respond in this exact format:
VIEW: POSITIVE | NEGATIVE | NEUTRAL
CONFIDENCE: HIGH | MEDIUM | LOW
REASON: <one sentence summarizing the key sentiment driver>"""

# ── RSS feeds — no API key needed ─────────────────────────────────────────────
_RSS_FEEDS = [
    ("Economic Times Markets", "https://economictimes.indiatimes.com/markets/rss.cms"),
    ("Moneycontrol",           "https://www.moneycontrol.com/rss/latestnews.xml"),
    ("Mint Markets",           "https://www.livemint.com/rss/markets"),
    ("Business Standard",      "https://www.business-standard.com/rss/markets-106.rss"),
]


class SentimentAnalystAgent(BaseAgent):
    def analyze(self, symbol: str) -> dict:
        # Strip .NS / .BO for cleaner search queries
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")

        headlines, source_used = _fetch_headlines(clean_sym)

        if not headlines:
            return {
                "source": "sentiment",
                "news_source": "none",
                "view": "NEUTRAL",
                "confidence": "LOW",
                "reason": "No recent news found — defaulting to neutral.",
                "raw": "",
            }

        bullet_list = "\n".join(f"- {h}" for h in headlines[:10])
        msg = f"Stock: {clean_sym} (Indian market)\n\nRecent headlines:\n{bullet_list}"
        raw = self.chat(_SYSTEM, msg)
        result = _parse_response(raw)
        result["news_source"] = source_used
        return result


# ── Fetchers ──────────────────────────────────────────────────────────────────

def _fetch_headlines(symbol: str) -> tuple:
    """Returns (headlines_list, source_name). Tries sources in priority order."""

    # 1. NewsData.io
    key = os.environ.get("NEWSDATA_API_KEY", "").strip()
    if key:
        headlines = _from_newsdata(symbol, key)
        if headlines:
            return headlines, "newsdata.io"

    # 2. NewsAPI.org
    key = os.environ.get("NEWSAPI_KEY", "").strip()
    if key:
        headlines = _from_newsapi(symbol, key)
        if headlines:
            return headlines, "newsapi.org"

    # 3. RSS feeds (no key)
    headlines = _from_rss(symbol)
    if headlines:
        return headlines, "rss"

    # 4. yfinance fallback
    headlines = _from_yfinance(symbol)
    if headlines:
        return headlines, "yfinance"

    return [], "none"


def _from_newsdata(symbol: str, api_key: str) -> list:
    try:
        import requests
        url = "https://newsdata.io/api/1/news"
        params = {
            "apikey":   api_key,
            "q":        symbol,
            "country":  "in",
            "language": "en",
            "category": "business",
        }
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        return [a.get("title", "") for a in data.get("results", []) if a.get("title")]
    except Exception as exc:
        logger.warning("NewsData.io failed for %s: %s", symbol, exc)
        return []


def _from_newsapi(symbol: str, api_key: str) -> list:
    try:
        import requests
        url = "https://newsapi.org/v2/everything"
        params = {
            "apiKey":   api_key,
            "q":        f"{symbol} stock NSE",
            "language": "en",
            "sortBy":   "publishedAt",
            "pageSize": 10,
        }
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        return [a.get("title", "") for a in data.get("articles", []) if a.get("title")]
    except Exception as exc:
        logger.warning("NewsAPI failed for %s: %s", symbol, exc)
        return []


def _from_rss(symbol: str) -> list:
    """Parse RSS feeds and filter articles mentioning the symbol."""
    try:
        import xml.etree.ElementTree as ET
        import urllib.request

        headlines = []
        sym_lower = symbol.lower()

        for feed_name, url in _RSS_FEEDS:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    xml_data = resp.read()
                root = ET.fromstring(xml_data)
                for item in root.iter("item"):
                    title = item.findtext("title", "").strip()
                    desc  = item.findtext("description", "").lower()
                    if sym_lower in title.lower() or sym_lower in desc:
                        headlines.append(title)
                if headlines:
                    break  # stop after first feed that has results
            except Exception:
                continue

        # If no symbol-specific results, grab general market headlines
        if not headlines:
            for feed_name, url in _RSS_FEEDS[:2]:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        xml_data = resp.read()
                    root = ET.fromstring(xml_data)
                    for item in root.iter("item"):
                        title = item.findtext("title", "").strip()
                        if title:
                            headlines.append(title)
                        if len(headlines) >= 8:
                            break
                    if headlines:
                        break
                except Exception:
                    continue

        return headlines[:10]
    except Exception as exc:
        logger.warning("RSS fetch failed: %s", exc)
        return []


def _from_yfinance(symbol: str) -> list:
    try:
        import yfinance as yf
        # yfinance needs .NS suffix for NSE stocks
        sym = symbol if symbol.endswith(".NS") or symbol.endswith(".BO") else f"{symbol}.NS"
        ticker = yf.Ticker(sym)
        news = ticker.news or []
        headlines = []
        for item in news:
            content = item.get("content", {})
            title = content.get("title") if isinstance(content, dict) else item.get("title", "")
            if title:
                headlines.append(title)
        return headlines
    except Exception as exc:
        logger.warning("yfinance news failed for %s: %s", symbol, exc)
        return []


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_response(raw: str) -> dict:
    result = {
        "raw": raw,
        "source": "sentiment",
        "view": "NEUTRAL",
        "confidence": "LOW",
        "reason": raw,
    }
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("VIEW:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
                result["view"] = val
        elif line.startswith("CONFIDENCE:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("HIGH", "MEDIUM", "LOW"):
                result["confidence"] = val
        elif line.startswith("REASON:"):
            result["reason"] = line.split(":", 1)[1].strip()
    return result
