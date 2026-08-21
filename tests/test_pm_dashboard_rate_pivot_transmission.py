import json
from pathlib import Path

from scripts.reporting.generate_pm_regime_dashboard import (
    _render_rate_pivot_monitor,
    build_html,
)

REPO = Path(__file__).resolve().parents[1]


def _monitor() -> dict:
    return json.loads((REPO / "data/research/rate_pivot_monitor.json").read_text(encoding="utf-8"))


def test_pm_renders_full_transmission_panel():
    html = _render_rate_pivot_monitor(_monitor())
    for text in (
        "FX PRESSURE EASING",
        "POTENTIAL RESERVE-REBUILD SETUP",
        "STATE 1",
        "NOT CONFIRMED",
        "OBSERVATION",
        "INFERENCE",
        "CONFIRMATION",
        "Regulatory funding relief",
        "Actual monetary liquidity creation",
        "FALSIFIERS",
    ):
        assert text.lower() in html.lower()
    assert "2007 repeat" not in html.lower()
    assert "liquidity boom confirmed" not in html.lower()


def test_g2_is_binding_when_g1_passes_and_g2_fails():
    html = _render_rate_pivot_monitor(_monitor())
    assert "G2" in html and "binding" in html.lower()
    assert "G1 FX veto is binding" not in html


def test_macro_pulse_badge_is_advisory_only():
    data = json.loads((REPO / "data/raw/pm_dashboard_data.json").read_text(encoding="utf-8"))
    html = build_html(data)
    assert "FX → Liquidity: STATE 1 · NOT CONFIRMED" in html
    assert "SYSTEM ROUTING: Reporting only" in html
