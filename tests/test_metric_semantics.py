"""Guardrails for global metric semantics (DXY vs broad USD, payroll level vs change)."""
from __future__ import annotations

import pytest

from src.metrics.registry import assert_no_dtwexbgs_labeled_dxy, assert_payroll_level_not_labeled_nfp_change


def test_dtwexbgs_allowed_only_for_usd_broad_metric_key() -> None:
    audit = [
        {
            "metric_key": "usd_broad_index_fred",
            "source_series_code_or_page": "DTWEXBGS",
            "semantic_label": "Nominal Broad U.S. Dollar Index (FRED DTWEXBGS)",
        }
    ]
    assert_no_dtwexbgs_labeled_dxy(audit)


def test_dtwexbgs_on_wrong_metric_key_raises() -> None:
    audit = [
        {
            "metric_key": "ust_2y",
            "source_series_code_or_page": "DTWEXBGS",
            "semantic_label": "wrong",
        }
    ]
    with pytest.raises(ValueError, match="usd_broad_index_fred"):
        assert_no_dtwexbgs_labeled_dxy(audit)


def test_payroll_level_row_must_not_be_labeled_as_change() -> None:
    audit = [
        {
            "metric_key": "nonfarm_payroll_level_thousands",
            "semantic_label": "Nonfarm payroll month-over-month change",
        }
    ]
    with pytest.raises(ValueError, match="payroll level"):
        assert_payroll_level_not_labeled_nfp_change(audit)
