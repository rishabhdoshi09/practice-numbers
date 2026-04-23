"""
Trade journal agent.

Analyzes past trades (from trade_log.csv or manual input) to identify:
  - Recurring mistakes
  - Best performing setups
  - Psychological patterns
  - Actionable improvements

Run via: python run_journal.py
"""

import logging
from .base import BaseAgent

logger = logging.getLogger(__name__)

_SYSTEM = """You are an elite trading coach analyzing a trader's trade journal.
Your goal is to find patterns, mistakes, and opportunities for improvement.
Be direct, specific, and constructive. Focus on what's actionable.
Always respond in this format:

PERFORMANCE SUMMARY:
- Win Rate: <value>
- Avg Win: <value>
- Avg Loss: <value>
- Best Setup: <describe>
- Worst Setup: <describe>

MISTAKES FOUND:
1. <specific mistake with example>
2. <specific mistake with example>
3. <specific mistake with example>

PATTERNS:
- <positive pattern>
- <negative pattern>

IMPROVEMENTS:
1. <actionable fix 1>
2. <actionable fix 2>
3. <actionable fix 3>

VERDICT: <2 sentences — overall assessment and top priority to fix>"""


class JournalAgent(BaseAgent):
    def analyze_trades(self, trades: list) -> dict:
        """
        Analyze a list of trade dicts.

        Each trade dict should have:
          symbol, entry_date, exit_date, entry_price, exit_price,
          net_pnl, return_pct, exit_reason, holding_days
        """
        if not trades:
            return {"raw": "No trades to analyze.", "verdict": "No trades yet."}

        msg = _build_message(trades)
        raw = self.chat(_SYSTEM, msg, max_tokens=700)
        return _parse(raw)

    def analyze_single_trade(self, trade: dict, why_taken: str = "", outcome_feeling: str = "") -> dict:
        """Analyze one specific trade with trader's notes."""
        _SINGLE_SYSTEM = """You are a trading coach reviewing a single trade.
        Identify what was done right, what was wrong, and what to learn.
        Format:
        EXECUTION: GOOD | POOR | MIXED
        WHAT WORKED: <one line>
        WHAT FAILED: <one line>
        ROOT CAUSE: <one line — the real reason it worked or failed>
        LESSON: <one actionable takeaway>"""

        msg = (
            f"Trade Details:\n"
            f"  Symbol: {trade.get('symbol')}\n"
            f"  Entry: {trade.get('entry_price')} on {trade.get('entry_date')}\n"
            f"  Exit: {trade.get('exit_price')} on {trade.get('exit_date')}\n"
            f"  P&L: ₹{trade.get('net_pnl', 0):,.0f} ({trade.get('return_pct', 0):.2f}%)\n"
            f"  Exit Reason: {trade.get('exit_reason')}\n"
            f"  Holding Days: {trade.get('holding_days')}\n\n"
            f"Trader's Notes:\n"
            f"  Why taken: {why_taken or 'Not specified'}\n"
            f"  How it felt: {outcome_feeling or 'Not specified'}"
        )
        raw = self.chat(_SINGLE_SYSTEM, msg, max_tokens=400)
        return {"raw": raw}


def _build_message(trades: list) -> str:
    wins   = [t for t in trades if t.get("net_pnl", 0) > 0]
    losses = [t for t in trades if t.get("net_pnl", 0) <= 0]
    total  = len(trades)
    wr     = len(wins) / total * 100 if total else 0
    avg_w  = sum(t.get("net_pnl", 0) for t in wins)   / len(wins)   if wins   else 0
    avg_l  = sum(t.get("net_pnl", 0) for t in losses) / len(losses) if losses else 0

    lines = [
        f"Total trades: {total}",
        f"Win rate: {wr:.1f}%",
        f"Avg win: ₹{avg_w:,.0f}",
        f"Avg loss: ₹{avg_l:,.0f}",
        "",
        "Trade log (last 20):",
    ]
    for t in trades[-20:]:
        pnl = t.get("net_pnl", 0)
        sign = "+" if pnl > 0 else ""
        lines.append(
            f"  {t.get('symbol','?')} | {t.get('entry_date','?')} → {t.get('exit_date','?')} "
            f"| {sign}₹{pnl:,.0f} ({t.get('return_pct', 0):.2f}%) "
            f"| Exit: {t.get('exit_reason','?')} | {t.get('holding_days','?')}d"
        )
    return "\n".join(lines)


def _parse(raw: str) -> dict:
    result = {"raw": raw, "mistakes": [], "improvements": [], "patterns": [], "verdict": ""}
    section = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("VERDICT:"):
            result["verdict"] = line.split(":", 1)[1].strip()
        elif line.startswith("MISTAKES FOUND:"):
            section = "mistakes"
        elif line.startswith("IMPROVEMENTS:"):
            section = "improvements"
        elif line.startswith("PATTERNS:"):
            section = "patterns"
        elif line.startswith("PERFORMANCE SUMMARY:"):
            section = "summary"
        elif section == "mistakes" and (line[0].isdigit() or line.startswith("-")):
            result["mistakes"].append(line.lstrip("0123456789.-) ").strip())
        elif section == "improvements" and (line[0].isdigit() or line.startswith("-")):
            result["improvements"].append(line.lstrip("0123456789.-) ").strip())
        elif section == "patterns" and line.startswith("-"):
            result["patterns"].append(line.lstrip("- ").strip())
    return result
