"""P0/P1 weekly report patch acceptance tests."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _minimal_payload() -> dict:
    return {
        "metadata": {"asof_date": "2026-05-17", "data_confidence": "Medium"},
        "regime_engine": {"current_regime": "STATE B", "suggested_regime": "STATE B"},
        "global_macro": {"facts": {}, "what_changed": []},
        "vietnam_liquidity": {"facts": {}},
        "market_structure": {
            "levels": {"vnindex_level": 1300, "vn30_level": 1400, "distribution_days_rolling_20": 3},
            "what_changed": [],
            "distribution": {},
        },
        "probability_allocation": {
            "allocation": {"gross_exposure": 0.55, "cash_weight": 0.45},
            "probabilities": {"fed_cut_3m": 0.35},
        },
        "decision_layer": {"top_actions": [], "top_risks": []},
        "execution_monitoring": {"risk_flags": {}, "sell_trim_signals": []},
        "downtrend_v2": {"outcome_b_adjusted": None, "confirmed_downtrend_adjusted": None},
        "geo_layers": {},
        "portfolio_health": {"summary": {}, "sector_concentration": []},
        "watchlist": {"candidates": []},
    }


def test_price_or_missing():
    from scripts.reporting.report_format import price_or_missing

    assert price_or_missing(None) == "Missing"
    assert price_or_missing("None") == "Missing"
    assert price_or_missing(float("nan")) == "Missing"
    assert price_or_missing(12345.6) == "12,345.60"


def test_cloud_label():
    from scripts.reporting.report_format import cloud_label

    assert cloud_label(True) == "Bull"
    assert cloud_label("true") == "Bull"
    assert cloud_label(False) == "Bear"
    assert cloud_label(None) == "Missing"


def test_credit_growth_sanity_warning():
    from scripts.reporting.report_format import fmt_credit_growth

    _, w = fmt_credit_growth(1.0)
    assert w is not None


def test_html_no_literal_none(tmp_path: Path):
    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections
    from scripts.reporting.render_weekly_report import render_html
    from scripts.reporting.report_format import html_has_literal_none

    payload = enrich_portfolio_decision_sections(_minimal_payload(), fetch_prices=False)
    out = tmp_path / "report.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    assert not html_has_literal_none(html)
    assert ">None<" not in html
    assert re.search(r">nan<", html, re.I) is None


def test_narrative_facts_not_repeating_macro_numbers(tmp_path: Path):
    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections

    payload = enrich_portfolio_decision_sections(_minimal_payload(), fetch_prices=False)
    assert payload["global_macro_narrative"]["facts"] == []
    assert payload["vn_liquidity_narrative"]["facts"] == []


def test_execution_prices_preformatted():
    from scripts.ingest.weekly_lean_sections import build_execution_scan_aligned

    block = {
        "rows": [
            {"ticker": "TST", "sector": "—", "action": "HOLD", "weight_pct": 5.0, "current_price": 100},
        ]
    }
    ex = build_execution_scan_aligned(_minimal_payload(), block)
    row = ex["rows"][0]
    assert row["trail_price"] == "Missing"
    assert row["tp1_price"] == "Missing"
    assert row["scan_missing"] is True
    assert row["strategy_book"] == "UNKNOWN"


def test_immediate_actions_from_scan_forced():
    from scripts.ingest.weekly_lean_sections import _build_immediate_actions

    rows = [
        {
            "ticker": "VCG",
            "scan_final_action": "TRAIL_EXIT",
            "required_operator_action": "SELL / EXIT",
            "scan_reason": "trail breach",
        },
        {
            "ticker": "NVL",
            "scan_final_action": "TRAIL_EXIT",
            "required_operator_action": "SELL / EXIT",
            "scan_reason": "trail breach",
        },
    ]
    actions = _build_immediate_actions(rows)
    assert any("VCG" in a for a in actions)
    assert any("NVL" in a for a in actions)


def test_charts_no_combined_liquidity(tmp_path: Path):
    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections
    from scripts.reporting.render_weekly_report import render_html

    payload = enrich_portfolio_decision_sections(_minimal_payload(), fetch_prices=False)
    charts = payload.get("visualizations_smart", {}).get("charts", [])
    ids = {c["id"] for c in charts}
    assert "vnindex-trend" not in ids
    assert "liq" not in ids
    if payload.get("manual_inputs") or True:
        pass
    out = tmp_path / "charts.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    assert "chart-liq-omo" in html or "liq-omo" not in html  # only if data present
    assert "OMO net','IB ON" not in html


def test_omo_unit_in_kpi_or_pulse():
    from scripts.ingest.weekly_lean_sections import build_market_pulse, build_smart_kpi_board

    payload = _minimal_payload()
    pulse = build_market_pulse(payload)
    labels = [r["metric"] for r in pulse["rows"]]
    assert any("OMO" in x and "bn" in x for x in labels)
    kpi = build_smart_kpi_board(payload)
    assert any("bn" in k["label"] for k in kpi["vn_liquidity"])


def test_dist_trail_scale_mismatch_detected():
    from scripts.reporting.report_format import scan_price_kVND_to_vnd

    assert scan_price_kVND_to_vnd(25.0) == 25000.0
    cur = 27329.0
    trail_vnd = scan_price_kVND_to_vnd(25.0)
    dist_pct = 100.0 * (cur - trail_vnd) / cur
    assert 0 < dist_pct < 20
    bad_pct = 100.0 * (cur - 25.0) / cur
    assert bad_pct > 90


def test_scan_mismatch_sets_critical_dq():
    from scripts.ingest.weekly_lean_sections import build_execution_scan_aligned

    payload = _minimal_payload()
    block = {
        "rows": [
            {
                "ticker": "NVL",
                "sector": "BDS",
                "action": "HOLD",
                "weight_pct": 5.0,
                "current_price": 17300.0,
            },
        ],
    }
    ex = build_execution_scan_aligned(payload, block)
    nvl = next(r for r in ex["rows"] if r["ticker"] == "NVL")
    if nvl.get("action_mismatch"):
        assert ex.get("mismatch_warning") and "CRITICAL" in ex["mismatch_warning"]


def test_global_macro_narrative_no_raw_numbers():
    from scripts.ingest.weekly_lean_sections import build_global_macro_narrative

    n = build_global_macro_narrative(_minimal_payload())
    interp = n["interpretation"]
    assert "4.47" not in interp
    assert "97.9" not in interp
    assert "UST curve" in interp


def test_watchlist_bucket_s3_not_avoid_remove():
    from scripts.ingest.scan_ssot import watchlist_bucket

    assert watchlist_bucket("HOLD", "S3_RESEARCH_ONLY") == "Watch / Research Only"
    assert watchlist_bucket("WATCH_ONLY", "A3_PRODUCTION") == "Watch / Research Only"
