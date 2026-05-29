"""Tests for cloud daily report validation — market context tests.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.research.cloud_daily_report_validation.evidence_inventory import build_evidence_registry
from src.research.cloud_daily_report_validation.schema import (
    EVIDENCE_LABEL_VALUES,
    EvidenceLabel,
    EvidenceStatus,
)


def _get_registry() -> pd.DataFrame:
    return build_evidence_registry()


def test_distribution_risk_already_validated():
    """Distribution risk must be registered as PARTIALLY_VALIDATED in evidence registry."""
    df = _get_registry()
    dist_rows = df[
        df["dashboard_output"].str.contains("dist_risk", case=False, na=False)
        | df["dashboard_output"].str.contains("distribution", case=False, na=False)
        | df["field_or_rule"].str.contains("distribution", case=False, na=False)
    ]
    assert not dist_rows.empty, "Distribution risk must be in evidence registry"

    for _, row in dist_rows.iterrows():
        status = str(row.get("evidence_status", ""))
        assert status in (
            EvidenceStatus.PARTIALLY_VALIDATED.value,
            EvidenceStatus.VALIDATED.value,
        ), (
            f"Distribution risk '{row.get('dashboard_output')}' should be PARTIALLY_VALIDATED, "
            f"got '{status}'"
        )


def test_rs_correction_partially_validated():
    """RS correction must be registered as PARTIALLY_VALIDATED."""
    df = _get_registry()
    rs_rows = df[
        df["dashboard_section"].str.contains("RS", case=False, na=False)
        | df["dashboard_output"].str.contains("RS_leaders", case=False, na=False)
    ]
    assert not rs_rows.empty, "RS correction must be in evidence registry"

    rs_leaders = df[df["dashboard_output"].str.contains("RS_leaders", case=False, na=False)]
    if not rs_leaders.empty:
        for _, row in rs_leaders.iterrows():
            status = str(row.get("evidence_status", ""))
            assert status == EvidenceStatus.PARTIALLY_VALIDATED.value, (
                f"RS_leaders should be PARTIALLY_VALIDATED, got '{status}'"
            )


def test_c3_is_context_only():
    """C3 rating must be labeled CONTEXT_ONLY or DISPLAY_ONLY in evidence registry."""
    df = _get_registry()
    c3_rows = df[
        df["dashboard_output"].str.contains("C3", case=False, na=False)
        | df["dashboard_section"].str.contains("C3", case=False, na=False)
    ]
    assert not c3_rows.empty, "C3 rating must be in evidence registry"

    for _, row in c3_rows.iterrows():
        status = str(row.get("evidence_status", ""))
        assert status in (
            EvidenceStatus.CONTEXT_ONLY.value,
            EvidenceStatus.DISPLAY_ONLY.value,
        ), (
            f"C3 '{row.get('dashboard_output')}' must be CONTEXT_ONLY or DISPLAY_ONLY, "
            f"got '{status}'"
        )


def test_breadth_gate_not_backtested():
    """T1/T2 breadth gate must be registered as NOT_BACKTESTED (insufficient data)."""
    df = _get_registry()
    breadth_rows = df[
        df["dashboard_output"].str.contains("breadth", case=False, na=False)
        | df["dashboard_output"].str.contains("T1_permission", case=False, na=False)
        | df["dashboard_output"].str.contains("T2_permission", case=False, na=False)
        | df["field_or_rule"].str.contains("breadth_t1_permission", case=False, na=False)
    ]
    assert not breadth_rows.empty, "Breadth gate must be in evidence registry"

    for _, row in breadth_rows.iterrows():
        status = str(row.get("evidence_status", ""))
        assert status in (
            EvidenceStatus.NOT_BACKTESTED.value,
            EvidenceStatus.BLOCKED_BY_DATA.value,
        ), (
            f"Breadth gate '{row.get('dashboard_output')}' should be NOT_BACKTESTED "
            f"or BLOCKED_BY_DATA (insufficient scan history), got '{status}'"
        )


def test_market_context_label_constrained():
    """All evidence_label values in registry must be from the approved enum."""
    df = _get_registry()
    if "evidence_label" not in df.columns:
        pytest.skip("evidence_label column not present in registry")

    bad_values = [v for v in df["evidence_label"].unique() if v not in EVIDENCE_LABEL_VALUES]
    assert bad_values == [], (
        f"Unapproved evidence_label values found: {bad_values}. "
        f"Allowed: {sorted(EVIDENCE_LABEL_VALUES)}"
    )
