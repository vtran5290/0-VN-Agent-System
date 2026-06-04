"""P0: v1.3 research dataset NaN hit labels and facts-only card."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.market.distribution_risk_lens.v13_research import (
    _assign_bucket,
    _compute_breadth_staleness,
    _hit_col,
)

REPO = Path(__file__).resolve().parents[1]
DATASET = REPO / "data" / "research" / "market_risk" / "distribution_v13_research_dataset.csv"
BUCKET_TBL = REPO / "data" / "research" / "market_risk" / "v13_breadth_bucket_probability_table.csv"
CARD = REPO / "data" / "research" / "market_risk" / "v13_daily_card_draft.md"
LATEST_JSON = REPO / "data" / "research" / "market_risk" / "distribution_risk_latest.json"


def test_hit_col_preserves_nan_on_synthetic():
    df = pd.DataFrame({"max_dd_25d": [np.nan, -0.06, -0.02]})
    _hit_col(df, "max_dd_25d", "<=", -0.05, "hit_max_dd_neg5pct_25d")
    assert pd.isna(df["hit_max_dd_neg5pct_25d"].iloc[0])
    assert df["hit_max_dd_neg5pct_25d"].iloc[1] == 1.0
    assert df["hit_max_dd_neg5pct_25d"].iloc[2] == 0.0


def test_hit_col_fwd_ret_nan():
    df = pd.DataFrame({"fwd_ret_25d": [np.nan, -0.06, 0.02]})
    _hit_col(df, "fwd_ret_25d", "<", 0, "end_ret_neg_25d")
    assert pd.isna(df["end_ret_neg_25d"].iloc[0])
    assert df["end_ret_neg_25d"].iloc[1] == 1.0
    assert df["end_ret_neg_25d"].iloc[2] == 0.0


@pytest.mark.skipif(not DATASET.is_file(), reason="run v1.3 pipeline first")
def test_dataset_nan_future_outcomes_have_nan_hit_labels():
    df = pd.read_csv(DATASET)
    m25 = df["max_dd_25d"].isna()
    for col in (
        "hit_max_dd_neg3pct_25d",
        "hit_max_dd_neg5pct_25d",
        "hit_max_dd_neg8pct_25d",
        "hit_max_dd_neg10pct_25d",
    ):
        assert df.loc[m25, col].isna().all(), f"{col} should be NaN when max_dd_25d is NaN"
    mfwd = df["fwd_ret_25d"].isna()
    assert df.loc[mfwd, "end_ret_neg_25d"].isna().all()
    assert df.loc[mfwd, "end_ret_le_neg5pct_25d"].isna().all()
    m75 = df["max_dd_75d"].isna()
    assert df.loc[m75, "hit_max_dd_neg10pct_75d"].isna().all()


@pytest.mark.skipif(not DATASET.is_file() or not BUCKET_TBL.is_file(), reason="run v1.3 pipeline first")
def test_bucket_table_excludes_nan_labels_from_base_rate():
    df = pd.read_csv(DATASET)
    tbl = pd.read_csv(BUCKET_TBL)
    row = tbl[(tbl["bucket_metric"] == "advancers_pct_5d_avg") & (tbl["bucket"] == "neutral")].iloc[0]
    cuts = [
        ("weak", None, 0.40),
        ("neutral", 0.40, 0.55),
        ("strong", 0.55, None),
    ]
    sub = df.copy()
    sub["bucket"] = _assign_bucket(sub["advancers_pct_5d_avg"].astype(float), cuts)
    # base_rate in bucket table is over full metric subset, not single bucket
    expected_base = float(sub["hit_max_dd_neg5pct_25d"].dropna().mean())
    assert abs(row["base_rate_hit_max_dd_neg5pct_25d"] - expected_base) < 1e-6
    grp = sub[sub["bucket"] == "neutral"]
    expected_cond = float(grp["hit_max_dd_neg5pct_25d"].dropna().mean())
    assert abs(row["p_hit_max_dd_neg5pct_25d"] - expected_cond) < 1e-6


@pytest.mark.skipif(not DATASET.is_file(), reason="run v1.3 pipeline first")
def test_incomplete_horizon_rows_do_not_bias_base_rate_downward():
    """Rows with NaN max_dd_25d must not count as non-events (0)."""
    df = pd.read_csv(DATASET)
    tail = df[df["max_dd_25d"].isna()].tail(25)
    assert tail["hit_max_dd_neg5pct_25d"].isna().all()
    known = df["hit_max_dd_neg5pct_25d"].dropna()
    if len(known) > 0:
        rate_with_nan_as_zero = float(
            df["hit_max_dd_neg5pct_25d"].fillna(0).mean()
        )
        rate_correct = float(known.mean())
        assert rate_with_nan_as_zero <= rate_correct


@pytest.mark.skipif(not CARD.is_file(), reason="run v1.3 pipeline first")
def test_daily_card_facts_only_no_probability_surface():
    text = CARD.read_text(encoding="utf-8")
    assert "probability surface" not in text.lower()
    assert "Status:" in text
    assert "### Safety" in text
    assert "final_action" in text
    assert "Walk-forward" not in text


@pytest.mark.skipif(not LATEST_JSON.is_file(), reason="run v1.3 pipeline first")
def test_latest_json_has_breadth_staleness_fields():
    data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    v13 = data.get("v13_research", {})
    assert "breadth_status" in v13
    assert "breadth_as_of" in v13
    assert "index_as_of" in v13
    assert "breadth_lag_sessions" in v13
    assert v13.get("changes_final_action") is False


def test_refresh_v13_json_from_artifacts_restores_block():
    from src.market.distribution_risk_lens.v13_research import refresh_v13_json_from_artifacts

    if not LATEST_JSON.is_file() or not DATASET.is_file():
        pytest.skip("run v1.3 pipeline first")
    data = refresh_v13_json_from_artifacts(LATEST_JSON)
    assert data is not None
    v13 = data.get("v13_research", {})
    assert v13.get("enabled") is True
    assert v13.get("changes_final_action") is False
    assert "breadth_status" in v13
    assert "breadth_as_of" in v13
    assert "index_as_of" in v13


@pytest.mark.skipif(not CARD.is_file(), reason="run v1.3 pipeline first")
def test_daily_card_has_asof_clarity_line():
    text = CARD.read_text(encoding="utf-8")
    assert "index_as_of" in text and "breadth_as_of" in text


def test_compute_breadth_staleness_stale_when_lag_gt_2():
    dates = [f"2026-05-{d:02d}" for d in range(10, 20)]
    df = pd.DataFrame(
        {
            "date": dates,
            "advancers_pct": [0.5] * 7 + [np.nan] * 3,
        }
    )
    st = _compute_breadth_staleness(df)
    assert st["breadth_status"] == "STALE_BREADTH_NEEDS_REFRESH"
    assert st["breadth_lag_sessions"] > 2
