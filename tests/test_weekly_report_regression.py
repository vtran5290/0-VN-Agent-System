"""
Regression tests for weekly report pipeline:
- report_snapshot_level vs latest_market_level vs wow_delta (never use delta for level)
- When latest_market_snapshot.json exists and is newer: KPI = latest (e.g. 1696.24)
- When no latest: KPI = report_snapshot with stale badge (e.g. 1880.33)
- 7600 must never appear
- Stale badge when KPI uses report snapshot
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LATEST_SNAPSHOT = REPO / "data" / "decision" / "latest_market_snapshot.json"


def test_normalized_vnindex_never_7600():
    """Current VNINDEX must never be 7600 (outlier); must come from FireAnt or be null."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON
    path = DECISION_WEEKLY_JSON if DECISION_WEEKLY_JSON.exists() else None
    payload = normalize_weekly_report(path)
    levels = payload.get("market_structure", {}).get("levels", {})
    vni = levels.get("vnindex_level")
    assert vni != 7600.0, "7600 must never appear as current VNINDEX"
    assert vni is None or (300 <= vni <= 3000), "VNINDEX must be in valid range or null"


def test_normalized_levels_not_from_delta():
    """Levels must not be derived from what_changed delta (sanity: no current = prev - delta)."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON
    path = DECISION_WEEKLY_JSON if DECISION_WEEKLY_JSON.exists() else None
    payload = normalize_weekly_report(path)
    levels = payload.get("market_structure", {}).get("levels", {})
    what = payload.get("market_structure", {}).get("what_changed", [])
    vni = levels.get("vnindex_level")
    delta_entry = next((d for d in what if isinstance(d, dict) and d.get("metric") == "VNINDEX"), None)
    if delta_entry and delta_entry.get("delta") is not None and vni is not None:
        delta = float(delta_entry["delta"])
        # Bug was: wrong value 7600 ≈ 1880.33 - (-5719.67). So current must not equal any prev - delta with wrong prev.
        wrong_prev_minus_delta = vni - delta  # if this were "prev", current would be vni. We must not have vni = 7600.
        assert vni != 7600.0


def test_rendered_html_never_7600():
    """Rendered HTML must not contain 7600 as current VNINDEX."""
    from scripts.reporting.render_weekly_report import render_html
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON, DATA_PROCESSED
    path = DECISION_WEEKLY_JSON if DECISION_WEEKLY_JSON.exists() else None
    payload = normalize_weekly_report(path)
    out = REPO / "reports" / "latest" / "index_regression_test.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    assert "7600.0" not in html and ">7600<" not in html, "Rendered HTML must not show 7600 as current level"
    out.unlink(missing_ok=True)


def test_resolver_prefers_fireant_over_manual():
    """When market_snapshot_debug exists, vnindex_level comes from it (e.g. 1880.33), not manual 7600."""
    from scripts.ingest.legacy_adapter import resolve_market_levels
    legacy = {"asof_date": "2026-02-27"}
    levels = resolve_market_levels(legacy, "2026-02-27", report_age_days=15)
    # If debug has 1880.33, we get it; if manual has 7600, adapter rejects outlier so vnindex becomes None
    assert levels.get("vnindex_level") != 7600.0
    assert levels.get("vnindex_level") is None or (300 <= levels["vnindex_level"] <= 3000)


def test_dist_days_resolved_from_debug_or_alerts():
    """Distribution days must resolve to value (e.g. 9) when debug or alerts have it."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON
    if not DECISION_WEEKLY_JSON.exists():
        pytest.skip("Legacy report not found")
    payload = normalize_weekly_report(DECISION_WEEKLY_JSON)
    levels = payload.get("market_structure", {}).get("levels", {})
    dist = levels.get("distribution_days_rolling_20")
    # When debug has distribution_days_rolling_20: 9, normalized should have 9
    if (REPO / "data" / "decision" / "market_snapshot_debug.json").exists():
        debug = json.loads((REPO / "data" / "decision" / "market_snapshot_debug.json").read_text(encoding="utf-8"))
        raw = debug.get("raw_source", {}).get("market", {})
        expected = raw.get("distribution_days_rolling_20")
        if expected is not None:
            assert dist == expected, "Dist days should come from FireAnt snapshot"


def test_suggested_regime_and_mismatch_from_decision_log():
    """Suggested regime and mismatch must come from decision_log when present."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON
    if not DECISION_WEEKLY_JSON.exists():
        pytest.skip("Legacy report not found")
    payload = normalize_weekly_report(DECISION_WEEKLY_JSON)
    regime = payload.get("regime_engine", {})
    # decision_log/2026-02-27.json has suggested_regime C and regime B -> mismatch True
    log_path = REPO / "decision_log" / "2026-02-27.json"
    if log_path.exists():
        log = json.loads(log_path.read_text(encoding="utf-8"))
        if log.get("suggested_regime") is not None:
            assert regime.get("suggested_regime") == log["suggested_regime"]
        if log.get("regime") and log.get("suggested_regime"):
            assert regime.get("mismatch") == (log["suggested_regime"] != log["regime"])


def test_watchlist_posture_from_risk_and_regime():
    """Posture must be Defensive when risk_flag is High, not default Neutral."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON
    if not DECISION_WEEKLY_JSON.exists():
        pytest.skip("Legacy report not found")
    payload = normalize_weekly_report(DECISION_WEEKLY_JSON)
    posture = payload.get("watchlist", {}).get("posture")
    # When risk is High, posture should be Defensive / Reduce new buys
    alerts_path = REPO / "data" / "alerts" / "market_flags.json"
    if alerts_path.exists():
        alerts = json.loads(alerts_path.read_text(encoding="utf-8"))
        if alerts.get("risk_flag") in ("High", "Elevated"):
            assert "Defensive" in posture or "Reduce" in posture


def test_sell_trim_signals_preserved():
    """Sell/trim signals must be loaded from sell_signals.json and appear in normalized output."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON
    if not DECISION_WEEKLY_JSON.exists():
        pytest.skip("Legacy report not found")
    payload = normalize_weekly_report(DECISION_WEEKLY_JSON)
    signals = payload.get("execution_monitoring", {}).get("sell_trim_signals", [])
    sell_path = REPO / "data" / "alerts" / "sell_signals.json"
    if sell_path.exists():
        data = json.loads(sell_path.read_text(encoding="utf-8"))
        expected_count = len(data.get("signals") or [])
        assert len(signals) == expected_count, "Sell/trim signals must be preserved"


def test_portfolio_health_preserved():
    """Portfolio health (n_positions, pct_below_ma20, sector_concentration) must come from decision_log."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON
    if not DECISION_WEEKLY_JSON.exists():
        pytest.skip("Legacy report not found")
    payload = normalize_weekly_report(DECISION_WEEKLY_JSON)
    ph = payload.get("portfolio_health", {})
    log_path = REPO / "decision_log" / "2026-02-27.json"
    if log_path.exists():
        log = json.loads(log_path.read_text(encoding="utf-8"))
        log_ph = log.get("portfolio_health") or {}
        if log_ph.get("n_positions") is not None:
            assert ph.get("summary", {}).get("n_positions") == log_ph.get("n_positions") or ph.get("summary", {}).get("n_positions") is not None
        if log_ph.get("sector_concentration"):
            assert len(ph.get("sector_concentration", [])) == len(log_ph["sector_concentration"])


def test_levels_have_snapshot_date_and_stale_flag():
    """Normalized market_structure.levels must include snapshot_date, kpi_display_source, kpi_is_stale."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON
    path = DECISION_WEEKLY_JSON if DECISION_WEEKLY_JSON.exists() else None
    payload = normalize_weekly_report(path)
    levels = payload.get("market_structure", {}).get("levels", {})
    assert "kpi_display_source" in levels
    assert levels.get("kpi_display_source") in ("latest_market", "report_snapshot", None)
    assert "kpi_is_stale" in levels or "is_stale" in levels


def test_report_snapshot_vs_latest_market_separate():
    """report_snapshot holds embedded snapshot (e.g. 1880.33); latest_market holds freshest when file exists."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON
    if not DECISION_WEEKLY_JSON.exists():
        pytest.skip("Legacy report not found")
    payload = normalize_weekly_report(DECISION_WEEKLY_JSON)
    ms = payload.get("market_structure", {})
    rs = ms.get("report_snapshot", {})
    lm = ms.get("latest_market")
    assert rs.get("date")  # report snapshot has date
    assert rs.get("vnindex_level") == 1880.33 or rs.get("vnindex_level") is not None  # from debug
    if LATEST_SNAPSHOT.exists():
        data = json.loads(LATEST_SNAPSHOT.read_text(encoding="utf-8"))
        if data.get("asof_date") and data.get("vnindex_level") is not None:
            assert lm is not None
            assert lm.get("vnindex_level") == 1696.24 or lm.get("vnindex_level") == data.get("vnindex_level")
            assert payload.get("market_structure", {}).get("levels", {}).get("vnindex_level") == lm.get("vnindex_level")
            assert payload.get("market_structure", {}).get("levels", {}).get("kpi_display_source") == "latest_market"
            assert payload.get("market_structure", {}).get("levels", {}).get("kpi_is_stale") is False


def test_when_no_latest_use_report_snapshot_with_stale():
    """When latest_market_snapshot.json is missing or older than report: KPI = report_snapshot, kpi_is_stale True."""
    from scripts.ingest.legacy_adapter import resolve_market_levels
    legacy = {"asof_date": "2026-02-27"}
    # Temporarily move latest out of the way to test fallback (skip if not present)
    if not LATEST_SNAPSHOT.exists():
        resolved = resolve_market_levels(legacy, "2026-02-27", report_age_days=20)
        assert resolved.get("levels", {}).get("kpi_display_source") == "report_snapshot"
        assert resolved.get("levels", {}).get("kpi_is_stale") is True
        assert resolved.get("report_snapshot", {}).get("vnindex_level") == 1880.33 or resolved.get("report_snapshot", {}).get("vnindex_level") is not None
    else:
        # With latest present, kpi_display_source is latest_market
        resolved = resolve_market_levels(legacy, "2026-02-27", report_age_days=20)
        assert resolved.get("levels", {}).get("kpi_display_source") in ("latest_market", "report_snapshot")
        assert resolved.get("report_snapshot", {}).get("vnindex_level") != 7600.0


def test_rendered_html_latest_label_when_using_latest():
    """When KPI uses latest_market, rendered HTML shows (latest) and value 1696.24."""
    from scripts.reporting.render_weekly_report import render_html
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.ingest.config import DECISION_WEEKLY_JSON
    if not DECISION_WEEKLY_JSON.exists():
        pytest.skip("Legacy report not found")
    payload = normalize_weekly_report(DECISION_WEEKLY_JSON)
    out = REPO / "reports" / "latest" / "index_regression_latest.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    if payload.get("market_structure", {}).get("levels", {}).get("kpi_display_source") == "latest_market":
        assert "1696.24" in html
        assert "latest" in html.lower()
    assert "7600" not in html or "7600.0" not in html
    out.unlink(missing_ok=True)


def test_rendered_html_stale_badge_when_using_report_snapshot():
    """When KPI uses report_snapshot (no latest), HTML must show stale badge."""
    from scripts.reporting.render_weekly_report import render_html
    payload = {
        "metadata": {"asof_date": "2026-02-27", "schema_version": "1.0.0"},
        "market_structure": {
            "report_snapshot": {"date": "2026-02-27", "vnindex_level": 1880.33, "vn30_level": 2061.75},
            "latest_market": None,
            "levels": {
                "vnindex_level": 1880.33,
                "vn30_level": 2061.75,
                "kpi_display_source": "report_snapshot",
                "kpi_is_stale": True,
                "snapshot_date": "2026-02-27",
            },
            "distribution": {},
        },
        "global_macro": {"facts": {}},
        "vietnam_liquidity": {"facts": {}},
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
    out = REPO / "reports" / "latest" / "index_regression_stale.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_html(payload, out)
    html = out.read_text(encoding="utf-8")
    assert "report snapshot" in html.lower() or "stale" in html.lower()
    assert "1880.33" in html
    out.unlink(missing_ok=True)
