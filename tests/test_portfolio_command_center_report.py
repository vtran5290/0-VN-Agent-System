"""Tests for portfolio command-center weekly report enrichments and HTML render."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _minimal_payload(regime: str = "STATE B", gross: float = 0.55, cash: float = 0.45) -> dict:
    return {
        "metadata": {"asof_date": "2026-05-17", "data_confidence": "Medium"},
        "regime_engine": {"current_regime": regime, "suggested_regime": regime},
        "global_macro": {"facts": {}, "what_changed": []},
        "vietnam_liquidity": {"facts": {}},
        "market_structure": {
            "levels": {"vnindex_level": 1300, "vn30_level": 1400, "distribution_days_rolling_20": 3},
            "what_changed": [],
            "distribution": {},
        },
        "probability_allocation": {
            "allocation": {"gross_exposure": gross, "cash_weight": cash},
            "probabilities": {},
        },
        "decision_layer": {"top_actions": ["Hold gross"], "top_risks": ["Dist days"]},
        "execution_monitoring": {
            "risk_flags": {"distribution_days": {}},
            "sell_trim_signals": [
                {"ticker": "MWG", "action": "SELL/EXIT", "reason": "Day-2 confirmation breach"},
                {"ticker": "VCB", "action": "HOLD", "reason": "OK"},
            ],
        },
        "downtrend_v2": {"outcome_b_adjusted": None, "confirmed_downtrend_adjusted": None},
        "geo_layers": {"geo_hormuz_energy_shock": {}},
        "portfolio_health": {"summary": {}, "sector_concentration": []},
        "watchlist": {"candidates": []},
    }


def test_regime_b_gross_band():
    from scripts.ingest.portfolio_decision_enrich import build_portfolio_command_center

    pcc = build_portfolio_command_center(_minimal_payload())
    assert pcc["gross_exposure_target_band"] == "50–60%"
    assert pcc["new_buy_mode"] == "Restricted"


def test_forced_exit_in_priority_action():
    from scripts.ingest.portfolio_decision_enrich import build_portfolio_command_center

    pcc = build_portfolio_command_center(_minimal_payload())
    assert pcc["has_forced_exit"] is True
    assert "MWG" in pcc["highest_priority_action"]
    assert "SELL" in pcc["highest_priority_action"].upper()


def test_regime_rules_highlight_current():
    from scripts.ingest.portfolio_decision_enrich import build_regime_rules

    rules = build_regime_rules("STATE B")
    current_rows = [r for r in rules["rows"] if r.get("is_current")]
    assert len(current_rows) == 1
    assert current_rows[0]["regime"] == "B"


def test_sector_unmapped_warning():
    from scripts.ingest.portfolio_decision_enrich import build_sector_exposure

    positions_block = {
        "rows": [
            {"ticker": "AAA", "sector": "—", "sector_mapped": False, "weight_pct": 10},
            {"ticker": "BBB", "sector": "Banks", "sector_mapped": True, "weight_pct": 20},
        ]
    }
    sec = build_sector_exposure({}, positions_block)
    assert sec["warning"] is not None
    assert "1/2" in sec["warning"]
    assert "AAA" in sec["unmapped_tickers"]


def test_render_with_missing_position_fields(tmp_path: Path):
    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections
    from scripts.reporting.render_weekly_report import render_html

    payload = _minimal_payload()
    payload = enrich_portfolio_decision_sections(payload, fetch_prices=False)
    out = tmp_path / "index.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    assert "Portfolio Command Center" in html
    assert "Regime rules (full table)" in html or "Regime Rules" in html
    assert "Portfolio Summary" in html
    assert "Market Pulse" in html
    assert "Decision Review" in html
    assert "viz-data-fed" in html or "viz-data-actions" in html
    assert "chart-fed" in html or "chart-actions" in html


def test_render_empty_watchlist(tmp_path: Path):
    from scripts.ingest.portfolio_decision_enrich import enrich_portfolio_decision_sections
    from scripts.reporting.render_weekly_report import render_html

    payload = _minimal_payload()
    payload = enrich_portfolio_decision_sections(payload, fetch_prices=False)
    payload["watchlist_board"] = {"candidates": [], "note": "No watchlist candidates loaded."}
    out = tmp_path / "empty_watch.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    assert "No watchlist candidates loaded" in html or "watchlist_board" not in html


def test_normalized_payload_includes_command_center():
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON

    if not DECISION_WEEKLY_JSON.exists():
        pytest.skip("legacy weekly_report.json missing")
    payload = normalize_weekly_report()
    assert "portfolio_command_center" in payload
    assert "regime_rules" in payload
    assert "position_decisions" in payload


def test_full_render_no_jinja_errors(tmp_path: Path):
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.reporting.render_weekly_report import render_html
    from scripts.ingest.config import DECISION_WEEKLY_JSON

    if not DECISION_WEEKLY_JSON.exists():
        pytest.skip("legacy weekly_report.json missing")
    payload = normalize_weekly_report()
    out = tmp_path / "full.html"
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    assert "{{" not in html or "pcc." not in html  # no raw jinja leaks for pcc
    assert "7600.0" not in html
