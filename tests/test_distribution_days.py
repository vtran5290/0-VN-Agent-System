"""Unit tests for distribution day definitions and forward outcomes."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.market.distribution_risk_lens.definitions import dist_day_flag
from src.market.distribution_risk_lens.features import build_features
from src.market.distribution_risk_lens.outcomes import attach_forward_outcomes


def _sample_ohlcv(n: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-01", periods=n)
    close = 1000 * (1 + rng.normal(0, 0.005, n)).cumprod()
    volume = rng.integers(1_000_000, 5_000_000, n)
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": volume,
        }
    )


def test_dist_day_uses_only_prior_bar():
    df = pd.DataFrame(
        {
            "close": [100.0, 99.0, 100.0],
            "volume": [1000.0, 2000.0, 500.0],
            "high": [100.0, 99.5, 100.5],
            "low": [99.5, 98.5, 99.5],
        }
    )
    flags = dist_day_flag(df, variant="base")
    assert flags.iloc[0] is False or flags.iloc[0] == False
    assert bool(flags.iloc[1]) is True
    assert bool(flags.iloc[2]) is False


def test_forward_returns_shifted_correctly():
    df = _sample_ohlcv(40)
    feat = build_features(df, index_view="test")
    full = attach_forward_outcomes(feat)
    c = full["close"].astype(float)
    for h in (5, 10, 25):
        expected = c.shift(-h) / c - 1.0
        pd.testing.assert_series_equal(
            full[f"fwd_ret_{h}d"],
            expected,
            check_names=False,
            atol=1e-12,
        )


def test_max_drawdown_uses_future_window_only():
    df = pd.DataFrame(
        {
            "date": pd.bdate_range("2020-01-01", periods=6),
            "close": [100.0, 105.0, 90.0, 95.0, 110.0, 108.0],
            "volume": [1e6] * 6,
        }
    )
    feat = build_features(df, index_view="t")
    full = attach_forward_outcomes(feat)
    # at t=0, 5d window includes drop to 90 from peak 105 -> dd about -14.3%
    mdd0 = full["max_dd_5d"].iloc[0]
    assert mdd0 < -0.10
    assert pd.isna(full["max_dd_5d"].iloc[-1])


def test_correction_flag_5pct():
    df = pd.DataFrame(
        {
            "date": pd.bdate_range("2020-01-01", periods=8),
            "close": [100.0, 100.0, 94.0, 96.0, 97.0, 98.0, 99.0, 100.0],
            "volume": [1e6] * 8,
        }
    )
    full = attach_forward_outcomes(build_features(df, index_view="t"))
    assert full["hit_correction_5pct_next_5d"].iloc[0] == 1.0
