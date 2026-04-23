from .base import BaseAgent

_SYSTEM = """You are a senior technical analyst for Indian equity markets (NSE/BSE).
Analyze the given technical indicators and return a structured view.
Always respond in this exact format:
VIEW: BULLISH | BEARISH | NEUTRAL
CONFIDENCE: HIGH | MEDIUM | LOW
REASON: <one sentence>"""


class TechnicalAnalystAgent(BaseAgent):
    """Evaluates technical indicators and returns a directional view."""

    def analyze(self, symbol: str, indicators: dict) -> dict:
        msg = (
            f"Symbol: {symbol}\n"
            f"Quant Signal: {indicators.get('signal', 'N/A')} (1=BUY, -1=SELL, 0=HOLD)\n"
            f"RSI(14): {indicators.get('rsi', 'N/A'):.1f}\n"
            f"Fast MA ({indicators.get('fast_ma_period', 20)}): {indicators.get('fast_ma', 'N/A'):.2f}\n"
            f"Slow MA ({indicators.get('slow_ma_period', 50)}): {indicators.get('slow_ma', 'N/A'):.2f}\n"
            f"MA Crossover: {indicators.get('ma_crossover', 'N/A')}\n"
            f"Price vs MA50: {indicators.get('price_vs_ma50', 'N/A')}\n"
            f"ATR(14): {indicators.get('atr', 'N/A'):.2f}\n"
            f"Bollinger %B: {indicators.get('bb_pct', 'N/A'):.2f}\n"
            f"BB Width: {indicators.get('bb_width', 'N/A'):.4f}\n"
            f"Volume Ratio: {indicators.get('volume_ratio', 'N/A'):.2f}x average\n"
            f"Current Price: {indicators.get('close', 'N/A'):.2f}\n"
            f"20-day Volatility (annualised): {indicators.get('volatility', 'N/A'):.1%}"
        )
        raw = self.chat(_SYSTEM, msg)
        return _parse_response(raw, "technical")


def _parse_response(raw: str, source: str) -> dict:
    result = {"raw": raw, "source": source, "view": "NEUTRAL", "confidence": "LOW", "reason": raw}
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("VIEW:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("BULLISH", "BEARISH", "NEUTRAL"):
                result["view"] = val
        elif line.startswith("CONFIDENCE:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("HIGH", "MEDIUM", "LOW"):
                result["confidence"] = val
        elif line.startswith("REASON:"):
            result["reason"] = line.split(":", 1)[1].strip()
    return result
