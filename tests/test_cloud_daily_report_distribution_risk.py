"""Cloud Daily Report integration for Distribution Risk Lens (read-only)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.trading.reports.cloud_daily_report import build_report
from src.trading.reports.distribution_risk_card import (
    LATEST_JSON,
    STALE_NEEDS_REVIEW_MSG,
    build_distribution_risk_standalone_html,
    build_distribution_risk_standalone_md,
    load_distribution_risk_latest,
    render_distribution_risk_html,
)

REPO = Path(__file__).resolve().parents[1]


def _minimal_inputs() -> dict:
    return {
        "scan_df": pd.DataFrame(),
        "intraday_df": pd.DataFrame(),
        "holdings": [],
        "nav_vnd": None,
        "warnings": [],
        "files_used": [],
    }


def test_cloud_report_does_not_crash_if_json_missing(monkeypatch, tmp_path):
    missing = tmp_path / "no_drl.json"
    monkeypatch.setattr(
        "src.trading.reports.distribution_risk_card.LATEST_JSON",
        missing,
    )
    data, warns = load_distribution_risk_latest(missing)
    assert data is None
    assert warns
    html, md, payload = build_report("eod", _minimal_inputs(), datetime.now(tz=timezone.utc))
    assert "VNINDEX Distribution Risk Lens" not in html or "missing" in " ".join(warns).lower()
    assert "final_action" not in payload


def test_cloud_report_shows_card_when_json_exists(monkeypatch, tmp_path):
    sample = {
        "as_of_date": "2026-05-17",
        "primary_view": "ex_vin_proxy",
        "vnindex_raw": {"warning_state": "NORMAL", "dist_count_10d": 0, "dist_count_25d": 0, "dist_count_50d": 0},
        "ex_vin_proxy": {
            "warning_state": "CAUTION",
            "dist_count_10d": 1,
            "dist_count_25d": 2,
            "dist_count_50d": 3,
            "probabilities": {"p_ret_neg_25d": 0.55, "confidence": "MEDIUM", "sample_size": 80},
        },
        "vin_group": {"distortion_flag": False},
        "comparison": {"raw_vs_ex_vin_warning_disagreement": False},
        "safety_note": "Distribution Risk Lens is market context only and does not change final_action.",
    }
    p = tmp_path / "distribution_risk_latest.json"
    p.write_text(json.dumps(sample), encoding="utf-8")
    monkeypatch.setattr("src.trading.reports.distribution_risk_card.LATEST_JSON", p)
    html = render_distribution_risk_html(sample)
    assert "VNINDEX Distribution Risk Lens" in html
    assert "CAUTION" in html
    html2, _, payload = build_report("eod", _minimal_inputs(), datetime.now(tz=timezone.utc))
    assert "VNINDEX Distribution Risk Lens" in html2
    assert payload.get("final_action") is None


def test_distribution_lens_does_not_modify_final_action_in_scan():
    """Scan final_action must remain whatever scan supplies; lens is separate."""
    scan = pd.DataFrame([{"symbol": "AAA", "final_action": "WATCH_ONLY"}])
    inputs = _minimal_inputs()
    inputs["scan_df"] = scan
    _, _, payload = build_report("eod", inputs, datetime.now(tz=timezone.utc))
    assert "final_action" not in payload


@pytest.mark.skipif(not LATEST_JSON.is_file(), reason="pipeline not run")
def test_repo_latest_json_loads():
    data, warns = load_distribution_risk_latest()
    assert data is not None
    assert "safety_note" in data


def test_card_uses_25d_base_for_25d_return_probability():
    from src.trading.reports.distribution_risk_card import _fmt_with_base

    probs = {
        "p_ret_neg_25d": 0.35,
        "base_rates": {
            "p_ret_neg_5d": 0.50,
            "p_ret_neg_25d": 0.39,
        },
    }
    s = _fmt_with_base(probs, "p_ret_neg_25d")
    assert "35.0%" in s
    assert "39.0%" in s
    assert "50.0%" not in s


def test_card_shows_10pct_75d_correction_with_correct_base():
    from src.trading.reports.distribution_risk_card import render_distribution_risk_html

    data = {
        "primary_view": "ex_vin_proxy",
        "vnindex_raw": {},
        "ex_vin_proxy": {
            "warning_state": "CAUTION",
            "probabilities": {
                "p_correction_10pct_75d": 0.22,
                "base_rates": {
                    "p_correction_10pct_75d": 0.55,
                    "p_correction_5pct_25d": 0.40,
                },
                "confidence": "HIGH",
                "sample_size": 100,
            },
        },
        "vin_group": {},
        "comparison": {},
    }
    html = render_distribution_risk_html(data)
    assert "P(-10% correction within 75D)" in html
    assert "22.0%" in html
    assert "55.0%" in html
    assert "40.0%" not in html.split("P(-10%")[1].split("</td>")[0]


def test_daily_scan_report_includes_distribution_risk_section(monkeypatch, tmp_path):
    import pandas as pd

    from scripts.reporting.daily_scan_report import write_daily_scan_report

    sample = {
        "as_of_date": "2026-05-18",
        "requested_as_of_date": "2026-05-18",
        "report_status": "OK",
        "primary_view": "ex_vin_proxy",
        "method_version": "test",
        "view_freshness": [
            {"index_view": "vnindex_raw", "last_data_date": "2026-05-18", "requested_as_of_date": "2026-05-18", "is_stale_for_as_of": False},
            {"index_view": "ex_vin_proxy", "last_data_date": "2026-05-18", "requested_as_of_date": "2026-05-18", "is_stale_for_as_of": False},
        ],
        "vnindex_raw": {"warning_state": "CAUTION", "dist_count_10d": 1, "dist_count_25d": 2, "dist_count_50d": 3, "is_stale_for_as_of": False},
        "ex_vin_proxy": {
            "warning_state": "CAUTION",
            "dist_count_10d": 1,
            "dist_count_25d": 2,
            "dist_count_50d": 3,
            "is_proxy": True,
            "note": "NOT true ex-VIN index",
            "probabilities": {},
            "is_stale_for_as_of": False,
        },
        "vin_group": {"distortion_flag": False, "warning_state": "NORMAL"},
        "comparison": {},
        "safety_note": "Distribution Risk Lens is market context only and does not change final_action.",
    }
    monkeypatch.setattr(
        "src.trading.reports.distribution_risk_card.refresh_distribution_risk_for_reports",
        lambda **kw: [],
    )
    monkeypatch.setattr(
        "src.trading.reports.distribution_risk_card.load_distribution_risk_latest",
        lambda path=None: (sample, []),
    )
    scan = pd.DataFrame(
        [
            {
                "as_of_date": "2026-05-18",
                "symbol": "AAA",
                "final_action": "WATCH_ONLY",
                "a3_rank_score": 0.5,
                "pct_cloud_bull_a3": 0.32,
                "pct_cloud_bull_s3": 0.31,
                "breadth_zone": "defense",
                "regime_bull": True,
                "breadth_t1_permission": True,
                "breadth_t2_permission": False,
            }
        ]
    )
    out_md = tmp_path / "daily_scan.md"
    out_json = tmp_path / "daily_scan.json"
    monkeypatch.setattr("scripts.reporting.daily_scan_report.OUT_MD", out_md)
    monkeypatch.setattr("scripts.reporting.daily_scan_report.OUT_JSON", out_json)
    write_daily_scan_report(scan)
    text = out_md.read_text(encoding="utf-8")
    assert "VNINDEX Distribution Risk Lens" in text
    assert "does not change final_action" in text
    assert "Index view freshness" in text or "freshness" in text.lower()


def test_card_includes_safety_note_and_ex_vin_proxy_disclosure():
    data = {
        "primary_view": "ex_vin_proxy",
        "vnindex_raw": {},
        "ex_vin_proxy": {"warning_state": "NORMAL", "is_proxy": True, "note": "derived basket"},
        "vin_group": {},
        "comparison": {},
    }
    html = render_distribution_risk_html(data)
    assert "does not change final_action" in html
    assert "NOT a native exchange index" in html


def test_stale_view_produces_needs_review_warning_in_html_and_md():
    data = {
        "report_status": "NEEDS_REVIEW",
        "primary_view": "ex_vin_proxy",
        "view_freshness": [
            {
                "index_view": "ex_vin_proxy",
                "last_data_date": "2026-05-10",
                "requested_as_of_date": "2026-05-18",
                "is_stale_for_as_of": True,
            }
        ],
        "vnindex_raw": {},
        "ex_vin_proxy": {"warning_state": "CAUTION"},
        "vin_group": {},
        "comparison": {},
    }
    html = build_distribution_risk_standalone_html(data)
    md = build_distribution_risk_standalone_md(data)
    assert STALE_NEEDS_REVIEW_MSG in html
    assert STALE_NEEDS_REVIEW_MSG in md


def test_cloud_report_section_g_stale_sets_needs_review_warning():
    sample = {
        "report_status": "NEEDS_REVIEW",
        "primary_view": "ex_vin_proxy",
        "view_freshness": [
            {
                "index_view": "vnindex_raw",
                "last_data_date": "2026-05-01",
                "requested_as_of_date": "2026-05-18",
                "is_stale_for_as_of": True,
            }
        ],
        "vnindex_raw": {"warning_state": "NORMAL", "dist_count_10d": 0, "dist_count_25d": 0, "dist_count_50d": 0},
        "ex_vin_proxy": {"warning_state": "CAUTION", "dist_count_10d": 0, "dist_count_25d": 0, "dist_count_50d": 0},
        "vin_group": {"distortion_flag": False},
        "comparison": {},
    }
    inputs = _minimal_inputs()
    inputs["distribution_risk_lens"] = sample
    html, _, payload = build_report("eod", inputs, datetime.now(tz=timezone.utc))
    assert STALE_NEEDS_REVIEW_MSG in html
    assert payload.get("report_status") == "NEEDS_REVIEW"
    assert "final_action" not in payload
