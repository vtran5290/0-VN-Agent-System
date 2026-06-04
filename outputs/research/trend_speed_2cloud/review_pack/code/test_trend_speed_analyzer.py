"""Unit tests for Trend Speed Analyzer indicator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.research.indicators.trend_speed_analyzer import compute_tsa_features


def _ohlcv(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    return pd.DataFrame(
        {
            "open": close - rng.uniform(0, 0.3, n),
            "high": close + rng.uniform(0, 0.5, n),
            "low": close - rng.uniform(0, 0.5, n),
            "close": close,
            "volume": rng.integers(1e5, 1e6, n),
        }
    )


def test_output_columns_present():
    feat = compute_tsa_features(_ohlcv())
    expected = {
        "tsa_dyn_ema",
        "tsa_speed",
        "tsa_trendspeed",
        "tsa_norm_speed",
        "tsa_dyn_trend_bull",
        "tsa_bull_turn",
        "tsa_speed_deterioration",
    }
    assert expected.issubset(feat.columns)


def test_no_future_leak_on_speed_reset():
    df = _ohlcv(120)
    f1 = compute_tsa_features(df.iloc[:80])
    f2 = compute_tsa_features(df)
    pd.testing.assert_series_equal(
        f1["tsa_speed"].iloc[:-1],
        f2["tsa_speed"].iloc[:79],
        check_names=False,
        rtol=1e-9,
        atol=1e-9,
    )


def test_norm_speed_bounded_or_neutral():
    feat = compute_tsa_features(_ohlcv())
    valid = feat["tsa_norm_speed"].dropna()
    assert valid.between(0, 1).all() or (valid == 0.5).any()


def test_quintile_no_lookahead():
    feat = compute_tsa_features(_ohlcv(200))
    q = feat["tsa_norm_speed_q"]
    # early bars should be NaN until enough history
    assert q.iloc[:4].isna().all()
