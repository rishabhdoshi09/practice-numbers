"""
FeatureEngine: orchestrates all sub-modules and returns a unified feature dict.
This is the single entry point for the Decision Engine to consume.
"""
import pandas as pd

from .statistics import describe, zscore, distribution_fit, correlation_matrix
from .technical import (
    sma, ema, rsi, macd, bollinger_bands, atr, obv,
    trend_signal, momentum_signal,
)
from .timeseries import fit_arima, fit_garch
from .simulation import monte_carlo, gbm_signal, expected_return
from .ml_models import train_and_predict
from .sentiment import aggregate_sentiment

from backend.config import SMA_SHORT, SMA_LONG, EMA_SPAN


class FeatureEngine:
    """Computes all quantitative features for a given OHLCV DataFrame."""

    def compute(self, df: pd.DataFrame, news: list[dict]) -> dict:
        """
        Main computation pipeline.

        Args:
            df: OHLCV DataFrame indexed by date.
            news: List of news dicts with 'headline' and optional 'score'.

        Returns:
            Nested dict with all computed signals and metadata.
        """
        close  = df["Close"]
        high   = df["High"]
        low    = df["Low"]
        volume = df["Volume"]

        # ── Descriptive statistics ─────────────────────────────────────────────
        returns = close.pct_change().dropna()
        stats = describe(returns)
        dist  = distribution_fit(close)

        # ── Technical indicators (for metadata / chart enrichment) ─────────────
        sma_s = sma(close, SMA_SHORT)
        sma_l = sma(close, SMA_LONG)
        ema_v = ema(close, EMA_SPAN)
        rsi_v = rsi(close)
        macd_d = macd(close)
        bb = bollinger_bands(close)
        atr_v = atr(high, low, close)
        obv_v = obv(close, volume)
        latest_atr = float(atr_v.iloc[-1])

        # ── Sub-signals ────────────────────────────────────────────────────────
        trend_s      = trend_signal(close)
        momentum_s   = momentum_signal(close)
        arima_result = fit_arima(close)
        garch_result = fit_garch(close)
        mc_result    = monte_carlo(close)
        gbm_result   = gbm_signal(close)
        ml_result    = train_and_predict(df)
        exp_ret      = expected_return(close)
        sentiment    = aggregate_sentiment(news)

        # Mean reversion: Z-score of current price vs 20-day MA
        z = float(zscore(close).iloc[-1])
        mean_revert_s = float(-z / 3.0)   # overbought → negative, oversold → positive

        return {
            "symbol_stats": stats,
            "distribution": dist,
            "expected_return": exp_ret,
            "indicators": {
                "sma_short": round(float(sma_s.iloc[-1]), 2),
                "sma_long":  round(float(sma_l.iloc[-1]), 2),
                "ema":       round(float(ema_v.iloc[-1]), 2),
                "rsi":       round(float(rsi_v.iloc[-1]), 2),
                "macd":      round(float(macd_d["macd"].iloc[-1]), 4),
                "macd_signal": round(float(macd_d["signal"].iloc[-1]), 4),
                "macd_hist": round(float(macd_d["histogram"].iloc[-1]), 4),
                "bb_upper":  round(float(bb["upper"].iloc[-1]), 2),
                "bb_lower":  round(float(bb["lower"].iloc[-1]), 2),
                "bb_pct_b":  round(float(bb["pct_b"].iloc[-1]), 4),
                "atr":       round(latest_atr, 4),
                "obv":       round(float(obv_v.iloc[-1]), 0),
            },
            "signals": {
                "trend":       round(trend_s, 4),
                "momentum":    round(momentum_s, 4),
                "arima":       round(arima_result["signal"], 4),
                "volatility":  round(garch_result["signal"], 4),
                "gbm":         round(gbm_result["signal"], 4),
                "ml":          round(ml_result["signal"], 4),
                "sentiment":   round(sentiment["signal"], 4),
                "mean_revert": round(mean_revert_s, 4),
            },
            "model_details": {
                "arima":     arima_result,
                "garch":     garch_result,
                "monte_carlo": mc_result,
                "gbm":       gbm_result,
                "ml":        ml_result,
                "sentiment": sentiment,
            },
            "atr": latest_atr,
            "current_price": float(close.iloc[-1]),
            "chart_data": {
                "sma_short": sma_s.dropna().round(2).tolist()[-60:],
                "sma_long":  sma_l.dropna().round(2).tolist()[-60:],
                "ema":       ema_v.dropna().round(2).tolist()[-60:],
                "rsi":       rsi_v.dropna().round(2).tolist()[-60:],
                "dates":     [str(d.date()) for d in close.index[-60:]],
                "close":     close.round(2).tolist()[-60:],
            },
        }
