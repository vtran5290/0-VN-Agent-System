"""Tests for cloud daily report validation — inventory framework.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.research.cloud_daily_report_validation.evidence_inventory import (
    build_evidence_registry,
    search_existing_evidence,
)
from src.research.cloud_daily_report_validation.output_inventory import build_output_inventory
from src.research.cloud_daily_report_validation.schema import (
    EVIDENCE_LABEL_VALUES,
    EVIDENCE_STATUS_VALUES,
    EvidenceStatus,
)

# Required columns in evidence registry
REQUIRED_REGISTRY_COLS = [
    "dashboard_section",
    "dashboard_output",
    "field_or_rule",
    "source_file_or_module",
    "already_backtested",
    "existing_backtest_path",
    "existing_result_summary",
    "evidence_status",
    "needs_new_backtest",
    "recommended_test_type",
    "notes",
]


def test_evidence_registry_has_required_columns():
    """Evidence registry must contain all 11 required columns."""
    df = build_evidence_registry()
    assert isinstance(df, pd.DataFrame), "build_evidence_registry() must return a DataFrame"
    assert len(df) > 0, "Evidence registry must not be empty"
    missing = [col for col in REQUIRED_REGISTRY_COLS if col not in df.columns]
    assert missing == [], f"Evidence registry missing required columns: {missing}"


def test_output_inventory_has_all_sections():
    """Output inventory must cover sections A through J."""
    df = build_output_inventory()
    assert isinstance(df, pd.DataFrame), "build_output_inventory() must return a DataFrame"
    assert "section" in df.columns, "output_inventory must have 'section' column"
    sections = set(df["section"].unique())
    required = set("ABCDEFGHIJ")
    missing = required - sections
    assert missing == set(), f"Output inventory missing sections: {missing}"


def test_existing_search_does_not_silently_validate_unknown():
    """UNKNOWN evidence_status items must not be marked as VALIDATED."""
    df = build_evidence_registry()
    assert "evidence_status" in df.columns
    unknown_rows = df[df["evidence_status"] == EvidenceStatus.UNKNOWN.value]
    if not unknown_rows.empty:
        # UNKNOWN items must not have already_backtested=True
        for _, row in unknown_rows.iterrows():
            assert not bool(row.get("already_backtested", False)), (
                f"UNKNOWN status row '{row.get('dashboard_output')}' "
                "must not be marked as already_backtested=True"
            )


def test_evidence_status_values_constrained():
    """All evidence_status values in registry must be from the approved enum."""
    df = build_evidence_registry()
    assert "evidence_status" in df.columns
    bad_values = [v for v in df["evidence_status"].unique() if v not in EVIDENCE_STATUS_VALUES]
    assert bad_values == [], (
        f"Unapproved evidence_status values found: {bad_values}. "
        f"Allowed values: {sorted(EVIDENCE_STATUS_VALUES)}"
    )


def test_registry_produced_before_backtest():
    """Evidence registry must be buildable independently (no backtest dependency)."""
    # This test verifies that build_evidence_registry() can be called without
    # any prior backtest execution — it is a prerequisite, not a derived output.
    try:
        df = build_evidence_registry()
    except Exception as exc:
        pytest.fail(f"build_evidence_registry() raised an exception: {exc}")
    assert df is not None
    assert isinstance(df, pd.DataFrame)
    # Must not require any data files to exist
    assert len(df) > 0, "Registry must have rows even without data files present"


# ---------------------------------------------------------------------------
# Patch 5 — Additional quality tests
# ---------------------------------------------------------------------------

def test_evidence_label_values_constrained():
    """All evidence_label values in registry must be from the approved enum."""
    df = build_evidence_registry()
    if "evidence_label" not in df.columns:
        pytest.skip("evidence_label column not yet present in registry")
    from src.research.cloud_daily_report_validation.schema import EVIDENCE_LABEL_VALUES
    bad = [v for v in df["evidence_label"].dropna().unique() if v not in EVIDENCE_LABEL_VALUES]
    assert bad == [], f"Unapproved evidence_label values: {bad}"


def test_rs_correction_not_directionally_supported_with_10_days():
    """RS Correction must not be labeled DIRECTIONALLY_SUPPORTED with only 10 trading days."""
    df = build_evidence_registry()
    if "evidence_label" not in df.columns:
        pytest.skip("evidence_label column not present")
    rs_rows = df[df["dashboard_output"] == "RS_leaders"]
    if rs_rows.empty:
        pytest.skip("RS_leaders not in registry")
    for _, row in rs_rows.iterrows():
        label = row.get("evidence_label", "")
        assert label != "DIRECTIONALLY_SUPPORTED", (
            "RS Correction cannot be DIRECTIONALLY_SUPPORTED with only 10 trading days. "
            f"Got: {label!r}. Must be INCONCLUSIVE_DIRECTIONAL_ONLY or BLOCKED_BY_DATA."
        )


def test_distribution_risk_label_requires_json_parse():
    """Distribution risk RISK_CONTROL_SUPPORTED must come from parsed JSON, not hardcoded."""
    from src.research.cloud_daily_report_validation.evidence_inventory import parse_distribution_risk_json
    parsed = parse_distribution_risk_json()
    if not parsed["exists"]:
        assert parsed["evidence_label"] == "BLOCKED_BY_DATA", (
            "Distribution risk label must be BLOCKED_BY_DATA when JSON file is missing, "
            f"got: {parsed['evidence_label']!r}"
        )
    else:
        if parsed["parsed_ok"]:
            assert parsed["evidence_label"] in ("RISK_CONTROL_SUPPORTED", "INCONCLUSIVE"), (
                f"Unexpected label when JSON is parsed: {parsed['evidence_label']!r}"
            )


def test_required_output_filenames_exist():
    """Required output filenames must all be generated. Skip if run_all.py not yet run."""
    from src.research.cloud_daily_report_validation.schema import OUTPUT_DIR
    required = [
        "cloud_dashboard_output_inventory.csv",
        "cloud_dashboard_evidence_registry.csv",
        "final_action_validation.csv",
        "t1_t2_gate_validation.csv",
        "exit_logic_validation.csv",
        "ranking_validation.csv",
        "s3_radar_validation.csv",
        "market_context_validation.csv",
        "rs_correction_validation.csv",
        "rs_c3_validation.csv",
        "portfolio_overlay_validation.csv",
        "cloud_action_portfolio_metrics.csv",
        "cloud_action_equity_curves.csv",
        "cloud_action_turnover_capacity.csv",
        "cloud_validation_summary.csv",
    ]
    if not OUTPUT_DIR.is_dir():
        pytest.skip("Output dir not yet created — run run_all.py first")
    missing = [f for f in required if not (OUTPUT_DIR / f).is_file()]
    assert missing == [], (
        f"Required output files missing: {missing}. Run run_all.py to generate."
    )


def test_evidence_search_module_importable():
    """Evidence search module must be importable and callable."""
    from src.research.cloud_daily_report_validation.evidence_search import run_evidence_search
    assert callable(run_evidence_search)


def test_evidence_search_non_empty_for_key_terms():
    """Evidence search must find hits for final_action, cloud_daily_report, phase36."""
    from src.research.cloud_daily_report_validation.evidence_search import run_evidence_search
    df = run_evidence_search(queries=["final_action", "cloud_daily_report", "phase36"])
    assert not df.empty, "Evidence search must return hits for key terms"
    found_queries = set(df["query"].unique())
    expected = {"final_action", "cloud_daily_report", "phase36"}
    missing = expected - found_queries
    assert missing == set(), f"Evidence search returned no hits for: {missing}"


def test_evidence_search_hits_distribution_risk():
    """Evidence search must find hits for distribution risk and C3."""
    from src.research.cloud_daily_report_validation.evidence_search import run_evidence_search
    df = run_evidence_search(queries=["distribution_risk", "c3_rating", "S3"])
    assert not df.empty, "Evidence search must find distribution_risk, C3, S3 references"


def test_market_context_validation_importable():
    """Market context tests must return a non-empty DataFrame with evidence_label column."""
    from src.research.cloud_daily_report_validation.market_context_tests import (
        run_market_context_validation,
    )
    result = run_market_context_validation()
    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0, "Market context validation must return rows"
    assert "evidence_label" in result.columns


def test_portfolio_metrics_all_blocked():
    """Portfolio metrics must all be BLOCKED_BY_DATA with <6 months of scan history."""
    from src.research.cloud_daily_report_validation.validation_summary import (
        build_portfolio_metrics_blocked,
    )
    metrics = build_portfolio_metrics_blocked()
    assert isinstance(metrics, pd.DataFrame)
    assert "acceptance_label" in metrics.columns
    assert all(metrics["acceptance_label"] == "BLOCKED_BY_DATA"), (
        "Portfolio metrics must all be BLOCKED_BY_DATA with insufficient scan history"
    )
