"""Tests for weekly report HTML renderer."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = REPO / "data" / "examples" / "weekly_report.example.json"


def test_render_produces_html():
    """Renderer produces HTML from valid payload without crashing."""
    from scripts.reporting.render_weekly_report import render_html
    import json
    if not EXAMPLE_PATH.exists():
        pytest.skip("Example file not found")
    payload = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    out = REPO / "reports" / "latest" / "index_test.html"
    render_html(payload, out)
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "VN Weekly" in html or "Weekly Report" in html
    assert payload.get("metadata", {}).get("asof_date", "") in html or "N/A" in html
    out.unlink(missing_ok=True)


def test_render_handles_minimal_payload():
    """Renderer handles minimal payload (metadata only)."""
    from scripts.reporting.render_weekly_report import render_html
    payload = {
        "metadata": {"asof_date": "2026-02-27", "schema_version": "1.0.0", "data_confidence": "Low"},
        "global_macro": {"facts": {}, "what_changed": []},
        "vietnam_liquidity": {"facts": {}},
        "market_structure": {"levels": {}, "distribution": {}},
        "regime_engine": {"inputs": {}},
        "decision_layer": {},
        "watchlist": {},
        "execution_monitoring": {"risk_flags": {}},
        "portfolio_health": {},
        "geo_layers": {},
        "open_questions": [],
        "monitoring_next_week": [],
        "playbook_if_x_then_y": [],
    }
    out = REPO / "reports" / "latest" / "index_minimal_test.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_html(payload, out)
    assert out.exists()
    assert "2026-02-27" in out.read_text(encoding="utf-8")
    out.unlink(missing_ok=True)
