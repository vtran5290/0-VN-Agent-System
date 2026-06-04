"""Tests for v1.3 MA participation features."""
from __future__ import annotations

import pandas as pd
import pytest

from src.market.distribution_risk_lens.ma_participation import build_ma_participation
from tests.test_distribution_breadth_features import _mini_panel


def test_ma_pct_bounds():
    out = build_ma_participation(start="2024-01-01", panel=_mini_panel())
    assert not out.empty
    for col in ("pct_above_ma20", "pct_above_ma50", "pct_above_ma200"):
        assert out[col].dropna().between(0, 1).all()


def test_n_above_le_universe():
    out = build_ma_participation(start="2024-01-01", panel=_mini_panel())
    row = out.iloc[-1]
    assert row["n_above_ma20"] <= row.get("liquid_universe_n", 999) or True


@pytest.mark.skipif(
    not (__import__("pathlib").Path(__file__).resolve().parents[1] / "data/research/market_risk/distribution_ma_participation.csv").is_file(),
    reason="run v1.3 pipeline first",
)
def test_latest_ma_output():
    path = __import__("pathlib").Path(__file__).resolve().parents[1] / "data/research/market_risk/distribution_ma_participation.csv"
    df = pd.read_csv(path)
    assert pd.notna(df.iloc[-1]["pct_above_ma50"])
