"""Lean weekly report structure, scan SSOT, and deduplication tests."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def test_scan_action_mapping_trail_exit():
    from scripts.ingest.scan_ssot import map_operator_action

    action, _ = map_operator_action("TRAIL_EXIT")
    assert "EXIT" in action.upper()


def test_watchlist_bucket_blocked_breadth():
    from scripts.ingest.scan_ssot import watchlist_bucket

    assert watchlist_bucket("NEW_T1_MANUAL_REVIEW_BREADTH", "A3_PRODUCTION") == "Blocked by Breadth"


def test_regime_b_band():
    from scripts.ingest.portfolio_decision_enrich import build_portfolio_command_center

    payload = {
        "regime_engine": {"current_regime": "STATE B"},
        "probability_allocation": {"allocation": {"gross_exposure": 0.55, "cash_weight": 0.45}},
        "execution_monitoring": {"sell_trim_signals": []},
        "metadata": {"data_confidence": "High"},
    }
    pcc = build_portfolio_command_center(payload)
    assert pcc["gross_exposure_target_band"] == "50–60%"


def test_metric_registry_vnindex_primary_section():
    from scripts.reporting.metric_registry import CORE_METRICS

    assert CORE_METRICS["VNINDEX"]["primary_section"] == "market_pulse"


def test_lean_render_section_order(tmp_path: Path):
    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections
    from scripts.reporting.render_weekly_report import render_html

    payload = {
        "metadata": {"asof_date": "2026-05-17", "data_confidence": "Medium"},
        "regime_engine": {"current_regime": "STATE B", "suggested_regime": "STATE B"},
        "global_macro": {"facts": {}, "what_changed": []},
        "vietnam_liquidity": {"facts": {}},
        "market_structure": {"levels": {}, "what_changed": [], "distribution": {}},
        "probability_allocation": {"allocation": {"gross_exposure": 0.55, "cash_weight": 0.45}, "probabilities": {}},
        "decision_layer": {"top_actions": [], "top_risks": []},
        "execution_monitoring": {"risk_flags": {}, "sell_trim_signals": []},
        "downtrend_v2": {"outcome_b_adjusted": None, "confirmed_downtrend_adjusted": None},
        "geo_layers": {},
        "portfolio_health": {"summary": {}, "sector_concentration": []},
        "watchlist": {"candidates": []},
    }
    payload = enrich_portfolio_decision_sections(payload, fetch_prices=False)
    out = tmp_path / "lean.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    assert html.index("portfolio-summary") < html.index("execution")
    assert html.index("execution") < html.index("watchlist")
    assert "Regime rules (full table)" in html
    assert "Smart KPI Board" in html
    assert "VNINDEX" in html
    # VNINDEX should appear in market pulse, not as duplicate KPI card label pattern
    assert html.count("id=\"kpis\"") == 0


def test_watchlist_a3_only_filter():
    from scripts.ingest.weekly_lean_sections import build_watchlist_a3

    board = build_watchlist_a3({})
    for c in board.get("candidates") or []:
        assert c.get("final_action")  # from scan rows only
