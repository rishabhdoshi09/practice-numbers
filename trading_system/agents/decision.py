from .base import BaseAgent

_SYSTEM = """You are the head trader at an Indian equity trading desk.
You receive analysis from three specialists and make the final trading call.
Be decisive. Err on the side of caution when risk is HIGH or EXCESSIVE.
Always respond in this exact format:
DECISION: BUY | SELL | HOLD
CONFIDENCE: HIGH | MEDIUM | LOW
REASON: <one sentence explaining the final call>"""


class DecisionAgent(BaseAgent):
    """Aggregates all agent views and makes the final trade decision."""

    def decide(
        self,
        symbol: str,
        quant_signal: int,
        technical: dict,
        sentiment: dict,
        risk: dict,
    ) -> dict:
        signal_label = {1: "BUY", -1: "SELL", 0: "HOLD"}.get(quant_signal, "HOLD")

        msg = (
            f"Symbol: {symbol}\n\n"
            f"QUANT SYSTEM SIGNAL: {signal_label}\n\n"
            f"TECHNICAL ANALYST:\n"
            f"  View: {technical.get('view')}\n"
            f"  Confidence: {technical.get('confidence')}\n"
            f"  Reason: {technical.get('reason')}\n\n"
            f"SENTIMENT ANALYST:\n"
            f"  View: {sentiment.get('view')}\n"
            f"  Confidence: {sentiment.get('confidence')}\n"
            f"  Reason: {sentiment.get('reason')}\n\n"
            f"RISK MANAGER:\n"
            f"  Assessment: {risk.get('assessment')}\n"
            f"  Confidence: {risk.get('confidence')}\n"
            f"  Reason: {risk.get('reason')}\n\n"
            "Make your final decision."
        )
        raw = self.chat(_SYSTEM, msg)
        return _parse_response(raw)


def _parse_response(raw: str) -> dict:
    result = {"raw": raw, "source": "decision", "decision": "HOLD", "confidence": "LOW", "reason": raw}
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("DECISION:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("BUY", "SELL", "HOLD"):
                result["decision"] = val
        elif line.startswith("CONFIDENCE:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("HIGH", "MEDIUM", "LOW"):
                result["confidence"] = val
        elif line.startswith("REASON:"):
            result["reason"] = line.split(":", 1)[1].strip()
    return result
