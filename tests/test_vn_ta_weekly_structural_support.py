from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.vn_ta_fireant_cli import (
    TAConfig,
    _classify_weekly_close_test,
    _weekly_ma_cluster_from_values,
    _weekly_structural_assessment,
    analyze_ticker,
)


def test_weekly_ma_cluster_classifies_vcb_style_tight_confluence() -> None:
    result = _weekly_ma_cluster_from_values(
        {"ma20": 61.25, "ma50": 61.35, "ma100": 60.60}
    )

    assert result["available"] is True
    assert result["count"] == 3
    assert result["width_pct"] < 2.0
    assert result["classification"] == "very_tight"
    assert result["representative_level"] == result["mean"]


def test_declining_cluster_is_not_automatically_bullish() -> None:
    result = _weekly_ma_cluster_from_values(
        {"ma20": 48.0, "ma50": 48.4, "ma100": 48.8},
        slopes={"ma20": "down", "ma50": "down", "ma100": "down"},
    )

    assert result["classification"] == "very_tight"
    assert result["trend_quality"] == "declining_cluster_caution"
    assert result["flat_or_rising"] is False


def test_widely_separated_weekly_mas_do_not_receive_overlap_points() -> None:
    weekly = _ohlcv_frame(220, "W-FRI", "2022-01-07", 20.0, 100.0)

    result = _weekly_structural_assessment(weekly)

    assert result["ma_cluster"]["classification"] == "weak"
    assert result["score_breakdown"]["ma_confluence"] <= 4


def test_weekly_close_inside_zone_survives_intrawweek_undercut() -> None:
    result = _classify_weekly_close_test(
        low=59.8,
        close=61.9,
        volume_ratio=0.8,
        zone_low=60.5,
        zone_high=62.0,
    )

    assert result["state"] == "support_test_held"
    assert result["wick_below_zone"] is True
    assert result["decisive_failure"] is False


def test_weekly_close_below_zone_on_expanding_volume_and_no_reclaim_fails() -> None:
    result = _classify_weekly_close_test(
        low=59.4,
        close=59.5,
        volume_ratio=1.6,
        zone_low=60.5,
        zone_high=62.0,
        next_close=59.8,
    )

    assert result["state"] == "support_failure"
    assert result["decisive_failure"] is True


def test_weekly_assessment_preserves_unknowns_with_insufficient_history() -> None:
    weekly = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-02", periods=8, freq="W-FRI"),
            "open": [50.0] * 8,
            "high": [51.0] * 8,
            "low": [49.0] * 8,
            "close": [50.0] * 8,
            "volume": [1_000_000.0] * 8,
        }
    )

    result = _weekly_structural_assessment(weekly)

    assert result["status"] == "not_available"
    assert result["structural_support_score"] is None
    assert result["role_reversal"]["state"] == "not_confirmed"
    assert result["wyckoff_phase"] == "not_confirmed"


def _ohlcv_frame(periods: int, freq: str, start: str, low: float, high: float) -> pd.DataFrame:
    close = np.linspace(low, high, periods) + np.sin(np.arange(periods) / 5.0)
    open_ = close - 0.2
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=periods, freq=freq),
            "open": open_,
            "high": np.maximum(open_, close) + 0.8,
            "low": np.minimum(open_, close) - 0.8,
            "close": close,
            "volume": 1_000_000.0 + (np.arange(periods) % 10) * 25_000.0,
        }
    )


def test_analyze_ticker_exposes_additive_weekly_structure(monkeypatch) -> None:
    frames = {
        "D": _ohlcv_frame(320, "B", "2025-01-02", 45.0, 66.0),
        "W": _ohlcv_frame(220, "W-FRI", "2022-01-07", 40.0, 65.0),
        "M": _ohlcv_frame(120, "ME", "2016-01-31", 25.0, 64.0),
    }

    def fake_fetch(symbol: str, start: str, end: str, resolution: str = "D") -> pd.DataFrame:
        assert symbol == "VCB"
        return frames[resolution].copy()

    monkeypatch.setattr("scripts.vn_ta_fireant_cli.fetch_ohlcv", fake_fetch)

    result = analyze_ticker("VCB", date(2026, 8, 26), TAConfig())

    assert result["weekly_structure"]["ma_cluster"]["available"] is True
    assert result["weekly_structure"]["structural_support_score"] is not None
    assert sum(result["weekly_structure"]["score_breakdown"].values()) == result[
        "weekly_structure"
    ]["structural_support_score"]
    assert result["indicators"]["rsi"]["W"]["value"] is not None
    assert any(
        zone["timeframe_origin"] == "W" for zone in result["levels"]["support_zones"]
    )
    assert "trade_plan_1_3m" in result


def test_skill_contract_documents_measured_weekly_schema() -> None:
    repo = Path(__file__).resolve().parents[1]
    skill = (
        repo / ".agents" / "skills" / "source-command-vn-ta" / "SKILL.md"
    ).read_text(encoding="utf-8")
    weekly_reference = (
        repo
        / ".agents"
        / "skills"
        / "source-command-vn-ta"
        / "reference-weekly-structural-support.md"
    ).read_text(encoding="utf-8")

    for required_schema_key in (
        '"available": true',
        '"weekly_close_test": {',
        '"prior_base_origin_markup": 0',
        '"momentum_invalidation": 0',
        '"score_classification": "Strong weekly support"',
    ):
        assert required_schema_key in skill

    for doctrine in (
        "MA_cluster_width",
        "ROLE_REVERSAL_SUPPORT",
        "Weekly close > intraweek wick",
        "A. MA Confluence — 20",
        "Reference example — VCB",
    ):
        assert doctrine in weekly_reference
