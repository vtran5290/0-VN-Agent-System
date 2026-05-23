"""Operator output layer tests (no methodology / scoring changes)."""
from __future__ import annotations

import pandas as pd

from src.scans.institutional_accumulation.operator_changes import format_operator_changes
from src.scans.institutional_accumulation.operator_diagnostics import compute_bucket_diagnostics
from src.scans.institutional_accumulation.operator_explain import explain_row


def _sample_row(**kwargs) -> pd.Series:
    base = {
        "ticker": "TST",
        "tier": "Tier 3",
        "institutional_accumulation_score": 45.0,
        "score_money_flow": 40.0,
        "score_context": 55.0,
        "score_risk_penalty": 10.0,
        "fund_context_bucket": "consensus_core",
        "emerging_accumulation_candidate": False,
        "vingroup_distortion_flag": False,
        "distribution_risk_flag": False,
        "has_fund_disclosure_tag": True,
        "in_consensus_core": True,
        "cmf20_daily": None,
        "cmf20_weekly": 0.02,
        "liquidity_ok": True,
    }
    base.update(kwargs)
    return pd.Series(base)


def test_format_operator_changes_suppresses_zero_delta():
    diff = {
        "previous_scan": "outputs/scans/institutional_accumulation_2026-04-30.csv",
        "new_tier12": [],
        "dropped_tier12": [],
        "tier_changes": [],
        "biggest_score_gains": [{"ticker": "APS", "score_delta": 0.0, "tier_cur": "Tier 3"}],
        "biggest_score_losses": [{"ticker": "APS", "score_delta": 0.0, "tier_cur": "Tier 3"}],
    }
    out = format_operator_changes(diff)
    assert out["has_meaningful_changes"] is False
    assert "No meaningful" in (out.get("summary_line") or "")


def test_bucket_mix_caution_proxy_vs_vin_flag():
    df = pd.DataFrame(
        [
            {
                "ticker": "VIC",
                "tier": "Tier 3",
                "institutional_accumulation_score": 40.0,
                "score_money_flow": 50,
                "score_context": 40,
                "score_risk_penalty": 50,
                "fund_context_bucket": "outside_fund_disclosure",
                "emerging_accumulation_candidate": False,
                "vingroup_distortion_flag": False,
                "distribution_risk_flag": False,
                "has_fund_disclosure_tag": False,
                "sector": "Unknown",
            },
            {
                "ticker": "AAA",
                "tier": "Tier 2",
                "institutional_accumulation_score": 60.0,
                "score_money_flow": 70,
                "score_context": 30,
                "score_risk_penalty": 10,
                "fund_context_bucket": "outside_fund_disclosure",
                "emerging_accumulation_candidate": True,
                "vingroup_distortion_flag": False,
                "distribution_risk_flag": False,
                "has_fund_disclosure_tag": False,
                "sector": "Banks",
            },
        ]
    )
    diag = compute_bucket_diagnostics(df)
    assert diag["count_top_tier_vin_distortion_flag"] == 0
    assert diag["count_top_tier_caution_proxy"] >= 1
    assert diag["bucket_mix_percentages_top_tier"]["vin_distortion_flagged"] == 0.0
    assert diag["bucket_mix_percentages_top_tier"]["caution_proxy"] > 0


def test_write_operator_summary_html(tmp_path):
    from src.scans.institutional_accumulation.operator_summary_html import (
        OPERATOR_HTML_SECTION_IDS,
        validate_operator_summary_html,
        write_operator_summary_html,
    )

    payload = {
        "scan_date": "2026-05-21",
        "smart_money_month": "2026-04",
        "methodology_version": "v1.1",
        "regime_label": "fragile_uptrend_narrow_leadership",
        "context_source": "test",
        "bucket_diagnostics": {"rows_scored": 10, "tier_counts": {"Tier 2": 1}, "emerging_count_total": 0},
        "look_first": {"fund_backed_candidates": [], "emerging_candidates": [], "important_rejects": [], "distortion_caution": []},
        "changes_since_previous": {"note": "no_previous_scan"},
        "key_warnings": [],
        "tier2_focus_list": [],
    }
    out = tmp_path / "summary.html"
    write_operator_summary_html(out, payload)
    text = out.read_text(encoding="utf-8")
    assert "2026-05-21" in text
    assert "Institutional Accumulation" in text
    assert "sidebar" in text
    assert validate_operator_summary_html(text) == []
    for sid in OPERATOR_HTML_SECTION_IDS:
        assert f'id="{sid}"' in text
    assert "IntersectionObserver" in text
    assert 'class="kpi-grid"' in text


def test_write_all_operator_outputs_includes_html_keys(tmp_path):
    from pathlib import Path

    import pandas as pd

    from src.scans.institutional_accumulation.operator_summary import write_all_operator_outputs

    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "tier": "Tier 2",
                "institutional_accumulation_score": 60.0,
                "score_money_flow": 70,
                "score_context": 30,
                "score_risk_penalty": 10,
                "fund_context_bucket": "outside_fund_disclosure",
                "emerging_accumulation_candidate": True,
                "vingroup_distortion_flag": False,
                "distribution_risk_flag": False,
                "has_fund_disclosure_tag": False,
                "sector": "Banks",
                "primary_driver": "test",
                "secondary_driver": "",
                "main_risk": "",
                "operator_note": "",
                "reject_failure_reason": "",
            }
        ]
    )
    ctx = {
        "context_source": "test",
        "month": "2026-04",
        "regime_label": "fragile_uptrend_narrow_leadership",
    }
    paths = write_all_operator_outputs(
        output_dir=tmp_path,
        scan_date="2026-05-21",
        df=df,
        ctx=ctx,
        diff_payload={"note": "no_previous_scan"},
        scan_json={"scan_date": "2026-05-21"},
        preserve_weekly_brief_md=False,
    )
    assert "operator_summary_html" in paths
    assert "operator_summary_md" in paths
    assert "operator_summary_json" in paths
    assert "operator_summary_html_latest" in paths
    assert Path(paths["operator_summary_html"]).is_file()
    assert Path(paths["operator_summary_html_latest"]).is_file()
    html = Path(paths["operator_summary_html"]).read_text(encoding="utf-8")
    assert "IntersectionObserver" in html


def test_weekly_brief_html_sync_from_md(tmp_path):
    from src.scans.institutional_accumulation.weekly_brief import sync_weekly_brief_html

    md = tmp_path / "institutional_accumulation_weekly_brief_2026-05-21.md"
    md.write_text(
        "# Institutional Accumulation Weekly Brief\n\n## Market internals\n\n- Tier 1: **0**\n",
        encoding="utf-8",
    )
    paths = sync_weekly_brief_html(tmp_path, "2026-05-21", regenerate_md=False)
    html = (tmp_path / "institutional_accumulation_weekly_brief_2026-05-21.html").read_text(
        encoding="utf-8"
    )
    assert paths["weekly_brief_html"].endswith(".html")
    assert "<h1>" in html
    assert "Tier 1" in html


def test_explain_avoids_generic_review_drivers():
    ex = explain_row(_sample_row())
    assert "review drivers above" not in ex["operator_note"].lower()
    assert "review drivers above" not in ex["primary_driver"].lower()
    assert "Consensus" in ex["primary_driver"] or "context" in ex["primary_driver"].lower()
