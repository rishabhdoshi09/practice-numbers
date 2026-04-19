"""
Machine-learning classifiers for price direction prediction.

Models:
  1. Logistic Regression — fast, interpretable baseline
  2. Random Forest — non-linear, ensemble secondary model

Features: lagged returns, RSI, volume delta, rolling volatility.
"""
import logging
import numpy as np
import pandas as pd
from typing import Optional

from backend.config import ML_LOOKBACK_LAGS, ML_TEST_SPLIT, RANDOM_STATE
from .technical import rsi as compute_rsi, ema as compute_ema

logger = logging.getLogger(__name__)


def _build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Engineer ML features from OHLCV DataFrame.
    Target: 1 if next-day close > today's close, else 0.
    """
    close  = df["Close"]
    volume = df["Volume"]

    feat = pd.DataFrame(index=df.index)

    # Lagged returns
    for lag in range(1, ML_LOOKBACK_LAGS + 1):
        feat[f"ret_lag_{lag}"] = close.pct_change(lag)

    # RSI
    feat["rsi"] = compute_rsi(close)

    # Volume delta (% change vs 5d avg)
    feat["vol_delta"] = volume / (volume.rolling(5).mean() + 1) - 1

    # Rolling 10d volatility
    feat["vol_10d"] = close.pct_change().rolling(10).std()

    # EMA slope (normalised)
    ema_vals = compute_ema(close)
    feat["ema_slope"] = ema_vals.pct_change(3)

    # Target: 1 if price goes up next day
    target = (close.shift(-1) > close).astype(int)

    # Align and drop NaN rows
    combined = pd.concat([feat, target.rename("target")], axis=1).dropna()
    # Drop last row (target is NaN for true last day)
    combined = combined.iloc[:-1]

    X = combined.drop("target", axis=1)
    y = combined["target"]
    return X, y


def train_and_predict(df: pd.DataFrame) -> dict:
    """
    Train both classifiers on historical data and predict direction for today.
    Returns an ensemble signal averaged from both models.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score

    X, y = _build_features(df)

    if len(X) < 60:   # need at least 60 samples for meaningful train/test
        logger.warning("Insufficient ML data (%d samples)", len(X))
        return _fallback_signal()

    split = int(len(X) * (1 - ML_TEST_SPLIT))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    # Scale features (critical for Logistic Regression)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    # ── Logistic Regression ───────────────────────────────────────────────────
    lr = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE, C=0.1)
    lr.fit(X_train_s, y_train)
    lr_pred  = lr.predict(X_test_s)
    lr_acc   = float(accuracy_score(y_test, lr_pred))
    lr_proba = float(lr.predict_proba(scaler.transform(X.iloc[[-1]]))[0][1])

    # ── Random Forest ─────────────────────────────────────────────────────────
    rf = RandomForestClassifier(n_estimators=100, max_depth=6,
                                random_state=RANDOM_STATE, n_jobs=-1)
    rf.fit(X_train, y_train)
    rf_pred  = rf.predict(X_test)
    rf_acc   = float(accuracy_score(y_test, rf_pred))
    rf_proba = float(rf.predict_proba(X.iloc[[-1]])[0][1])

    # Accuracy-weighted ensemble probability
    total_acc = lr_acc + rf_acc + 1e-10
    ensemble_proba = (lr_proba * lr_acc + rf_proba * rf_acc) / total_acc

    # Map P(up) from [0,1] to [-1,+1]
    signal = float(np.clip((ensemble_proba - 0.5) * 4, -1, 1))

    # Feature importances from RF
    feature_importances = dict(zip(X.columns, rf.feature_importances_.round(4)))

    return {
        "logistic_regression": {
            "probability_up": round(lr_proba, 4),
            "test_accuracy": round(lr_acc, 4),
            "signal": round((lr_proba - 0.5) * 4, 4),
        },
        "random_forest": {
            "probability_up": round(rf_proba, 4),
            "test_accuracy": round(rf_acc, 4),
            "signal": round((rf_proba - 0.5) * 4, 4),
        },
        "ensemble_probability_up": round(ensemble_proba, 4),
        "signal": round(signal, 4),
        "feature_importances": feature_importances,
    }


def _fallback_signal() -> dict:
    return {
        "logistic_regression": {"probability_up": 0.5, "test_accuracy": None, "signal": 0.0},
        "random_forest": {"probability_up": 0.5, "test_accuracy": None, "signal": 0.0},
        "ensemble_probability_up": 0.5,
        "signal": 0.0,
        "feature_importances": {},
    }
