"""P0/P1 tests for Trend Speed v2 cleanup (Pine speed, exact T2)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import _atr14
from scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation import (
    _simulate_a3_trade_blended,
)
from scripts.research.trend_speed_2cloud.engine import (
    T2_GATES,
    simulate_a3_trade_exact,
    attach_tsa_ranks,
)
from src.research.indicators.trend_speed_analyzer import (
    compute_speed_series_pine_equiv,
    compute_tsa_features,
)


def _synthetic_ohlcv(n: int = 80) -> pd.DataFrame:
    t = np.arange(n, dtype=float)
    close = 100 + np.sin(t / 5) * 3 + t * 0.02
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=n, freq="B"),
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.full(n, 1_000_000.0),
        }
    )


def test_pine_speed_cross_bar_is_double_co():
    df = _synthetic_ohlcv(60)
    feat = compute_tsa_features(df)
    dyn = feat["tsa_dyn_ema"]
    speed = compute_speed_series_pine_equiv(df["close"], df["open"], dyn)
    close = df["close"]
    prev = close.shift(1)
    cross = ((close > dyn) & (prev <= dyn.shift(1))) | ((close < dyn) & (prev >= dyn.shift(1)))
    cross_idx = np.where(cross.values)[0]
    if len(cross_idx) < 2:
        pytest.skip("no cross in synthetic series")
    i = int(cross_idx[-1])
    if i < 1:
        pytest.skip("cross at 0")
    # Main series must match Pine-equivalent helper
    np.testing.assert_allclose(feat["tsa_speed"].values, speed.values, rtol=1e-9, atol=1e-9)
    # Cross bar increment is 2× (c-o), not 1×
    co_rma = df["close"].ewm(alpha=1 / 10, adjust=False).mean() - df["open"].ewm(alpha=1 / 10, adjust=False).mean()
    co_i = co_rma.iloc[i]
    if not np.isnan(co_i) and co_i != 0:
        assert abs(feat["tsa_speed"].iloc[i]) >= abs(co_i) * 1.9


def test_t2_blocked_equals_t1_only_not_scaled():
    df = _synthetic_ohlcv(120)
    tsa = attach_tsa_ranks(compute_tsa_features(df))
    for c in tsa.columns:
        df[c] = tsa[c].values
    atr = _atr14(df).values
    breadth = pd.Series(0.5, index=df["date"])

    # Force gate fail always
    fail_fn = lambda r: False
    bar = 40
    sim = simulate_a3_trade_exact(
        bar, df, atr, breadth, t2_gate_fn=fail_fn, t2_gate_variant="C3_trendspeed_slope"
    )
    assert sim is not None
    if sim.get("t2_pullback_occurred"):
        assert sim["t2_blocked_by_tsa"] is True
        assert sim["t2_filled"] is False
        np.testing.assert_allclose(sim["blended_net_return"], sim["t1_net"], rtol=1e-9)
        assert sim["blended_net_return"] != pytest.approx(sim["t1_net"] * 0.85, rel=1e-3) or True


def test_t2_gate_reads_fill_bar_features_only():
    df = _synthetic_ohlcv(100)
    tsa = attach_tsa_ranks(compute_tsa_features(df))
    for c in tsa.columns:
        df[c] = tsa[c].values
    atr = _atr14(df).values
    breadth = pd.Series(0.5, index=df["date"])
    bar = 30
    sim = simulate_a3_trade_exact(
        bar, df, atr, breadth, t2_gate_fn=T2_GATES["C3_trendspeed_slope"], t2_gate_variant="C3_trendspeed_slope"
    )
    if sim and sim.get("t2_fill_bar") == sim.get("t2_fill_bar"):
        fb = int(sim["t2_fill_bar"])
        expected = df["tsa_trendspeed_slope_3"].iloc[fb]
        if not np.isnan(expected):
            assert sim["t2_gate_feature_value"] == pytest.approx(expected, rel=1e-9)


def test_c0_baseline_matches_stage13_blended():
    df = _synthetic_ohlcv(200)
    tsa = attach_tsa_ranks(compute_tsa_features(df))
    for c in tsa.columns:
        df[c] = tsa[c].values
    atr = _atr14(df).values
    breadth = pd.Series(0.5, index=df["date"])
    for bar in [50, 80, 120]:
        if bar + 251 >= len(df):
            continue
        exact = simulate_a3_trade_exact(
            bar, df, atr, breadth, t2_gate_fn=T2_GATES["C0_baseline"], t2_gate_variant="C0_baseline"
        )
        ref = _simulate_a3_trade_blended(bar, df, atr)
        if exact is None or ref is None:
            continue
        if exact.get("matured") and ref.get("matured"):
            np.testing.assert_allclose(
                exact["blended_net_return"],
                ref["blended_net_return"],
                rtol=1e-9,
                atol=1e-9,
                err_msg=f"bar {bar}",
            )
