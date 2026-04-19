"""
Descriptive statistics and Z-score normalisation helpers.
"""
import numpy as np
import pandas as pd
from scipy import stats as sp_stats


def describe(series: pd.Series) -> dict:
    """Return mean, variance, std-dev, skew, kurtosis."""
    return {
        "mean": float(series.mean()),
        "variance": float(series.var()),
        "std": float(series.std()),
        "skewness": float(sp_stats.skew(series.dropna())),
        "kurtosis": float(sp_stats.kurtosis(series.dropna())),
    }


def zscore(series: pd.Series) -> pd.Series:
    """Standardise a series to zero mean / unit variance."""
    mu, sigma = series.mean(), series.std()
    return (series - mu) / (sigma + 1e-10)


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation matrix across columns."""
    return df.pct_change().dropna().corr()


def distribution_fit(series: pd.Series) -> dict:
    """
    Fit both normal and log-normal distributions to *series*.
    Returns AIC-ranked parameters so callers know which fits better.
    """
    data = series.dropna().values
    # Normal fit
    mu_n, std_n = sp_stats.norm.fit(data)
    ll_n = np.sum(sp_stats.norm.logpdf(data, mu_n, std_n))
    aic_n = 2 * 2 - 2 * ll_n   # k=2 params

    # Log-normal fit (on positive price data)
    log_data = np.log(data[data > 0])
    mu_ln, std_ln = log_data.mean(), log_data.std()
    ll_ln = np.sum(sp_stats.norm.logpdf(log_data, mu_ln, std_ln))
    aic_ln = 2 * 2 - 2 * ll_ln

    return {
        "normal":   {"mu": mu_n,  "sigma": std_n,  "aic": aic_n},
        "lognormal": {"mu": mu_ln, "sigma": std_ln, "aic": aic_ln},
        "best_fit": "normal" if aic_n < aic_ln else "lognormal",
    }
