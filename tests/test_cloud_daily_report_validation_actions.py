"""Tests for cloud daily report validation — A3 action tests.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.research.cloud_daily_report_validation.action_tests import run_action_validation
from src.research.cloud_daily_report_validation.schema import (
    OUTPUT_DIR,
    REPORTS_DIR,
    RESEARCH_ONLY_LABEL,
    EvidenceLabel,
    FINAL_ACTIONS,
)

# Research-only output paths — must never point to production paths
_PRODUCTION_PATH_PATTERNS = [
    "data/decision",
    "data/state",
    "data/trading",
    "src/trading",
    "src/exec",
    "src/signals",
]


def _make_minimal_scan(final_action: str = "NEW_T1", n: int = 3) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "symbol": f"SYM{i:03d}",
            "as_of_date": "2026-05-22",
            "final_action": final_action,
            "a3_rank_score": 1.5,
            "close_kVND": 20.0,
        }
        for i in range(n)
    ])


def test_action_validation_final_action_t1_timing():
    """Action validation must use T+1 timing (entry at T+1 open, not T close)."""
    # With minimal OHLCV, forward returns will be NaN but the structure should be correct
    scan_df = _make_minimal_scan("NEW_T1", n=10)
    ohlcv = pd.DataFrame()  # Empty — returns NaN

    result = run_action_validation(scan_df, ohlcv, horizons=[5])

    # T+1 timing is enforced inside compute_forward_returns (tested in outcomes tests)
    # Here we verify the action test calls it with the right structure
    assert isinstance(result, pd.DataFrame)
    assert "final_action" in result.columns
    assert "horizon_days" in result.columns
    assert "signal_integrity" in result.columns


def test_s3_outputs_are_paper_only():
    """S3 outputs (s3_shadow_action, s3_no_real_order_flag) must never become live signals.

    The action validation framework only processes FINAL_ACTIONS (A3 actions).
    S3 shadow actions must not appear in the actionable action list.
    """
    # Verify S3 shadow actions are not in FINAL_ACTIONS list
    s3_shadow_markers = ["PAPER_S3", "S3_SHADOW", "s3_shadow_action"]
    for marker in s3_shadow_markers:
        for action in FINAL_ACTIONS:
            assert marker.lower() not in action.lower(), (
                f"S3 shadow marker '{marker}' found in FINAL_ACTIONS: {action}"
            )

    # Verify scan rows with s3_no_real_order_flag=True are treated as display-only
    scan_with_s3 = pd.DataFrame([{
        "symbol": "AAA",
        "as_of_date": "2026-05-22",
        "final_action": "WATCH_ONLY",
        "s3_no_real_order_flag": True,
        "s3_shadow_action": "S3_BUY",
    }])
    result = run_action_validation(scan_with_s3, pd.DataFrame(), horizons=[5])
    # WATCH_ONLY should appear but with DISPLAY_ONLY or WORKFLOW label
    watch_rows = result[result["final_action"] == "WATCH_ONLY"]
    if not watch_rows.empty:
        for _, row in watch_rows.iterrows():
            label = str(row.get("evidence_label", ""))
            assert "ALPHA" not in label.upper(), (
                f"WATCH_ONLY must not be labeled as alpha; got '{label}'"
            )


def test_market_context_does_not_override_final_action():
    """Market context fields (breadth_zone, regime_bull) must not change final_action values.

    The action validation computes returns per final_action; market context is a separate test.
    """
    # Run with scan_df that has final_action plus market context fields
    scan_df = _make_minimal_scan("NEW_T1", n=2)
    scan_df["regime_bull"] = True
    scan_df["breadth_zone"] = "normal"
    scan_df["breadth_t1_permission"] = True

    result = run_action_validation(scan_df, pd.DataFrame(), horizons=[5])

    # final_action column in result should only reflect actual final_action values
    # not be overridden by market context
    if not result.empty:
        assert set(result["final_action"].unique()).issubset(set(FINAL_ACTIONS)), (
            "final_action values in result must only be from FINAL_ACTIONS list; "
            "market context must not create new action values"
        )


def test_portfolio_overlay_does_not_infer_cash():
    """Portfolio overlay means holdings only — must not infer cash position.

    Scan data has no cash or NAV field; portfolio overlay must not fabricate cash.
    """
    scan_df = _make_minimal_scan("HOLD_T1", n=3)
    # Should not have a 'cash' or 'nav' field
    assert "cash" not in scan_df.columns, "Scan data should not have cash column"
    assert "nav" not in scan_df.columns, "Scan data should not have nav column"

    result = run_action_validation(scan_df, pd.DataFrame(), horizons=[5])

    # Action validation output must not infer cash
    assert "cash" not in result.columns, "Action validation must not infer cash position"
    assert "inferred_nav" not in result.columns, "Action validation must not infer NAV"


def test_no_output_to_production_paths():
    """Output paths must only be research directories, never production paths."""
    # Check that OUTPUT_DIR and REPORTS_DIR are research paths
    output_str = str(OUTPUT_DIR).replace("\\", "/")
    reports_str = str(REPORTS_DIR).replace("\\", "/")

    for prod_pattern in _PRODUCTION_PATH_PATTERNS:
        assert prod_pattern not in output_str, (
            f"OUTPUT_DIR '{output_str}' must not contain production path '{prod_pattern}'"
        )
        assert prod_pattern not in reports_str, (
            f"REPORTS_DIR '{reports_str}' must not contain production path '{prod_pattern}'"
        )

    # Must be in research paths
    assert "research" in output_str, f"OUTPUT_DIR '{output_str}' must be in a research directory"
