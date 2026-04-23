import logging
from .base import BaseAgent

logger = logging.getLogger(__name__)

_SYSTEM = """You are a financial news analyst specializing in Indian equity markets.
Analyze the news headlines below and return a structured sentiment view.
Always respond in this exact format:
VIEW: POSITIVE | NEGATIVE | NEUTRAL
CONFIDENCE: HIGH | MEDIUM | LOW
REASON: <one sentence summarizing the key sentiment driver>"""


class SentimentAnalystAgent(BaseAgent):
    """Fetches recent news via yfinance and scores sentiment with an LLM."""

    def analyze(self, symbol: str) -> dict:
        headlines = _fetch_headlines(symbol)
        if not headlines:
            return {
                "source": "sentiment",
                "view": "NEUTRAL",
                "confidence": "LOW",
                "reason": "No recent news found.",
                "raw": "",
            }

        bullet_list = "\n".join(f"- {h}" for h in headlines[:8])
        msg = f"Symbol: {symbol}\n\nRecent news headlines:\n{bullet_list}"
        raw = self.chat(_SYSTEM, msg)
        return _parse_response(raw)


def _fetch_headlines(symbol: str) -> list:
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        news = ticker.news or []
        headlines = []
        for item in news:
            content = item.get("content", {})
            title = content.get("title") if isinstance(content, dict) else item.get("title", "")
            if title:
                headlines.append(title)
        return headlines
    except Exception as exc:
        logger.warning("Could not fetch news for %s: %s", symbol, exc)
        return []


def _parse_response(raw: str) -> dict:
    result = {"raw": raw, "source": "sentiment", "view": "NEUTRAL", "confidence": "LOW", "reason": raw}
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
