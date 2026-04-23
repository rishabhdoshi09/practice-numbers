"""
Pre-market briefing agent.

Fetches overnight global market data (indices, currency, commodities)
and produces a structured morning briefing with market bias.

Run via: python run_premarket.py
"""

import logging
from .base import BaseAgent

logger = logging.getLogger(__name__)

_SYSTEM = """You are a pre-market analyst for Indian equity markets (NSE/BSE).
Every morning you summarize global cues and set the trading bias for the day.
Be concise, actionable, and specific to Indian markets.
Always respond in this exact format:

GLOBAL CUES:
- US Markets: <brief>
- Asian Markets: <brief>
- SGX Nifty: <brief>
- Dollar Index (DXY): <brief>
- Crude Oil: <brief>
- Gold: <brief>

BIAS: BULLISH | BEARISH | NEUTRAL
STRENGTH: STRONG | MODERATE | WEAK
NIFTY EXPECTED OPEN: GAP UP | GAP DOWN | FLAT (approximate %)

KEY WATCH:
- <sector or stock 1>
- <sector or stock 2>
- <sector or stock 3>

SUMMARY: <2 sentences — what traders should focus on today>"""


class PreMarketAgent(BaseAgent):
    def brief(self, market_data: dict) -> dict:
        """
        Generate morning briefing from global market snapshot.

        Args:
            market_data: dict with keys like us_close, sgx_nifty,
                         crude, gold, dxy, asia_summary, vix etc.
        """
        msg = _build_message(market_data)
        raw = self.chat(_SYSTEM, msg, max_tokens=600)
        return _parse(raw)


def _build_message(d: dict) -> str:
    lines = ["Global market snapshot for today's pre-market:\n"]
    mapping = {
        "us_close":    "US Markets (prev close)",
        "sgx_nifty":  "SGX Nifty",
        "nikkei":     "Nikkei 225",
        "hang_seng":  "Hang Seng",
        "crude":      "Crude Oil ($/bbl)",
        "gold":       "Gold ($/oz)",
        "dxy":        "Dollar Index (DXY)",
        "vix":        "VIX",
        "usd_inr":    "USD/INR",
        "extra":      "Other Notes",
    }
    for key, label in mapping.items():
        if key in d and d[key]:
            lines.append(f"{label}: {d[key]}")
    return "\n".join(lines)


def _parse(raw: str) -> dict:
    result = {
        "raw": raw,
        "bias": "NEUTRAL",
        "strength": "MODERATE",
        "expected_open": "FLAT",
        "key_watch": [],
        "summary": "",
        "global_cues": {},
    }
    section = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("BIAS:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("BULLISH", "BEARISH", "NEUTRAL"):
                result["bias"] = val
        elif line.startswith("STRENGTH:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("STRONG", "MODERATE", "WEAK"):
                result["strength"] = val
        elif line.startswith("NIFTY EXPECTED OPEN:"):
            result["expected_open"] = line.split(":", 1)[1].strip()
        elif line.startswith("SUMMARY:"):
            result["summary"] = line.split(":", 1)[1].strip()
        elif line.startswith("KEY WATCH:"):
            section = "watch"
        elif section == "watch" and line.startswith("-"):
            result["key_watch"].append(line.lstrip("- ").strip())
    return result
