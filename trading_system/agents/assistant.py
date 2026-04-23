"""
Real-time trading assistant.

Ask anything mid-session:
  "Is this breakout weak or strong?"
  "Volume confirmation valid?"
  "Should I trail my stop here?"
  "What does RSI divergence mean right now?"

Run via: python run_assistant.py
Or import and call ask() directly in your own scripts.
"""

from .base import BaseAgent

_SYSTEM = """You are a sharp, experienced Indian equity trader acting as a real-time assistant.
Answer questions concisely — like a trading desk colleague, not a textbook.
When given chart data or indicators, give a direct opinion.
No disclaimers. No "consult a financial advisor." Just clear, actionable answers.
If you need more data to answer properly, say exactly what data you need.
Keep answers under 5 lines unless the question requires more depth."""


class TradingAssistant(BaseAgent):
    def __init__(self):
        super().__init__()
        self._history = [{"role": "system", "content": _SYSTEM}]

    def ask(self, question: str, context: dict = None) -> str:
        """
        Ask a real-time question, optionally with market context.

        Args:
            question: natural language question
            context:  optional dict with current market data
                      e.g. {"symbol": "RELIANCE", "rsi": 68, "volume_ratio": 2.1,
                             "close": 2850, "ma20": 2800, "ma50": 2750}
        """
        user_msg = _build_question(question, context)
        self._history.append({"role": "user", "content": user_msg})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self._history,
            max_tokens=300,
            temperature=0.2,
        )
        answer = response.choices[0].message.content.strip()
        self._history.append({"role": "assistant", "content": answer})
        return answer

    def reset(self):
        """Clear conversation history (start fresh session)."""
        self._history = [{"role": "system", "content": _SYSTEM}]


def _build_question(question: str, context: dict = None) -> str:
    if not context:
        return question
    ctx_lines = [f"{k}: {v}" for k, v in context.items()]
    ctx_str = "\n".join(ctx_lines)
    return f"Market context:\n{ctx_str}\n\nQuestion: {question}"
