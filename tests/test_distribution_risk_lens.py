"""Integration tests for Distribution Risk Lens pipeline pieces."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.market.distribution_risk_lens.buckets import build_probability_table, confidence_label
from src.market.distribution_risk_lens.events import run_event_study
from src.market.distribution_risk_lens.features import build_features
from src.market.distribution_risk_lens.index_views import VIN_SYMBOLS
from src.market.distribution_risk_lens.outcomes import attach_forward_outcomes
from src.market.distribution_risk_lens.warnings import (
    snapshot_probabilities,
    vin_distortion_flag,
    warning_disagreement,
    warning_state_row,
)

REPO = Path(__file__).resolve().parents[1]
LATEST_JSON = REPO / "data" / "research" / "market_risk" / "distribution_risk_latest.json"


def _synthetic_full(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2018-01-01", periods=n)
    close = 1000 * (1 + rng.normal(0, 0.004, n)).cumprod()
    vol = rng.integers(1e6, 3e6, n)
    df = pd.DataFrame({"date": dates, "close": close, "volume": vol, "high": close * 1.01, "low": close * 0.99})
    feat = build_features(df, index_view="vnindex_raw")
    feat["dist_count_25d"] = feat["dist_day_flag"].rolling(25, min_periods=1).sum()
    feat["dist_count_10d"] = feat["dist_day_flag"].rolling(10, min_periods=1).sum()
    feat["dist_count_50d"] = feat["dist_day_flag"].rolling(50, min_periods=1).sum()
    return attach_forward_outcomes(feat)


def test_bucket_table_has_base_rate_and_lift():
    full = _synthetic_full()
    tbl = build_probability_table(full, index_view="vnindex_raw")
    assert not tbl.empty
    assert "base_rate_p_ret_neg" in tbl.columns
    assert "lift_p_ret_neg" in tbl.columns
    row = tbl[(tbl["metric"] == "dist_count_25d") & (tbl["horizon_d"] == 25)].iloc[0]
    assert row["n"] >= 1
    assert row["confidence"] in ("LOW", "MEDIUM", "HIGH")


def test_declustered_events_do_not_overlap_within_skip():
    full = _synthetic_full(300)
    full.loc[full.index[50:60], "dist_count_25d"] = 5
    full.loc[full.index[55], "dist_count_25d"] = 5
    ev = run_event_study(full, index_view="t", skip_days=25)
    if len(ev) >= 2:
        idx0 = full.index[full["date"] == ev["event_date"].iloc[0]][0]
        idx1 = full.index[full["date"] == ev["event_date"].iloc[1]][0]
        assert idx1 - idx0 >= 25


def test_ex_vin_proxy_labelled_in_latest_json():
    if not LATEST_JSON.is_file():
        pytest.skip("run distribution-risk pipeline first")
    data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    views = data.get("index_views_available", [])
    if "ex_vin_proxy" in views:
        ex = data.get("ex_vin_proxy", {})
        assert ex.get("is_proxy") is True or data.get("primary_view") == "ex_vin_proxy"


def test_vin_distortion_detected():
    assert vin_distortion_flag(0.05, 0.01, None, None) is True
    assert vin_distortion_flag(0.01, 0.01, 0.02, 0.02) is False


def test_warning_states_deterministic():
    row = pd.Series({"dist_count_25d": 0, "close_above_ema20": 1, "close_above_ema50": 1, "close": 100})
    assert warning_state_row(row) == "NORMAL"
    row2 = pd.Series({"dist_count_25d": 4, "close_above_ema20": 0, "close_above_ema50": 1, "close": 100})
    assert warning_state_row(row2) == "CORRECTION_RISK"


def test_warning_disagreement():
    assert warning_disagreement("CORRECTION_RISK", "NORMAL") is True
    assert warning_disagreement("NORMAL", "CAUTION") is False


def test_latest_json_required_keys():
    if not LATEST_JSON.is_file():
        pytest.skip("run distribution-risk pipeline first")
    data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    for key in (
        "as_of_date",
        "data_start",
        "data_end",
        "method_version",
        "index_views_available",
        "primary_view",
        "vnindex_raw",
        "safety_note",
    ):
        assert key in data
    assert "final_action" not in data


def test_confidence_labels():
    assert confidence_label(10) == "LOW"
    assert confidence_label(50) == "MEDIUM"
    assert confidence_label(120) == "HIGH"


def test_vin_symbols_exclude_vpl_by_default():
    assert "VPL" not in VIN_SYMBOLS
    assert set(VIN_SYMBOLS) == {"VIC", "VHM", "VRE"}


def test_snapshot_probabilities_empty_bucket():
    tbl = pd.DataFrame(columns=["index_view", "metric", "bucket", "horizon_d", "n", "p_ret_neg", "confidence"])
    out = snapshot_probabilities(tbl, index_view="x", bucket="99")
    assert out["confidence"] == "LOW"


def test_vin_group_missing_volume_must_not_be_normal():
    dates = pd.bdate_range("2020-01-01", periods=30)
    df = pd.DataFrame(
        {
            "date": dates,
            "close": [1000.0] * 30,
            "volume": [np.nan] * 30,
            "high": [1000.0] * 30,
            "low": [1000.0] * 30,
        }
    )
    feat = build_features(df, index_view="vin_group", distribution_volume_available=False)
    assert feat["dist_day_flag"].isna().all()
    assert feat["dist_count_25d"].isna().all()
    row = feat.iloc[-1]
    assert warning_state_row(row) == "UNKNOWN"


def test_probability_table_includes_neg10pct_column():
    full = _synthetic_full()
    tbl = build_probability_table(full, index_view="vnindex_raw")
    assert "p_max_dd_le_neg10pct" in tbl.columns
    assert "base_rate_p_max_dd_le_neg10pct" in tbl.columns
    row75 = tbl[(tbl["horizon_d"] == 75) & (tbl["metric"] == "dist_count_25d")].iloc[0]
    p5 = row75["p_max_dd_le_neg5pct"]
    p10 = row75["p_max_dd_le_neg10pct"]
    assert p10 <= p5 or (pd.isna(p5) and pd.notna(p10))


def test_snapshot_10pct_correction_uses_neg10_not_neg5():
    tbl = pd.DataFrame(
        [
            {
                "index_view": "t",
                "metric": "dist_count_25d",
                "bucket": "2",
                "horizon_d": 75,
                "n": 120,
                "p_ret_neg": 0.4,
                "p_max_dd_le_neg5pct": 0.55,
                "p_max_dd_le_neg10pct": 0.22,
                "base_rate_p_ret_neg": 0.41,
                "base_rate_p_max_dd_le_neg10pct": 0.25,
                "lift_p_ret_neg": 0.0,
                "confidence": "HIGH",
            }
        ]
    )
    out = snapshot_probabilities(tbl, index_view="t", bucket="2")
    assert out["p_correction_10pct_75d"] == 0.22
    assert out["p_correction_10pct_75d"] != out.get("p_max_dd_le_neg5pct", 0.55)
    assert out["base_rates"]["p_correction_10pct_75d"] == 0.25


def test_snapshot_base_rates_are_horizon_specific():
    tbl = pd.DataFrame(
        [
            {
                "index_view": "t",
                "metric": "dist_count_25d",
                "bucket": "2",
                "horizon_d": 5,
                "n": 100,
                "p_ret_neg": 0.48,
                "base_rate_p_ret_neg": 0.50,
                "confidence": "HIGH",
            },
            {
                "index_view": "t",
                "metric": "dist_count_25d",
                "bucket": "2",
                "horizon_d": 25,
                "n": 100,
                "p_ret_neg": 0.35,
                "base_rate_p_ret_neg": 0.39,
                "p_max_dd_le_neg5pct": 0.34,
                "base_rate_p_max_dd_le_neg5pct": 0.40,
                "confidence": "HIGH",
            },
            {
                "index_view": "t",
                "metric": "dist_count_25d",
                "bucket": "2",
                "horizon_d": 75,
                "n": 100,
                "p_ret_neg": 0.29,
                "base_rate_p_ret_neg": 0.30,
                "p_max_dd_le_neg10pct": 0.44,
                "base_rate_p_max_dd_le_neg10pct": 0.55,
                "confidence": "HIGH",
            },
        ]
    )
    out = snapshot_probabilities(tbl, index_view="t", bucket="2")
    br = out["base_rates"]
    assert br["p_ret_neg_5d"] == 0.50
    assert br["p_ret_neg_25d"] == 0.39
    assert br["p_ret_neg_75d"] == 0.30
    assert br["p_correction_5pct_25d"] == 0.40
    assert br["p_correction_10pct_75d"] == 0.55
    assert "p_ret_neg" not in br


def test_align_closes_by_date_not_range_index():
    from src.market.distribution_risk_lens.pipeline import _align_closes_by_date, _return_spread

    raw = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]),
            "close": [100.0, 110.0, 120.0],
        }
    )
    ex = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-04"]),
            "close": [50.0, 55.0, 60.0],
        }
    )
    joined = _align_closes_by_date(raw, ex)
    assert list(joined.index.strftime("%Y-%m-%d")) == ["2020-01-02", "2020-01-03"]
    spread = _return_spread(joined, 1)
    assert spread is not None
    expected = (120.0 / 110.0 - 1.0) - (55.0 / 50.0 - 1.0)
    assert abs(spread - expected) < 1e-9
