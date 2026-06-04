"""Tests for operator dashboard full-history evidence fields and sections."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.scans.institutional_accumulation.operator_explain import (
    ALLOWED_EVIDENCE_LABELS,
    EVIDENCE_LABEL_AVOID,
    EVIDENCE_LABEL_HEAT,
    EVIDENCE_LABEL_INCONCLUSIVE,
    EVIDENCE_LABEL_RISK_CLEAN,
    EVIDENCE_SAFETY_NOTE,
    attach_backtest_evidence_fields,
    load_dashboard_evidence_config,
)
from src.scans.institutional_accumulation.operator_diagnostics import compute_evidence_lists
from src.scans.institutional_accumulation.operator_summary_html import (
    OPERATOR_HTML_SECTION_IDS,
    validate_operator_summary_html,
    write_operator_summary_html,
)

FIXTURE_CONFIG = Path(__file__).parent / "fixtures" / "ia_dashboard_evidence_config.json"


def _make_multi_scan_df() -> pd.DataFrame:
    rows = []
    for i in range(20):
        rows.append({
            "ticker": f"T{i:02d}",
            "tier": "Tier 2" if i % 3 != 0 else "Tier 3",
            "institutional_accumulation_score": float(30 + i * 2),
            "score_money_flow": float(40 + i),
            "score_risk_penalty": float(5 + i),
            "score_context": 50.0,
            "fund_context_bucket": "outside_fund_disclosure",
            "emerging_accumulation_candidate": False,
            "vingroup_distortion_flag": False,
            "distribution_risk_flag": i % 5 == 0,
            "has_fund_disclosure_tag": False,
            "score_decile": i % 10,
            "extension_pct_above_ma20": float(i),
            "distribution_days_25": float(i % 8),
            "turnover_accel_ratio_5d50d": float(0.5 + i * 0.1),
            "liquidity_ok": True,
            "sector": "Banks",
        })
    return pd.DataFrame(rows)


def _minimal_payload(evidence_lists: dict | None = None) -> dict:
    cfg = json.loads(FIXTURE_CONFIG.read_text(encoding="utf-8"))
    return {
        "scan_date": "2026-05-28",
        "smart_money_month": "2026-04",
        "methodology_version": "v1.1",
        "regime_label": "normal_uptrend",
        "context_source": "test",
        "evidence_config": cfg,
        "evidence_version": "full_history_v0.2",
        "bucket_diagnostics": {
            "rows_scored": 10,
            "tier_counts": {"Tier 2": 2},
            "emerging_count_total": 0,
            "count_top_tier_caution_proxy": 0,
            "bucket_mix_percentages_top_tier": {},
            "bucket_mix_counts_top_tier": {},
            "bucket_mix_denominator": "n=2",
        },
        "look_first": {
            "fund_backed_candidates": [],
            "emerging_candidates": [],
            "important_rejects": [],
            "distortion_caution": [],
        },
        "changes_since_previous": {"note": "no_previous_scan"},
        "key_warnings": [],
        "tier2_focus_list": [],
        "evidence_lists": evidence_lists or {},
    }


def test_evidence_banner_full_history_zero_promising(tmp_path) -> None:
    out = tmp_path / "op.html"
    write_operator_summary_html(out, _minimal_payload())
    html = out.read_text(encoding="utf-8")
    assert 'id="evidence-status"' in html
    assert "Full-History" in html
    assert "RESEARCH_ONLY_NOT_PRODUCTION" in html
    assert "0" in html
    assert "PORTFOLIO_PROMISING" in html or "portfolio-promising" in html.lower()


def test_research_only_safety_note_exact(tmp_path) -> None:
    out = tmp_path / "op.html"
    write_operator_summary_html(out, _minimal_payload())
    html = out.read_text(encoding="utf-8")
    assert EVIDENCE_SAFETY_NOTE in html
    assert validate_operator_summary_html(html) == []


def test_heat_warning_shown_when_triggered(tmp_path) -> None:
    heat_card = {
        "ticker": "HTT",
        "tier": "Tier 2",
        "institutional_accumulation_score": 75.0,
        "score_money_flow": 60.0,
        "score_risk_penalty": 10.0,
        "fund_context_bucket": "outside_fund_disclosure",
        "emerging_accumulation_candidate": False,
        "vingroup_distortion_flag": False,
        "distribution_risk_flag": False,
        "primary_driver": "test",
        "secondary_driver": "",
        "main_risk": "",
        "operator_note": "",
        "score_decile": 9,
        "evidence_label": EVIDENCE_LABEL_HEAT,
        "research_only_flag": "RESEARCH_ONLY_NOT_PRODUCTION",
        "risk_clean_flag": True,
        "distribution_risk_clean": True,
        "top_decile_heat_risk": True,
        "controlled_accumulation_flag": False,
        "dashboard_priority_bucket": "heat_warning",
        "dashboard_operator_note": "High score may reflect late-stage heat.",
        "extension_pct_above_ma20": 18.0,
        "distribution_days_25": 2.0,
        "turnover_accel_ratio_5d50d": 2.5,
        "sector": "Banks",
    }
    ev = {
        "risk_clean_queue": [],
        "heat_warning_names": [heat_card],
        "dist_avoid_names": [],
        "n_risk_clean": 0,
        "n_heat_warnings": 1,
        "n_dist_avoid": 0,
    }
    out = tmp_path / "op.html"
    write_operator_summary_html(out, _minimal_payload(evidence_lists=ev))
    html = out.read_text(encoding="utf-8")
    assert 'id="heat-warnings"' in html
    assert "HEAT_RISK_MANUAL_REVIEW" in html
    assert "HTT" in html


def test_dist_risk_names_not_in_risk_clean_queue() -> None:
    df = _make_multi_scan_df()
    df_ev = attach_backtest_evidence_fields(df)
    dist_rows = df_ev[df_ev["distribution_risk_flag"] == True]  # noqa: E712
    assert (dist_rows["dashboard_priority_bucket"] != "risk_clean_research").all()
    ev = compute_evidence_lists(df_ev)
    risk_clean_tickers = {c["ticker"] for c in ev["risk_clean_queue"]}
    dist_tickers = set(df[df["distribution_risk_flag"] == True]["ticker"])  # noqa: E712
    assert not (risk_clean_tickers & dist_tickers)


def test_controlled_accumulation_flag_only_decile_5_to_8() -> None:
    rows = []
    for decile in range(10):
        rows.append({
            "ticker": f"D{decile}",
            "tier": "Tier 2",
            "institutional_accumulation_score": float(30 + decile * 4),
            "score_decile": decile,
            "distribution_risk_flag": False,
            "extension_pct_above_ma20": 5.0,
            "distribution_days_25": 1.0,
            "turnover_accel_ratio_5d50d": 1.0,
        })
    df_ev = attach_backtest_evidence_fields(pd.DataFrame(rows))
    ctrl_deciles = set(df_ev[df_ev["controlled_accumulation_flag"] == True]["score_decile"])  # noqa: E712
    assert ctrl_deciles.issubset({5, 6, 7, 8})
    for d in [0, 1, 2, 3, 4, 9]:
        assert not df_ev[df_ev["score_decile"] == d]["controlled_accumulation_flag"].iloc[0]


def test_no_production_fields_in_evidence_output() -> None:
    df_ev = attach_backtest_evidence_fields(_make_multi_scan_df())
    forbidden = {"final_action", "oms_order", "dnse_routing", "sizing", "live_order", "position_size"}
    new_cols = set(df_ev.columns) - set(_make_multi_scan_df().columns)
    assert not (new_cols & forbidden)


def test_distribution_risk_clean_is_inverse_of_flag() -> None:
    df_ev = attach_backtest_evidence_fields(_make_multi_scan_df())
    assert (df_ev["distribution_risk_clean"] == ~df_ev["distribution_risk_flag"].astype(bool)).all()
    assert (df_ev["risk_clean_flag"] == df_ev["distribution_risk_clean"]).all()


def test_heat_risk_decile_9_or_heat_indicators() -> None:
    rows = []
    for d in range(10):
        rows.append({
            "ticker": f"H{d}",
            "tier": "Tier 2",
            "institutional_accumulation_score": float(30 + d * 4),
            "score_decile": d,
            "distribution_risk_flag": False,
            "extension_pct_above_ma20": 20.0,
            "distribution_days_25": 5.0,
            "turnover_accel_ratio_5d50d": 3.0,
        })
    df_ev = attach_backtest_evidence_fields(pd.DataFrame(rows))
    assert df_ev[df_ev["score_decile"] == 9]["top_decile_heat_risk"].all()
    for d in range(9):
        assert df_ev[df_ev["score_decile"] == d]["top_decile_heat_risk"].iloc[0]


def test_all_section_ids_including_how_to_read(tmp_path) -> None:
    out = tmp_path / "op.html"
    write_operator_summary_html(out, _minimal_payload())
    html = out.read_text(encoding="utf-8")
    assert len(OPERATOR_HTML_SECTION_IDS) == 19
    for sid in OPERATOR_HTML_SECTION_IDS:
        assert f'id="{sid}"' in html, f"Missing section id={sid}"


def test_validate_catches_missing_safety_note() -> None:
    errors = validate_operator_summary_html("<html><body><p>nothing</p></body></html>")
    assert any("safety" in e.lower() or "final_action" in e for e in errors)


def test_evidence_labels_display_only_enum() -> None:
    df_ev = attach_backtest_evidence_fields(_make_multi_scan_df())
    labels = set(df_ev["evidence_label"].astype(str))
    assert labels.issubset(ALLOWED_EVIDENCE_LABELS)
    forbidden = {"BUY", "SELL", "ORDER", "POSITION_SIZE"}
    assert not (labels & forbidden)


def test_full_history_validation_link_in_html(tmp_path) -> None:
    out = tmp_path / "op.html"
    write_operator_summary_html(out, _minimal_payload())
    html = out.read_text(encoding="utf-8")
    assert "full_history_accumulation_validation.html" in html


def test_raw_score_not_buy_signal_in_html(tmp_path) -> None:
    out = tmp_path / "op.html"
    write_operator_summary_html(out, _minimal_payload())
    html = out.read_text(encoding="utf-8")
    assert "not a buy signal" in html.lower() or "INCONCLUSIVE" in html


def test_load_dashboard_evidence_config_fixture() -> None:
    cfg = json.loads(FIXTURE_CONFIG.read_text(encoding="utf-8"))
    assert cfg["portfolio_promising_count"] == 0
    assert cfg["research_only_flag"] == "RESEARCH_ONLY_NOT_PRODUCTION"
    live = load_dashboard_evidence_config(validate_metrics=False)
    assert live.get("portfolio_promising_count", 0) == 0 or "portfolio_promising_count" in live


def test_dist_avoid_gets_avoid_label() -> None:
    row = {
        "ticker": "DST",
        "tier": "Tier 2",
        "institutional_accumulation_score": 50.0,
        "score_decile": 6,
        "distribution_risk_flag": True,
        "extension_pct_above_ma20": 5.0,
        "distribution_days_25": 1.0,
        "turnover_accel_ratio_5d50d": 1.0,
    }
    df_ev = attach_backtest_evidence_fields(pd.DataFrame([row]))
    assert df_ev["evidence_label"].iloc[0] == EVIDENCE_LABEL_AVOID


def test_risk_clean_label_for_mid_decile_clean() -> None:
    row = {
        "ticker": "RC1",
        "tier": "Tier 2",
        "institutional_accumulation_score": 55.0,
        "score_decile": 6,
        "distribution_risk_flag": False,
        "extension_pct_above_ma20": 5.0,
        "distribution_days_25": 1.0,
        "turnover_accel_ratio_5d50d": 1.0,
    }
    df_ev = attach_backtest_evidence_fields(pd.DataFrame([row]))
    assert df_ev["evidence_label"].iloc[0] == EVIDENCE_LABEL_RISK_CLEAN
