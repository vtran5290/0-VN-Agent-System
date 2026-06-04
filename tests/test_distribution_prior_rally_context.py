"""Tests for v1.3 prior rally context."""
from __future__ import annotations

import pandas as pd
import pytest

from src.market.distribution_risk_lens.prior_rally import build_prior_rally_context


def test_prior_buckets():
    out = build_prior_rally_context(start="2018-01-01")
    assert not out.empty
    assert set(out["prior_20d_return_bucket"].dropna().unique()).issubset(
        {"cold", "normal", "hot", "unknown"}
    )


@pytest.mark.skipif(
    not (__import__("pathlib").Path(__file__).resolve().parents[1] / "data/research/market_risk/distribution_prior_rally_context.csv").is_file(),
    reason="run v1.3 pipeline first",
)
def test_latest_prior_rally():
    df = pd.read_csv(
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "data/research/market_risk/distribution_prior_rally_context.csv"
    )
    assert pd.notna(df.iloc[-1]["ret_20d"])
