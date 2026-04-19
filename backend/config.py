"""
Central configuration for SimpleQuant.
All constants live here — no magic numbers in engine code.
"""
from typing import Final

# ── Market universe ────────────────────────────────────────────────────────────
DEFAULT_SYMBOLS: Final[list[str]] = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "BAJFINANCE.NS", "WIPRO.NS", "SBIN.NS", "TATAMOTORS.NS",
    "ADANIPORTS.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BHARTIARTL.NS", "ITC.NS",
]

DEFAULT_SYMBOL: Final[str] = "RELIANCE.NS"

# ── Data fetch windows ─────────────────────────────────────────────────────────
HISTORY_DAYS: Final[int] = 365          # 1-year training window
INTRADAY_INTERVAL: Final[str] = "1d"   # yFinance interval string
DATA_CACHE_TTL_SECONDS: Final[int] = 300

# ── Feature engine ─────────────────────────────────────────────────────────────
SMA_SHORT: Final[int] = 10
SMA_LONG: Final[int] = 50
EMA_SPAN: Final[int] = 20
RSI_PERIOD: Final[int] = 14
ATR_PERIOD: Final[int] = 14
BOLLINGER_PERIOD: Final[int] = 20
BOLLINGER_STD: Final[float] = 2.0

# Monte Carlo
MC_SIMULATIONS: Final[int] = 1000
MC_HORIZON_DAYS: Final[int] = 30

# ARIMA order — (p, d, q)
ARIMA_ORDER: Final[tuple[int, int, int]] = (2, 1, 2)
ARIMA_FORECAST_DAYS: Final[int] = 5

# GARCH order — (p, q)
GARCH_P: Final[int] = 1
GARCH_Q: Final[int] = 1

# ML
ML_LOOKBACK_LAGS: Final[int] = 5       # lagged-return features
ML_TEST_SPLIT: Final[float] = 0.2
RANDOM_STATE: Final[int] = 42

# Z-score threshold for "extreme" signals
ZSCORE_THRESHOLD: Final[float] = 1.5

# ── Decision engine ────────────────────────────────────────────────────────────
# Signal weights must sum to 1.0
SIGNAL_WEIGHTS: Final[dict[str, float]] = {
    "trend":       0.20,
    "momentum":    0.15,
    "volatility":  0.10,
    "arima":       0.15,
    "gbm":         0.05,
    "ml":          0.20,
    "sentiment":   0.10,
    "mean_revert": 0.05,
}

BUY_THRESHOLD: Final[float] = 0.15      # weighted score > threshold → BUY
SELL_THRESHOLD: Final[float] = -0.15    # weighted score < threshold → SELL

CONFIDENCE_SCALE: Final[float] = 100.0  # map [-1,1] → [0,100]

# ── Risk engine ────────────────────────────────────────────────────────────────
KELLY_FRACTION: Final[float] = 0.5      # half-Kelly for safety
MAX_POSITION_PCT: Final[float] = 0.20   # never more than 20 % of portfolio in one stock
MAX_DRAWDOWN_PCT: Final[float] = 0.15   # halt at 15 % drawdown
ATR_STOP_MULTIPLIER: Final[float] = 2.0 # stop = entry − 2×ATR
VAR_CONFIDENCE_95: Final[float] = 0.95
VAR_CONFIDENCE_99: Final[float] = 0.99
DEFAULT_PORTFOLIO_VALUE: Final[float] = 1_000_000.0   # ₹10 lakh starting capital

# ── Execution engine ───────────────────────────────────────────────────────────
PAPER_TRADING_SLIPPAGE_BPS: Final[float] = 5.0       # 0.05 % slippage simulation
PAPER_TRADING_COMMISSION_BPS: Final[float] = 3.0     # 0.03 % commission

# Sharpe ratio annualisation factor (252 trading days)
SHARPE_ANNUALISE: Final[float] = 252.0 ** 0.5

# ── Sentiment ─────────────────────────────────────────────────────────────────
SENTIMENT_POSITIVE_KEYWORDS: Final[list[str]] = [
    "profit", "growth", "beat", "surge", "record", "strong", "rally",
    "upgrade", "outperform", "buy", "bullish",
]
SENTIMENT_NEGATIVE_KEYWORDS: Final[list[str]] = [
    "loss", "decline", "miss", "crash", "weak", "sell", "downgrade",
    "underperform", "bearish", "risk", "concern",
]
