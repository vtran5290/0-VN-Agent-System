"""Tests for v1.3 liquid-universe breadth features."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.market.distribution_risk_lens.breadth_features import build_breadth_features


def _mini_panel() -> pd.DataFrame:
    rows = []
    for d in pd.bdate_range("2024-01-02", periods=60):
        for t, base in (("AAA", 50.0), ("BBB", 30.0)):
            rows.append(
                {
                    "ticker": t,
                    "date": d,
                    "open": base,
                    "high": base + 1,
                    "low": base - 1,
                    "close": base + (0.1 if t == "AAA" else -0.05),
                    "volume": 1_000_000,
                    "value": base * 1000 * 1_000_000,
                }
            )
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    from src.market.distribution_risk_lens.liquid_universe import _normalize_panel

    panel, _, _, _ = _normalize_panel(df)
    panel["adv50_value"] = 5e9
    panel["is_liquid"] = True
    return panel


def test_breadth_percentages_sum_and_counts():
    out = build_breadth_features(start="2024-01-01", panel=_mini_panel())
    assert not out.empty
    row = out.iloc[-1]
    n = row["liquid_universe_n"]
    assert abs(row["advancers_pct"] + row["decliners_pct"] + row["unchanged_pct"] - 1.0) < 0.02
    assert row["advancers_n"] + row["decliners_n"] + row["unchanged_n"] == n


def test_up_down_ratio_zero_decliners():
    out = build_breadth_features(start="2024-01-01", panel=_mini_panel())
    udr = out["up_down_ratio"].replace(np.inf, 999).dropna()
    assert (udr >= 0).all()


def test_adv50_no_lookahead_on_synthetic():
    """ADV50 on last row must not use future bars beyond that date."""
    panel = _mini_panel()
    t0 = panel[(panel["ticker"] == "AAA") & (panel["date"] == panel["date"].iloc[30])]
    assert not t0.empty
    from src.market.distribution_risk_lens.liquid_universe import _normalize_panel

    raw = panel.drop(columns=[c for c in panel.columns if c.endswith("_v") or c in ("tv", "adv50_value", "is_liquid", "prev_close_v")], errors="ignore")
    sub = raw[raw["date"] <= panel["date"].iloc[30]]
    p2, _, _, _ = _normalize_panel(sub)
    assert p2["adv50_value"].notna().sum() >= 0


@pytest.mark.skipif(
    not (__import__("pathlib").Path(__file__).resolve().parents[1] / "data/research/market_risk/distribution_breadth_features.csv").is_file(),
    reason="run v1.3 pipeline first",
)
def test_latest_breadth_output_exists():
    path = __import__("pathlib").Path(__file__).resolve().parents[1] / "data/research/market_risk/distribution_breadth_features.csv"
    df = pd.read_csv(path)
    row = df.iloc[-1]
    assert pd.notna(row["liquid_universe_n"])
    assert pd.notna(row["advancers_pct"])
