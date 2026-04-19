"""
Smoke tests for all five engines.
Run with: pytest backend/tests/ -v
"""
import pytest
import pandas as pd
import numpy as np

from backend.config import DEFAULT_SYMBOL
from backend.data_engine.dummy_data import generate_ohlcv, generate_news
from backend.feature_engine.engine import FeatureEngine
from backend.decision_engine.engine import DecisionEngine
from backend.risk_engine.engine import RiskEngine
from backend.execution_engine.engine import ExecutionEngine


@pytest.fixture(scope="module")
def sample_df():
    return generate_ohlcv(DEFAULT_SYMBOL, days=200)


@pytest.fixture(scope="module")
def features(sample_df):
    news = generate_news(DEFAULT_SYMBOL)
    return FeatureEngine().compute(sample_df, news)


class TestDataEngine:
    def test_ohlcv_shape(self, sample_df):
        assert len(sample_df) == 200
        assert set(sample_df.columns) == {"Open", "High", "Low", "Close", "Volume"}

    def test_no_nan(self, sample_df):
        assert not sample_df.isnull().any().any()

    def test_ohlc_consistency(self, sample_df):
        assert (sample_df["High"] >= sample_df["Low"]).all()
        assert (sample_df["High"] >= sample_df["Close"]).all()
        assert (sample_df["Low"]  <= sample_df["Close"]).all()

    def test_news_structure(self):
        news = generate_news(DEFAULT_SYMBOL)
        assert len(news) > 0
        assert "headline" in news[0]
        assert "sentiment" in news[0]


class TestFeatureEngine:
    def test_signals_in_range(self, features):
        for name, val in features["signals"].items():
            assert -1.0 <= val <= 1.0, f"Signal '{name}' = {val} out of [-1,1]"

    def test_indicators_present(self, features):
        expected = ["rsi", "macd", "atr", "ema", "sma_short", "sma_long"]
        for k in expected:
            assert k in features["indicators"], f"Missing indicator: {k}"

    def test_ml_output(self, features):
        ml = features["model_details"]["ml"]
        assert 0 <= ml["ensemble_probability_up"] <= 1
        assert -1 <= ml["signal"] <= 1


class TestDecisionEngine:
    def test_decision_fields(self, features):
        decision = DecisionEngine().decide(features["signals"], features)
        assert decision["action"] in ("BUY", "SELL", "HOLD")
        assert 0 <= decision["confidence"] <= 100
        assert decision["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    def test_signal_breakdown_complete(self, features):
        decision = DecisionEngine().decide(features["signals"], features)
        assert len(decision["signal_breakdown"]) == len(features["signals"])


class TestRiskEngine:
    def test_var_positive(self, sample_df):
        risk = RiskEngine().compute(sample_df, current_price=2850.0, atr=45.0)
        assert risk["var"]["var_95_pct"] >= 0
        assert risk["var"]["var_99_pct"] >= risk["var"]["var_95_pct"]

    def test_stop_below_price(self, sample_df):
        price = 2850.0
        risk = RiskEngine().compute(sample_df, current_price=price, atr=45.0)
        assert risk["stop_loss"]["price"] < price

    def test_kelly_within_bounds(self, sample_df):
        risk = RiskEngine().compute(sample_df, current_price=2850.0, atr=45.0)
        pct = risk["position_sizing"]["recommended_pct"]
        assert 0 <= pct <= 20   # max 20 %


class TestExecutionEngine:
    def test_buy_reduces_cash(self):
        eng = ExecutionEngine(starting_capital=1_000_000)
        eng.execute("RELIANCE.NS", "BUY", 2850.0, 50_000)
        assert eng.cash < 1_000_000

    def test_sell_rejected_without_position(self):
        eng = ExecutionEngine(starting_capital=1_000_000)
        result = eng.execute("RELIANCE.NS", "SELL", 2850.0, 50_000)
        assert result["status"] == "rejected"

    def test_roundtrip_pnl_tracked(self):
        eng = ExecutionEngine(starting_capital=1_000_000)
        eng.execute("RELIANCE.NS", "BUY",  2850.0, 100_000)
        eng.execute("RELIANCE.NS", "SELL", 3000.0, 100_000)
        assert len(eng.daily_pnl) == 1
        assert eng.daily_pnl[0] > 0   # bought low, sold high
