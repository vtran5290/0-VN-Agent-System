"""Tests for cloud daily report validation — reporting and review pack.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.research.cloud_daily_report_validation.evidence_inventory import build_evidence_registry
from src.research.cloud_daily_report_validation.output_inventory import build_output_inventory
from src.research.cloud_daily_report_validation.reporting import (
    generate_evidence_inventory_html,
    generate_validation_html,
)
from src.research.cloud_daily_report_validation.review_pack import build_review_pack
from src.research.cloud_daily_report_validation.schema import (
    DASHBOARD_RECOMMENDATION_VALUES,
    EVIDENCE_LABEL_VALUES,
    EVIDENCE_STATUS_VALUES,
    RESEARCH_ONLY_LABEL,
    EvidenceLabel,
    EvidenceStatus,
)
from src.research.cloud_daily_report_validation.portfolio_overlay_tests import (
    run_portfolio_overlay_validation,
)


def _make_minimal_registry() -> pd.DataFrame:
    return build_evidence_registry()


def _make_minimal_inventory() -> pd.DataFrame:
    return build_output_inventory()


def test_html_includes_research_only_banner():
    """Generated HTML must contain RESEARCH_ONLY_NOT_PRODUCTION banner."""
    registry = _make_minimal_registry()
    inventory = _make_minimal_inventory()
    html = generate_evidence_inventory_html(registry, inventory)

    assert isinstance(html, str), "HTML output must be a string"
    assert RESEARCH_ONLY_LABEL in html, (
        f"HTML must contain '{RESEARCH_ONLY_LABEL}' safety banner"
    )


def test_validation_html_includes_research_only_banner():
    """Main validation HTML must contain RESEARCH_ONLY_NOT_PRODUCTION banner."""
    all_results = {"test_section": pd.DataFrame([{"col": "val"}])}
    html = generate_validation_html(all_results)
    assert RESEARCH_ONLY_LABEL in html, (
        f"Validation HTML must contain '{RESEARCH_ONLY_LABEL}' safety banner"
    )


def test_evidence_labels_constrained_to_enum():
    """All evidence_label values must be from the approved EvidenceLabel enum."""
    registry = _make_minimal_registry()
    if "evidence_label" not in registry.columns:
        pytest.skip("evidence_label not in registry")

    bad_values = [
        v for v in registry["evidence_label"].unique()
        if v not in EVIDENCE_LABEL_VALUES
    ]
    assert bad_values == [], (
        f"Unapproved evidence_label values: {bad_values}. "
        f"Allowed: {sorted(EVIDENCE_LABEL_VALUES)}"
    )


def test_dashboard_recommendations_constrained():
    """All dashboard_recommendation values must be from the approved enum."""
    registry = _make_minimal_registry()
    if "dashboard_recommendation" not in registry.columns:
        pytest.skip("dashboard_recommendation not in registry")

    bad_values = [
        v for v in registry["dashboard_recommendation"].unique()
        if v not in DASHBOARD_RECOMMENDATION_VALUES
    ]
    assert bad_values == [], (
        f"Unapproved dashboard_recommendation values: {bad_values}. "
        f"Allowed: {sorted(DASHBOARD_RECOMMENDATION_VALUES)}"
    )


def test_blocked_by_data_used_when_data_unavailable():
    """Portfolio overlay must be BLOCKED_BY_DATA when no historical positions exist."""
    result = run_portfolio_overlay_validation()
    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0, "Portfolio overlay validation must return at least one row"

    # All overlay action tests (not the requirements row) must be BLOCKED_BY_DATA
    action_rows = result[result["test"].str.startswith("portfolio_overlay_", na=False)]
    if not action_rows.empty:
        for _, row in action_rows.iterrows():
            label = str(row.get("evidence_label", ""))
            assert label == EvidenceLabel.BLOCKED_BY_DATA.value, (
                f"Portfolio overlay action '{row.get('test')}' must be BLOCKED_BY_DATA "
                f"(no historical positions), got '{label}'"
            )


def test_review_pack_contains_required_files():
    """Review pack zip must contain all required files."""
    required_files = [
        "implementation_report.md",
        "open_questions_for_chatgpt.md",
        "source_file_inventory.csv",
        "test_log.txt",
        "implementation_diff.patch",
        "README.md",
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = build_review_pack(output_dir=tmp_path, date_str="20260529test")

        assert zip_path.is_file(), f"Review pack zip not created at {zip_path}"
        assert zip_path.suffix == ".zip", "Review pack must be a .zip file"

        with zipfile.ZipFile(zip_path, "r") as zf:
            zip_contents = set(zf.namelist())
            for required in required_files:
                assert required in zip_contents, (
                    f"Review pack must contain '{required}'; found: {sorted(zip_contents)}"
                )


def test_review_pack_source_snapshots_present():
    """Review pack must contain source_snapshots/ directory with .py files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = build_review_pack(output_dir=tmp_path, date_str="20260529snap")

        with zipfile.ZipFile(zip_path, "r") as zf:
            zip_contents = set(zf.namelist())
            snapshot_entries = [f for f in zip_contents if f.startswith("source_snapshots/")]
            assert len(snapshot_entries) > 0, (
                f"Review pack must contain source_snapshots/ entries; "
                f"zip contains: {sorted(zip_contents)[:10]}"
            )


def test_review_pack_test_log_not_placeholder():
    """test_log.txt must not be the old 'No test log found' placeholder string.

    When running inside pytest, build_review_pack() skips nested pytest (to avoid
    recursion) and returns a 'Running inside pytest session' note — that is acceptable.
    The banned string is only the old static placeholder 'No test log found.'
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = build_review_pack(output_dir=tmp_path, date_str="20260529log")

        with zipfile.ZipFile(zip_path, "r") as zf:
            log_content = zf.read("test_log.txt").decode("utf-8")
        # The old static placeholder is forbidden
        assert "No test log found." not in log_content, (
            "test_log.txt must not contain the old 'No test log found.' placeholder. "
            "The review pack builder must capture real output or skip-note."
        )
        # Must be non-trivially short
        assert len(log_content) > 30, "test_log.txt is suspiciously short"


def test_review_pack_readme_has_manifest():
    """README.md in review pack must contain a file manifest table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = build_review_pack(output_dir=tmp_path, date_str="20260529readme")

        with zipfile.ZipFile(zip_path, "r") as zf:
            if "README.md" not in zf.namelist():
                pytest.fail("README.md not found in review pack")
            readme = zf.read("README.md").decode("utf-8")
        assert "File Manifest" in readme, "README.md must contain 'File Manifest' section"
        assert "implementation_report.md" in readme, "README.md manifest must list implementation_report.md"
        assert "test_log.txt" in readme, "README.md manifest must list test_log.txt"


def test_source_file_inventory_non_empty():
    """source_file_inventory.csv must not be empty or have zero data rows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = build_review_pack(output_dir=tmp_path, date_str="20260529inv")

        with zipfile.ZipFile(zip_path, "r") as zf:
            if "source_file_inventory.csv" not in zf.namelist():
                pytest.fail("source_file_inventory.csv not in review pack")
            content = zf.read("source_file_inventory.csv").decode("utf-8")

        import io
        df = pd.read_csv(io.StringIO(content))
        assert len(df) > 0, (
            "source_file_inventory.csv must have at least one data row (non-empty). "
            "The inventory must list the new validation source files."
        )
        assert "file_path" in df.columns, "source_file_inventory.csv must have 'file_path' column"


def test_inconclusive_directional_only_is_valid_label():
    """INCONCLUSIVE_DIRECTIONAL_ONLY must be a valid EvidenceLabel enum value."""
    from src.research.cloud_daily_report_validation.schema import EvidenceLabel, EVIDENCE_LABEL_VALUES
    assert "INCONCLUSIVE_DIRECTIONAL_ONLY" in EVIDENCE_LABEL_VALUES, (
        "INCONCLUSIVE_DIRECTIONAL_ONLY must be added to EvidenceLabel enum"
    )


def test_no_required_validation_silently_skipped():
    """All 9 final_action classes must appear in the evidence registry."""
    from src.research.cloud_daily_report_validation.schema import FINAL_ACTIONS
    registry = _make_minimal_registry()
    documented_outputs = set(registry["dashboard_output"].unique())
    # Each final action must appear in registry as dashboard_output OR field_or_rule
    documented_fields = set(registry.get("field_or_rule", pd.Series()).unique())
    for action in FINAL_ACTIONS:
        # Check if action appears in either column
        in_output = any(action in str(v) for v in documented_outputs)
        in_field = any(action in str(v) for v in documented_fields)
        assert in_output or in_field, (
            f"final_action '{action}' is not documented in the evidence registry. "
            "Every final_action class must have an evidence entry."
        )
