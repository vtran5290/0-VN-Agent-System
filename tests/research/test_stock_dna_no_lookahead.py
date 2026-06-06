"""
Tests 1-2: No-lookahead bias for MA/EMA and ATR computations.
Validates that perturbing future prices does not change feature values before the perturbation point.
"""
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.features import compute_indicators


def _make_panel(n: int = 300, n_syms: int = 2) -> pd.DataFrame:
    rng = np.random.default_rng(77)
    rows = []
    for sym in [f"SYM{i}" for i in range(n_syms)]:
        dates = pd.date_range("2018-01-01", periods=n, freq="B")
        close = np.cumprod(1 + rng.normal(0.001, 0.015, n)) * 50
        high  = close * (1 + np.abs(rng.normal(0, 0.005, n)))
        low   = close * (1 - np.abs(rng.normal(0, 0.005, n)))
        rows.append(pd.DataFrame({
            "symbol": sym,
            "date":   dates,
            "open":   close,
            "high":   high,
            "low":    low,
            "close":  close,
            "volume": rng.uniform(1e5, 1e6, n),
            "value":  close * rng.uniform(1e5, 1e6, n),
        }))
    return pd.concat(rows, ignore_index=True)


def _check_no_lookahead(col: str, perturb_from: int = 150) -> None:
    """
    Perturb close/high/low from bar perturb_from onward.
    Verify that feature values before perturb_from are unchanged.
    """
    df1 = _make_panel(300)
    df2 = df1.copy()
    df2.loc[df2.index[perturb_from:], "close"] *= 10.0
    df2.loc[df2.index[perturb_from:], "high"]  *= 10.0
    df2.loc[df2.index[perturb_from:], "low"]   *= 10.0
    df2.loc[df2.index[perturb_from:], "value"] *= 10.0

    r1 = compute_indicators(df1.copy())
    r2 = compute_indicators(df2.copy())

    if col not in r1.columns:
        pytest.skip(f"Column {col} not in indicators output")

    # Only check first symbol rows before perturb_from
    sym0 = r1["symbol"].unique()[0]
    pre1 = r1[r1["symbol"] == sym0].iloc[:perturb_from][col].fillna(-9999).reset_index(drop=True)
    pre2 = r2[r2["symbol"] == sym0].iloc[:perturb_from][col].fillna(-9999).reset_index(drop=True)
    diff = (pre1 - pre2).abs().max()
    assert diff < 1e-6, (
        f"{col}: future perturbation changed past values (max diff={diff:.2e}) — lookahead bias!"
    )


# ── Test 1: MA / EMA no lookahead ─────────────────────────────────────────────

class TestMAEMANoLookahead:

    def test_ema20_no_lookahead(self):
        _check_no_lookahead("ema20")

    def test_ema50_no_lookahead(self):
        _check_no_lookahead("ema50")

    def test_sma100_no_lookahead(self):
        _check_no_lookahead("sma100")

    def test_sma150_no_lookahead(self):
        _check_no_lookahead("sma150")

    def test_ema20_warmup_nonnull(self):
        """EMA20 should produce non-null values after warmup period."""
        df = _make_panel(100)
        result = compute_indicators(df)
        sym0 = result["symbol"].unique()[0]
        vals = result[result["symbol"] == sym0]["ema20"].iloc[25:]
        assert not vals.isna().all(), "EMA20 should be non-NaN after warmup"

    def test_sma100_warmup_nonnull(self):
        """SMA100 should produce non-null values after 50 bars (min_periods = w//2)."""
        df = _make_panel(200)
        result = compute_indicators(df)
        sym0 = result["symbol"].unique()[0]
        vals = result[result["symbol"] == sym0]["sma100"].iloc[55:]
        assert not vals.isna().all(), "SMA100 should be non-NaN after min_periods"


# ── Test 2: ATR14 no lookahead ────────────────────────────────────────────────

class TestATR14NoLookahead:

    def test_atr14_no_lookahead(self):
        _check_no_lookahead("atr14")

    def test_atr14_positive_after_warmup(self):
        """ATR14 must always be positive (it's a range measure)."""
        df = _make_panel(100)
        result = compute_indicators(df)
        sym0 = result["symbol"].unique()[0]
        atr = result[result["symbol"] == sym0]["atr14"].dropna()
        assert (atr > 0).all(), "ATR14 should always be positive"

    def test_adv20_no_lookahead(self):
        _check_no_lookahead("adv20_vnd")

    def test_adv50_no_lookahead(self):
        _check_no_lookahead("adv50_vnd")
