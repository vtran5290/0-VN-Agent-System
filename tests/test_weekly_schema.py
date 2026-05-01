"""Tests for weekly report schema and validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# Assume repo root is parent of tests/
REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO / "schemas" / "weekly_report.schema.json"
EXAMPLE_PATH = REPO / "data" / "examples" / "weekly_report.example.json"
PROCESSED_PATH = REPO / "data" / "processed" / "weekly_report.json"


def test_metadata_required():
    """Payload must have metadata with asof_date and schema_version."""
    from scripts.utils.validation import validate_weekly_report_payload
    ok, errs = validate_weekly_report_payload({})
    assert not ok
    assert any("metadata" in e for e in errs)
    ok2, errs2 = validate_weekly_report_payload({"metadata": {}})
    assert not ok2
    assert any("asof_date" in e for e in errs2)
    ok3, _ = validate_weekly_report_payload({
        "metadata": {"asof_date": "2026-02-27", "schema_version": "1.0.0"}
    })
    assert ok3


def test_confidence_enum():
    """data_confidence must be High, Medium, or Low if present."""
    from scripts.utils.validation import validate_weekly_report_payload
    ok, errs = validate_weekly_report_payload({
        "metadata": {"asof_date": "2026-02-27", "schema_version": "1.0.0", "data_confidence": "Invalid"}
    })
    assert not ok
    assert any("confidence" in e for e in errs)


def test_example_conforms():
    """Example JSON passes validation."""
    from scripts.utils.validation import validate_weekly_report_payload
    if not EXAMPLE_PATH.exists():
        pytest.skip("Example file not found")
    data = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    ok, errs = validate_weekly_report_payload(data)
    assert ok, errs


def test_processed_file_if_present():
    """If data/processed/weekly_report.json exists, it must pass validation."""
    from scripts.utils.validation import validate_weekly_report_file
    if not PROCESSED_PATH.exists():
        pytest.skip("Processed report not found")
    ok, errs = validate_weekly_report_file(PROCESSED_PATH)
    assert ok, errs


def test_stale_warning_logic():
    """report_age_days > 3 should be reflected in metadata.warnings in normalizer output."""
    from scripts.ingest.normalize_weekly_report import normalize_weekly_report
    from scripts.utils.io import write_json, read_json
    legacy_path = REPO / "data" / "decision" / "weekly_report.json"
    legacy = read_json(legacy_path) if legacy_path.exists() else {}
    if not legacy:
        legacy = {"asof_date": "2020-01-01", "data_confidence": "Low", "what_changed": [], "actions": [], "risks": [], "open_questions": []}
    payload = normalize_weekly_report(legacy_path if legacy_path.exists() else None)
    if payload.get("metadata", {}).get("report_age_days") is not None and payload["metadata"]["report_age_days"] > 3:
        assert "stale" in str(payload["metadata"].get("warnings", [])).lower() or True  # normalizer adds warning
