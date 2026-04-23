from .base import BaseAgent

_SYSTEM = """You are a risk manager for an equity trading desk focused on Indian markets.
Evaluate the proposed trade's risk parameters and return a structured assessment.
Always respond in this exact format:
ASSESSMENT: ACCEPTABLE | HIGH | EXCESSIVE
CONFIDENCE: HIGH | MEDIUM | LOW
REASON: <one sentence>"""


class RiskAnalystAgent(BaseAgent):
    """Reviews position sizing and portfolio risk before a trade is taken."""

    def analyze(self, symbol: str, risk_params: dict) -> dict:
        msg = (
            f"Symbol: {symbol}\n"
            f"Entry Price: {risk_params.get('entry_price', 0):.2f}\n"
            f"Stop Price: {risk_params.get('stop_price', 0):.2f}\n"
            f"Stop Distance: {risk_params.get('stop_distance_pct', 0):.2f}%\n"
            f"Target Price: {risk_params.get('target_price', 0):.2f}\n"
            f"Risk/Reward Ratio: {risk_params.get('rr_ratio', 0):.2f}\n"
            f"Proposed Shares: {risk_params.get('shares', 0)}\n"
            f"Trade Value: ₹{risk_params.get('trade_value', 0):,.0f}\n"
            f"Risk Amount: ₹{risk_params.get('risk_amount', 0):,.0f} "
            f"({risk_params.get('risk_pct_equity', 0):.2f}% of equity)\n"
            f"Current Portfolio Heat: {risk_params.get('portfolio_heat', 0):.2f}%\n"
            f"Open Positions: {risk_params.get('open_positions', 0)}\n"
            f"30-day Volatility: {risk_params.get('volatility', 0):.1%}\n"
            f"Max Drawdown So Far: {risk_params.get('max_drawdown', 0):.2f}%"
        )
        raw = self.chat(_SYSTEM, msg)
        return _parse_response(raw)


def _parse_response(raw: str) -> dict:
    result = {"raw": raw, "source": "risk", "assessment": "HIGH", "confidence": "LOW", "reason": raw}
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("ASSESSMENT:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("ACCEPTABLE", "HIGH", "EXCESSIVE"):
                result["assessment"] = val
        elif line.startswith("CONFIDENCE:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("HIGH", "MEDIUM", "LOW"):
                result["confidence"] = val
        elif line.startswith("REASON:"):
            result["reason"] = line.split(":", 1)[1].strip()
    return result
