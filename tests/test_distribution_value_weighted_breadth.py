"""Tests for v1.3 value-weighted breadth."""
from __future__ import annotations

import pandas as pd
import pytest

from src.market.distribution_risk_lens.value_weighted_breadth import build_value_weighted_breadth
from tests.test_distribution_breadth_features import _mini_panel


def test_value_pct_sum_when_positive():
    out = build_value_weighted_breadth(start="2024-01-01", panel=_mini_panel())
    pos = out[out["total_value_traded_liquid"] > 0]
    if not pos.empty:
        s = pos["advancing_value_pct"] + pos["declining_value_pct"] + pos["unchanged_value_pct"]
        assert (s - 1.0).abs().max() < 0.02


@pytest.mark.skipif(
    not (__import__("pathlib").Path(__file__).resolve().parents[1] / "data/research/market_risk/distribution_value_weighted_breadth.csv").is_file(),
    reason="run v1.3 pipeline first",
)
def test_latest_value_breadth():
    df = pd.read_csv(
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "data/research/market_risk/distribution_value_weighted_breadth.csv"
    )
    assert pd.notna(df.iloc[-1]["advancing_value_pct"])
