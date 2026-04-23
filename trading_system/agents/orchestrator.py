"""
AgentOrchestrator — coordinates all 4 LLM agents for a given trading signal.

Flow:
  1. TechnicalAnalystAgent   — reads indicators, gives BULLISH/BEARISH/NEUTRAL
  2. SentimentAnalystAgent   — reads news headlines, gives POSITIVE/NEGATIVE/NEUTRAL
  3. RiskAnalystAgent        — reviews position sizing and portfolio heat
  4. DecisionAgent           — aggregates all views, gives final BUY/SELL/HOLD

The orchestrator is called only when the quant system fires a signal (buy or sell).
It acts as a second opinion layer — not the sole decision maker.
"""

import logging
from typing import Dict

import pandas as pd

from .technical import TechnicalAnalystAgent
from .sentiment import SentimentAnalystAgent
from .risk_agent import RiskAnalystAgent
from .decision import DecisionAgent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self):
        self.technical = TechnicalAnalystAgent()
        self.sentiment = SentimentAnalystAgent()
        self.risk = RiskAnalystAgent()
        self.decision = DecisionAgent()

    def analyze(
        self,
        symbol: str,
        row: pd.Series,
        quant_signal: int,
        equity: float,
        portfolio_heat: float,
        open_positions: int,
        max_drawdown_pct: float,
        strategy_cfg,
    ) -> Dict:
        """
        Run all agents for a single symbol on a single bar.

        Args:
            symbol:           stock ticker
            row:              latest data row with all indicators
            quant_signal:     1=BUY, -1=SELL, 0=HOLD from quant system
            equity:           current portfolio equity
            portfolio_heat:   fraction of equity at risk across open trades
            open_positions:   number of currently open positions
            max_drawdown_pct: max drawdown seen so far (%)
            strategy_cfg:     StrategyConfig for MA periods etc.

        Returns:
            dict with all agent outputs and final decision
        """
        # ── 1. Technical ──────────────────────────────────────────────
        fast_ma_col = f"ma_{strategy_cfg.fast_ma}"
        slow_ma_col = f"ma_{strategy_cfg.slow_ma}"
        vol_col = f"volatility_20"

        indicators = {
            "signal": quant_signal,
            "rsi": _safe(row, "rsi"),
            "fast_ma": _safe(row, fast_ma_col),
            "slow_ma": _safe(row, slow_ma_col),
            "fast_ma_period": strategy_cfg.fast_ma,
            "slow_ma_period": strategy_cfg.slow_ma,
            "ma_crossover": (
                "Fast above Slow"
                if _safe(row, fast_ma_col) > _safe(row, slow_ma_col)
                else "Fast below Slow"
            ),
            "price_vs_ma50": (
                "Above MA50" if _safe(row, "close") > _safe(row, "ma_50") else "Below MA50"
            ),
            "atr": _safe(row, "atr"),
            "bb_pct": _safe(row, "bb_pct"),
            "bb_width": _safe(row, "bb_width"),
            "volume_ratio": _safe(row, "volume_ratio"),
            "close": _safe(row, "close"),
            "volatility": _safe(row, vol_col),
        }

        logger.info("[%s] Running TechnicalAnalystAgent...", symbol)
        tech_result = self.technical.analyze(symbol, indicators)

        # ── 2. Sentiment ──────────────────────────────────────────────
        logger.info("[%s] Running SentimentAnalystAgent...", symbol)
        sent_result = self.sentiment.analyze(symbol)

        # ── 3. Risk ───────────────────────────────────────────────────
        close = _safe(row, "close")
        stop = _safe(row, "stop_price") if not pd.isna(_safe(row, "stop_price")) else close * 0.97
        target = _safe(row, "target_price") if not pd.isna(_safe(row, "target_price")) else close * 1.06
        stop_dist_pct = ((close - stop) / close * 100) if close > 0 else 0
        rr = ((target - close) / (close - stop)) if (close - stop) > 0 else 0
        risk_amount = equity * 0.01  # 1% risk per trade
        shares_approx = risk_amount / max((close - stop), 0.01)
        trade_value = shares_approx * close

        risk_params = {
            "entry_price": close,
            "stop_price": stop,
            "stop_distance_pct": stop_dist_pct,
            "target_price": target,
            "rr_ratio": rr,
            "shares": int(shares_approx),
            "trade_value": trade_value,
            "risk_amount": risk_amount,
            "risk_pct_equity": 1.0,
            "portfolio_heat": portfolio_heat * 100,
            "open_positions": open_positions,
            "volatility": _safe(row, vol_col),
            "max_drawdown": max_drawdown_pct,
        }

        logger.info("[%s] Running RiskAnalystAgent...", symbol)
        risk_result = self.risk.analyze(symbol, risk_params)

        # ── 4. Decision ───────────────────────────────────────────────
        logger.info("[%s] Running DecisionAgent...", symbol)
        decision_result = self.decision.decide(
            symbol, quant_signal, tech_result, sent_result, risk_result
        )

        return {
            "symbol": symbol,
            "quant_signal": quant_signal,
            "technical": tech_result,
            "sentiment": sent_result,
            "risk": risk_result,
            "decision": decision_result,
        }


def _safe(row: pd.Series, col: str, default: float = 0.0) -> float:
    val = row.get(col, default)
    return default if pd.isna(val) else float(val)
