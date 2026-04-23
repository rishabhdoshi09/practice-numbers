"""
Mac-optimized TradingAgents config — Kite for price data, Groq for LLM.

Usage:
    from mac_config import MAC_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    ta = TradingAgentsGraph(debug=True, config=MAC_CONFIG)
    _, decision = ta.propagate("RELIANCE", "2024-11-15")
"""

from tradingagents.default_config import DEFAULT_CONFIG

MAC_CONFIG = DEFAULT_CONFIG.copy()

# ── LLM: Groq (free, no GPU needed) ──────────────────────────────────────────
MAC_CONFIG["llm_provider"]    = "groq"
MAC_CONFIG["deep_think_llm"]  = "llama-3.3-70b-versatile"
MAC_CONFIG["quick_think_llm"] = "llama-3.3-70b-versatile"

# ── RAM saver: debate rounds zero (8GB Mac ke liye critical) ──────────────────
MAC_CONFIG["max_debate_rounds"]       = 0
MAC_CONFIG["max_risk_discuss_rounds"] = 1

# ── Data: Kite for OHLCV + indicators, yfinance for fundamentals/news ─────────
MAC_CONFIG["data_vendors"] = {
    "core_stock_apis":      "kite",      # OHLCV from Kite (NSE direct)
    "technical_indicators": "kite",      # Indicators computed on Kite data
    "fundamental_data":     "yfinance",  # Kite has no fundamentals API
    "news_data":            "newsdata",  # NewsData.io — best Indian coverage
}
