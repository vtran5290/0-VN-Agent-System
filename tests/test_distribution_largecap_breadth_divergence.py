"""Tests for v1.3 large-cap breadth divergence."""
from __future__ import annotations

import pandas as pd
import pytest

from src.market.distribution_risk_lens.largecap_divergence import build_largecap_divergence
from tests.test_distribution_breadth_features import _mini_panel


def test_divergence_flags_binary():
    out = build_largecap_divergence(start="2024-01-01", panel=_mini_panel())
    if out.empty:
        pytest.skip("insufficient mini data")
    assert set(out["largecap_breadth_divergence_flag"].dropna().unique()).issubset({0, 1})


@pytest.mark.skipif(
    not (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "data/research/market_risk/distribution_largecap_breadth_divergence.csv"
    ).is_file(),
    reason="run v1.3 pipeline first",
)
def test_latest_largecap_output():
    df = pd.read_csv(
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "data/research/market_risk/distribution_largecap_breadth_divergence.csv"
    )
    assert "top30_advancers_minus_all_advancers" in df.columns
