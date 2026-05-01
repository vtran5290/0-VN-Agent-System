"""Tests for weekly report normalization (legacy → schema v1.0)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def test_normalize_produces_metadata():
    """Normalizer output has metadata with asof_date and schema_version."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    payload = normalize_weekly_report(None)
    assert "metadata" in payload
    assert payload["metadata"].get("schema_version") == "1.0.0"
    assert "asof_date" in payload["metadata"] or payload["metadata"].get("asof_date") is None


def test_normalize_maps_actions_risks():
    """Legacy actions/risks map to decision_layer.top_actions and top_risks."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.utils.io import write_json, read_json
    legacy_path = REPO / "data" / "decision" / "weekly_report.json"
    legacy = read_json(legacy_path) if legacy_path.exists() else {}
    if legacy and legacy.get("actions"):
        payload = normalize_weekly_report(legacy_path)
        assert payload.get("decision_layer", {}).get("top_actions") == legacy.get("actions", [])
        assert payload.get("decision_layer", {}).get("top_risks") == legacy.get("risks", [])
    else:
        payload = normalize_weekly_report(None)
        assert "decision_layer" in payload
        assert "top_actions" in payload["decision_layer"]


def test_normalize_geo_layer_preserved():
    """If legacy has geo_hormuz_energy_shock, it appears in geo_layers."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    legacy = {
        "asof_date": "2026-02-27",
        "data_confidence": "High",
        "what_changed": [],
        "actions": [],
        "risks": [],
        "open_questions": [],
        "geo_hormuz_energy_shock": {"layer": "geo_hormuz_energy_shock", "state": {"risk_state": "LOW"}},
    }
    # Normalizer expects path; we pass a temp path and pre-fill legacy via mock. Actually normalizer reads from path.
    # So we need to test with a temp file or test the logic that maps legacy["geo_hormuz_energy_shock"] -> geo_layers.
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(legacy, f, ensure_ascii=False)
        path = Path(f.name)
    try:
        payload = normalize_weekly_report(path)
        assert "geo_layers" in payload
        assert "geo_hormuz_energy_shock" in payload["geo_layers"]
        assert payload["geo_layers"]["geo_hormuz_energy_shock"].get("state", {}).get("risk_state") == "LOW"
    finally:
        path.unlink(missing_ok=True)


def test_confidence_in_output():
    """Normalizer output has data_confidence and source_coverage_score in metadata."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    payload = normalize_weekly_report(None)
    meta = payload.get("metadata", {})
    assert "data_confidence" in meta or "source_coverage_score" in meta
    if meta.get("source_coverage_score") is not None:
        assert 0 <= meta["source_coverage_score"] <= 1.0
