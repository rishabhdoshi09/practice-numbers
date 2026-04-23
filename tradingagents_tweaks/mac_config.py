"""
Mac-optimized TradingAgents config for MacBook Air 2015 (8GB RAM, Intel i5).

Usage:
    from mac_config import MAC_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    ta = TradingAgentsGraph(debug=True, config=MAC_CONFIG)
    _, decision = ta.propagate("RELIANCE.NS", "2024-11-15")
    print(decision)
"""

from tradingagents.default_config import DEFAULT_CONFIG

MAC_CONFIG = DEFAULT_CONFIG.copy()

# ── LLM: Groq (free, no GPU needed) ──────────────────────────────────────────
MAC_CONFIG["llm_provider"]    = "groq"
MAC_CONFIG["deep_think_llm"]  = "llama-3.3-70b-versatile"   # best quality, free
MAC_CONFIG["quick_think_llm"] = "llama-3.1-8b-instant"       # fastest, free

# ── RAM saver: debate rounds zero karo (8GB Mac ke liye critical) ─────────────
MAC_CONFIG["max_debate_rounds"]      = 0   # default=1, skip bull/bear debate
MAC_CONFIG["max_risk_discuss_rounds"] = 1   # keep one risk check

# ── Data: yfinance (Indian stocks use .NS suffix) ─────────────────────────────
MAC_CONFIG["data_vendors"] = {
    "core_stock_apis":      "yfinance",
    "technical_indicators": "yfinance",
    "fundamental_data":     "yfinance",
    "news_data":            "yfinance",
}
