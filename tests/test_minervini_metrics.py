from __future__ import annotations

import numpy as np
import pandas as pd

from src.screeners.minervini_metrics import (
    add_indicators,
    compute_rs,
    compute_volume_profile_metrics,
    detect_best_base,
    score_ticker,
)


def _mock_ohlcv(n: int = 320, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-01", periods=n)
    drift = np.linspace(0, 30, n)
    noise = rng.normal(0, 0.7, n).cumsum()
    close = 50 + drift + noise
    open_ = close * (1 + rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.015, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.015, n))
    volume = rng.integers(2_000_000, 7_000_000, size=n)
    return pd.DataFrame({"date": dates, "open": open_, "high": high, "low": low, "close": close, "volume": volume})


def test_score_range_and_components():
    stock = add_indicators(_mock_ohlcv())
    bench = add_indicators(_mock_ohlcv(seed=8))
    weekly = add_indicators(stock.set_index("date").resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index())
    rs = compute_rs(stock, bench)
    vp = compute_volume_profile_metrics(stock, vp_bins=100, value_area_pct=0.7)
    base = detect_best_base(stock)
    sc = score_ticker(stock, rs, weekly, vp, base)
    assert 0 <= sc["total_score"] <= 20
    assert all(0 <= int(v) <= 2 for v in sc["scores"].values())


def test_vp_outputs_shape():
    stock = add_indicators(_mock_ohlcv())
    vp = compute_volume_profile_metrics(stock, vp_bins=80, value_area_pct=0.7)
    for k in ["short", "mid", "long"]:
        assert "poc" in vp[k]
        assert "val" in vp[k]
        assert "vah" in vp[k]
