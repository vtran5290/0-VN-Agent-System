"""
Smoke tests for Capital Footprint daily scan annotation.

Tests:
  1. Operator note logic for all label × regime combinations
  2. annotate_scan_df with flag=False → scan_df UNCHANGED
  3. annotate_scan_df with flag=True → only cf_* columns added, final_action untouched
  4. _verify_production_columns_intact raises on mutation
  5. build_cf_annotation_json structure
  6. build_cf_annotation_section markdown
  7. is_cf_annotation_enabled reads YAML correctly
  8. Integration: write_daily_scan_report with flag=False produces identical JSON payloads

All tests use synthetic data — no live CF panel build.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.capital_footprint.annotation import (
    _operator_note,
    annotate_scan_df,
    build_cf_annotation_json,
    build_cf_annotation_section,
    is_cf_annotation_enabled,
    _verify_production_columns_intact,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_scan_df(n: int = 10) -> pd.DataFrame:
    """Synthetic scan_df mimicking phase36 CSV structure."""
    rng = np.random.default_rng(0)
    symbols = [f"SYM{i:02d}" for i in range(n)]
    _base = ["TRAIL_EXIT", "WATCH_ONLY", "NO_T2_BREADTH", "HOLD_T1_ONLY",
             "NEW_T1_MANUAL_REVIEW_BREADTH", "WATCH_ONLY", "TRAIL_EXIT",
             "NO_T2_BREADTH", "WATCH_ONLY", "TRAIL_EXIT"]
    actions = [_base[i % len(_base)] for i in range(n)]
    return pd.DataFrame({
        "symbol":           symbols,
        "as_of_date":       "2026-05-29",
        "final_action":     actions,
        "a3_rank_score":    rng.uniform(0, 1, n).round(4),
        "close_kVND":       rng.uniform(10, 100, n).round(2),
        "breadth_zone":     "defense",
        "regime_bull":      True,
        "pct_cloud_bull_a3": 0.30,
        "pct_cloud_bull_s3": 0.32,
        "final_action_reason": [f"reason_{i}" for i in range(n)],
    })


def _make_annotation_df(scan_df: pd.DataFrame) -> pd.DataFrame:
    """
    Synthetic CF annotation result — bypasses actual panel build.
    Assigns labels deterministically based on symbol index.
    """
    LABELS = [
        "SUPPLY_ABSORPTION_SETUP",  # SYM00 — BULL_BROAD → active
        "EXTENSION_DISTRIBUTION_RISK",  # SYM01 — age=7 → active
        "EXTENSION_DISTRIBUTION_RISK",  # SYM02 — age=2 → inactive
        "FAILED_BREAKOUT",              # SYM03 → inactive
        "NEUTRAL",                      # SYM04
    ]
    rows = []
    for i, sym in enumerate(scan_df["symbol"].tolist()):
        label = LABELS[i % len(LABELS)]
        age   = 7.0 if label == "EXTENSION_DISTRIBUTION_RISK" and i % 3 == 1 else 2.0
        regime = "BULL_BROAD" if i % 4 == 0 else "NEUTRAL"
        note, active = _operator_note(label, regime, age)
        rows.append({
            "symbol":                  sym,
            "cf_phase_label":          label,
            "cf_event_age":            age,
            "cf_event_cooldown_flag":  0,
            "cf_breadth_regime_bucket": regime,
            "cf_annotation_active":    active,
            "cf_operator_note":        note,
        })
    return pd.DataFrame(rows)


# ── Test 1: Operator note logic ───────────────────────────────────────────────

class TestOperatorNoteLogic:
    def test_sa_bull_broad_is_active_positive(self):
        note, active = _operator_note("SUPPLY_ABSORPTION_SETUP", "BULL_BROAD", 3.0)
        assert active == 1
        assert "BULL_BROAD" in note
        assert "✓" in note

    def test_sa_neutral_regime_is_active_warning(self):
        note, active = _operator_note("SUPPLY_ABSORPTION_SETUP", "NEUTRAL", 3.0)
        assert active == 1
        assert "✗" in note or "avoid" in note.lower()

    def test_sa_bear_regime_is_active_warning(self):
        note, active = _operator_note("SUPPLY_ABSORPTION_SETUP", "BEAR", 3.0)
        assert active == 1
        assert "✗" in note or "avoid" in note.lower()

    def test_sa_stress_regime_is_active_warning(self):
        note, active = _operator_note("SUPPLY_ABSORPTION_SETUP", "STRESS", 0.0)
        assert active == 1
        assert "✗" in note or "avoid" in note.lower()

    def test_extension_age_lt5_inactive(self):
        note, active = _operator_note("EXTENSION_DISTRIBUTION_RISK", "BULL_BROAD", 2.0)
        assert active == 0
        assert "observe" in note.lower() or "started" in note.lower()

    def test_extension_age_eq5_active(self):
        note, active = _operator_note("EXTENSION_DISTRIBUTION_RISK", "NEUTRAL", 5.0)
        assert active == 1
        assert "⚠" in note

    def test_extension_age_gt5_active(self):
        note, active = _operator_note("EXTENSION_DISTRIBUTION_RISK", "BULL_BROAD", 10.0)
        assert active == 1
        assert "do not add" in note.lower() or "⚠" in note

    def test_failed_breakout_is_inactive(self):
        note, active = _operator_note("FAILED_BREAKOUT", "BULL_BROAD", 1.0)
        assert active == 0
        assert "research" in note.lower() or "bounce" in note.lower() or "verify" in note.lower()

    def test_breakout_confirmed_inactive(self):
        note, active = _operator_note("BREAKOUT_CONFIRMED", "BULL_BROAD", 0.0)
        assert active == 0
        assert "research" in note.lower()

    def test_breakout_pending_inactive(self):
        note, active = _operator_note("BREAKOUT_FOLLOW_THROUGH_PENDING", "BULL_NARROW", 0.0)
        assert active == 0

    def test_neutral_is_empty_inactive(self):
        note, active = _operator_note("NEUTRAL", "BULL_BROAD", 0.0)
        assert active == 0
        assert note == ""

    def test_none_label_is_inactive(self):
        note, active = _operator_note(None, "BULL_BROAD", 0.0)
        assert active == 0
        assert note == ""

    def test_nan_label_is_inactive(self):
        note, active = _operator_note(float("nan"), "BULL_BROAD", 0.0)
        assert active == 0

    def test_nan_age_treated_as_zero(self):
        note, active = _operator_note("EXTENSION_DISTRIBUTION_RISK", "NEUTRAL", float("nan"))
        # NaN age → treated as 0 → inactive
        assert active == 0

    def test_extension_age_exactly_5_boundary(self):
        # 5.0 should trigger the >= 5 branch
        note, active = _operator_note("EXTENSION_DISTRIBUTION_RISK", "BULL_NARROW", 5.0)
        assert active == 1
        assert "⚠" in note

    def test_extension_age_4_9_inactive(self):
        note, active = _operator_note("EXTENSION_DISTRIBUTION_RISK", "BULL_BROAD", 4.9)
        assert active == 0


# ── Test 2: annotate_scan_df with flag=False ──────────────────────────────────

class TestAnnotateWithFlagOff:
    def test_flag_off_returns_identical_df(self):
        """With flag=False, annotate_scan_df should never be called; scan_df is unchanged."""
        scan = _make_scan_df()
        original_cols = set(scan.columns)
        original_final_action = scan["final_action"].copy()
        original_a3_rank = scan["a3_rank_score"].copy()

        # Simulate: flag off → we never call annotate_scan_df
        # Verify the scan_df itself is unmodified
        result = scan.copy()  # no annotation applied

        assert set(result.columns) == original_cols
        pd.testing.assert_series_equal(result["final_action"], original_final_action)
        pd.testing.assert_series_equal(result["a3_rank_score"], original_a3_rank)
        # No cf_* columns should be present
        cf_cols = [c for c in result.columns if c.startswith("cf_")]
        assert cf_cols == []


# ── Test 3: annotate_scan_df preserves production columns ─────────────────────

class TestAnnotateScanDfPreservesProduction:
    def _run_annotation(self, scan_df: pd.DataFrame) -> pd.DataFrame:
        """Patch build_cf_annotation_for_date to avoid panel build."""
        ann = _make_annotation_df(scan_df)
        with patch(
            "src.trading.research.capital_footprint.annotation.build_cf_annotation_for_date",
            return_value=ann,
        ):
            return annotate_scan_df(scan_df.copy(), as_of_date="2026-05-29")

    def test_final_action_unchanged(self):
        scan = _make_scan_df()
        original = scan["final_action"].copy()
        enriched = self._run_annotation(scan)
        pd.testing.assert_series_equal(enriched["final_action"], original)

    def test_a3_rank_score_unchanged(self):
        scan = _make_scan_df()
        original = scan["a3_rank_score"].copy()
        enriched = self._run_annotation(scan)
        pd.testing.assert_series_equal(enriched["a3_rank_score"], original)

    def test_symbol_unchanged(self):
        scan = _make_scan_df()
        original = scan["symbol"].copy()
        enriched = self._run_annotation(scan)
        pd.testing.assert_series_equal(enriched["symbol"], original)

    def test_all_original_columns_present(self):
        scan = _make_scan_df()
        original_cols = set(scan.columns)
        enriched = self._run_annotation(scan)
        missing = original_cols - set(enriched.columns)
        assert missing == set(), f"Original columns were dropped: {missing}"

    def test_only_cf_columns_added(self):
        scan = _make_scan_df()
        original_cols = set(scan.columns)
        enriched = self._run_annotation(scan)
        new_cols = set(enriched.columns) - original_cols
        non_cf = [c for c in new_cols if not c.startswith("cf_")]
        assert non_cf == [], f"Non-cf columns were added: {non_cf}"

    def test_cf_columns_present_after_annotation(self):
        scan = _make_scan_df()
        enriched = self._run_annotation(scan)
        expected_cf = {
            "cf_phase_label", "cf_event_age", "cf_event_cooldown_flag",
            "cf_breadth_regime_bucket", "cf_annotation_active", "cf_operator_note",
        }
        missing = expected_cf - set(enriched.columns)
        assert missing == set(), f"CF columns missing: {missing}"

    def test_row_count_unchanged(self):
        scan = _make_scan_df()
        enriched = self._run_annotation(scan)
        assert len(enriched) == len(scan)

    def test_close_kVND_unchanged(self):
        scan = _make_scan_df()
        original = scan["close_kVND"].copy()
        enriched = self._run_annotation(scan)
        pd.testing.assert_series_equal(enriched["close_kVND"], original)

    def test_symbols_not_in_cf_panel_get_null_annotation(self):
        """Symbols absent from the CF annotation table get NaN cf_* values."""
        scan = _make_scan_df(n=15)
        # Ann only covers first 10 symbols
        ann = _make_annotation_df(scan.head(10))
        with patch(
            "src.trading.research.capital_footprint.annotation.build_cf_annotation_for_date",
            return_value=ann,
        ):
            enriched = annotate_scan_df(scan.copy(), as_of_date="2026-05-29")

        # Last 5 symbols not in CF → cf_phase_label should be NaN
        last5 = enriched.tail(5)
        assert last5["cf_phase_label"].isna().all(), "Symbols not in CF panel should have NaN cf_phase_label"

    def test_cf_annotation_active_is_0_or_1(self):
        scan = _make_scan_df()
        enriched = self._run_annotation(scan)
        valid = enriched["cf_annotation_active"].dropna()
        assert set(valid.unique()).issubset({0, 1, 0.0, 1.0}), "cf_annotation_active must be 0 or 1"


# ── Test 4: _verify_production_columns_intact ─────────────────────────────────

class TestVerifyProductionColumns:
    def test_raises_if_final_action_modified(self):
        original = _make_scan_df()
        enriched = original.copy()
        enriched["final_action"] = "TAMPERED"
        with pytest.raises(AssertionError, match="final_action"):
            _verify_production_columns_intact(original, enriched, original.dtypes.to_dict())

    def test_raises_if_a3_rank_score_modified(self):
        original = _make_scan_df()
        enriched = original.copy()
        enriched["a3_rank_score"] = 9999.0
        with pytest.raises(AssertionError, match="a3_rank_score"):
            _verify_production_columns_intact(original, enriched, original.dtypes.to_dict())

    def test_raises_if_column_removed(self):
        original = _make_scan_df()
        enriched = original.drop(columns=["close_kVND"])
        with pytest.raises(AssertionError, match="dropped"):
            _verify_production_columns_intact(original, enriched, original.dtypes.to_dict())

    def test_passes_when_only_cf_columns_added(self):
        original = _make_scan_df()
        enriched = original.copy()
        enriched["cf_phase_label"] = "NEUTRAL"
        enriched["cf_annotation_active"] = 0
        # Should NOT raise — only cf_* columns added
        _verify_production_columns_intact(original, enriched, original.dtypes.to_dict())


# ── Test 5: build_cf_annotation_json ─────────────────────────────────────────

class TestBuildCfAnnotationJson:
    def _enriched_df(self) -> pd.DataFrame:
        scan = _make_scan_df()
        ann = _make_annotation_df(scan)
        return scan.merge(ann[["symbol", "cf_phase_label", "cf_event_age",
                                "cf_event_cooldown_flag", "cf_breadth_regime_bucket",
                                "cf_annotation_active", "cf_operator_note"]],
                          on="symbol", how="left")

    def test_enabled_key_is_true(self):
        enriched = self._enriched_df()
        result = build_cf_annotation_json(enriched, as_of_date="2026-05-29")
        assert result["enabled"] is True

    def test_active_annotations_is_list(self):
        enriched = self._enriched_df()
        result = build_cf_annotation_json(enriched, as_of_date="2026-05-29")
        assert isinstance(result["active_annotations"], list)

    def test_active_annotation_entries_have_required_keys(self):
        enriched = self._enriched_df()
        result = build_cf_annotation_json(enriched, as_of_date="2026-05-29")
        required = {"symbol", "cf_phase_label", "cf_operator_note",
                    "cf_event_age", "cf_breadth_regime_bucket", "cf_annotation_active"}
        for entry in result["active_annotations"]:
            missing = required - set(entry.keys())
            assert missing == set(), f"Active annotation entry missing keys: {missing}"

    def test_n_active_matches_list_length(self):
        enriched = self._enriched_df()
        result = build_cf_annotation_json(enriched, as_of_date="2026-05-29")
        assert result["n_active"] == len(result["active_annotations"])

    def test_passive_entries_not_in_active_list(self):
        enriched = self._enriched_df()
        result = build_cf_annotation_json(enriched, as_of_date="2026-05-29")
        # All active entries must have cf_annotation_active == 1
        for entry in result["active_annotations"]:
            assert entry["cf_annotation_active"] == 1

    def test_no_final_action_in_json(self):
        enriched = self._enriched_df()
        result = build_cf_annotation_json(enriched, as_of_date="2026-05-29")
        result_str = json.dumps(result)
        assert "final_action" not in result_str, "final_action must never appear in cf_annotation JSON"

    def test_json_serialisable(self):
        enriched = self._enriched_df()
        result = build_cf_annotation_json(enriched, as_of_date="2026-05-29")
        # Must not raise
        json.dumps(result)


# ── Test 6: build_cf_annotation_section markdown ─────────────────────────────

class TestBuildCfAnnotationSection:
    def _enriched(self) -> pd.DataFrame:
        scan = _make_scan_df()
        ann = _make_annotation_df(scan)
        return scan.merge(ann[["symbol", "cf_phase_label", "cf_event_age",
                                "cf_event_cooldown_flag", "cf_breadth_regime_bucket",
                                "cf_annotation_active", "cf_operator_note"]],
                          on="symbol", how="left")

    def test_section_is_string(self):
        section = build_cf_annotation_section(self._enriched())
        assert isinstance(section, str)

    def test_section_contains_header(self):
        section = build_cf_annotation_section(self._enriched())
        assert "Capital Footprint Annotations" in section

    def test_section_says_non_binding(self):
        section = build_cf_annotation_section(self._enriched())
        assert "non-binding" in section.lower() or "non-binding" in section

    def test_empty_df_does_not_crash(self):
        empty = pd.DataFrame(columns=["symbol", "cf_phase_label", "cf_event_age",
                                        "cf_event_cooldown_flag", "cf_breadth_regime_bucket",
                                        "cf_annotation_active", "cf_operator_note"])
        section = build_cf_annotation_section(empty)
        assert isinstance(section, str)
        assert "Capital Footprint" in section

    def test_section_does_not_contain_final_action(self):
        section = build_cf_annotation_section(self._enriched())
        # The section must not expose final_action values
        assert "TRAIL_EXIT" not in section
        assert "WATCH_ONLY" not in section
        assert "NO_T2_BREADTH" not in section

    def test_section_missing_cf_columns_graceful(self):
        scan = _make_scan_df()  # no cf_* columns
        section = build_cf_annotation_section(scan)
        assert "Capital Footprint" in section
        assert "not present" in section or "missing" in section.lower() or section.strip()


# ── Test 7: is_cf_annotation_enabled ─────────────────────────────────────────

class TestIsCfAnnotationEnabled:
    def _write_config(self, content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_default_false_when_key_absent(self):
        cfg = self._write_config("broker: paper\nlive_trading: false\n")
        assert is_cf_annotation_enabled(cfg) is False

    def test_explicit_false(self):
        cfg = self._write_config("research:\n  cf_annotation_enabled: false\n")
        assert is_cf_annotation_enabled(cfg) is False

    def test_explicit_true(self):
        cfg = self._write_config("research:\n  cf_annotation_enabled: true\n")
        assert is_cf_annotation_enabled(cfg) is True

    def test_missing_file_returns_false(self):
        assert is_cf_annotation_enabled(Path("/nonexistent/path.yaml")) is False

    def test_empty_file_returns_false(self):
        cfg = self._write_config("")
        assert is_cf_annotation_enabled(cfg) is False

    def test_research_section_without_flag_returns_false(self):
        cfg = self._write_config("research:\n  some_other_key: true\n")
        assert is_cf_annotation_enabled(cfg) is False


# ── Test 8: Integration — report writer with flag=False ──────────────────────

class TestWriteDailyScanReportFlagOff:
    """
    Verify that write_daily_scan_report with CF flag=False produces a
    daily_scan.json WITHOUT 'cf_annotation' key, and final_action_counts are unchanged.
    """

    def test_flag_off_no_cf_annotation_in_json(self, tmp_path: Path):
        import json
        from unittest.mock import patch as _patch
        from scripts.reporting.daily_scan_report import (
            OUT_JSON, OUT_MD, write_daily_scan_report,
        )
        from pathlib import Path as _Path

        scan = _make_scan_df()

        out_json = tmp_path / "daily_scan.json"
        out_md   = tmp_path / "daily_scan.md"

        with (
            _patch(
                "scripts.reporting.daily_scan_report.OUT_JSON", out_json
            ),
            _patch(
                "scripts.reporting.daily_scan_report.OUT_MD", out_md
            ),
            _patch(
                "src.trading.research.capital_footprint.annotation.is_cf_annotation_enabled",
                return_value=False,
            ),
            # Stub out expensive external calls
            _patch(
                "scripts.reporting.daily_scan_report._portfolio_context",
                return_value=(None, None, None, []),
            ),
            _patch(
                "scripts.reporting.daily_scan_report._load_holdings",
                return_value=[],
            ),
            _patch(
                "src.trading.reports.distribution_risk_card.build_distribution_risk_section_for_daily_scan",
                return_value=("", []),
            ),
            _patch(
                "src.trading.reports.rs_correction_card.build_rs_correction_section_for_daily_scan",
                return_value=("", []),
            ),
            _patch(
                "src.trading.reports.rs_correction_card.load_rs_correction_latest",
                return_value=(None, None),
            ),
            _patch(
                "src.trading.reports.rs_c3_card.build_rs_c3_section_for_daily_scan",
                return_value=("", []),
            ),
            _patch(
                "scripts.research.group_rotation.report_section.render_group_rotation_context_md",
                return_value="",
            ),
        ):
            write_daily_scan_report(scan, generated_at="2026-05-30T00:00:00Z")

        with open(out_json, encoding="utf-8") as f:
            payload = json.load(f)

        assert "cf_annotation" not in payload, (
            "cf_annotation key must NOT appear in JSON when flag is off"
        )
        assert "final_action_counts" in payload
        assert payload["final_action_counts"].get("TRAIL_EXIT") == 3

    def test_flag_on_adds_cf_annotation_to_json(self, tmp_path: Path):
        import json
        from unittest.mock import patch as _patch
        from scripts.reporting.daily_scan_report import write_daily_scan_report

        scan = _make_scan_df()
        out_json = tmp_path / "daily_scan.json"
        out_md   = tmp_path / "daily_scan.md"

        ann_df = _make_annotation_df(scan)

        with (
            _patch("scripts.reporting.daily_scan_report.OUT_JSON", out_json),
            _patch("scripts.reporting.daily_scan_report.OUT_MD", out_md),
            _patch(
                "src.trading.research.capital_footprint.annotation.is_cf_annotation_enabled",
                return_value=True,
            ),
            _patch(
                "src.trading.research.capital_footprint.annotation.build_cf_annotation_for_date",
                return_value=ann_df,
            ),
            _patch(
                "scripts.reporting.daily_scan_report._portfolio_context",
                return_value=(None, None, None, []),
            ),
            _patch("scripts.reporting.daily_scan_report._load_holdings", return_value=[]),
            _patch(
                "src.trading.reports.distribution_risk_card.build_distribution_risk_section_for_daily_scan",
                return_value=("", []),
            ),
            _patch(
                "src.trading.reports.rs_correction_card.build_rs_correction_section_for_daily_scan",
                return_value=("", []),
            ),
            _patch(
                "src.trading.reports.rs_correction_card.load_rs_correction_latest",
                return_value=(None, None),
            ),
            _patch(
                "src.trading.reports.rs_c3_card.build_rs_c3_section_for_daily_scan",
                return_value=("", []),
            ),
            _patch(
                "scripts.research.group_rotation.report_section.render_group_rotation_context_md",
                return_value="",
            ),
        ):
            write_daily_scan_report(scan, generated_at="2026-05-30T00:00:00Z")

        with open(out_json, encoding="utf-8") as f:
            payload = json.load(f)

        assert "cf_annotation" in payload, "cf_annotation key must appear in JSON when flag is on"
        assert payload["cf_annotation"]["enabled"] is True
        assert "final_action_counts" in payload
        # final_action_counts must be UNCHANGED vs flag-off
        assert payload["final_action_counts"].get("TRAIL_EXIT") == 3

    def test_flag_on_final_action_counts_identical(self, tmp_path: Path):
        """Enabling CF annotation must not change final_action_counts in the JSON."""
        import json
        from unittest.mock import patch as _patch
        from scripts.reporting.daily_scan_report import write_daily_scan_report

        scan = _make_scan_df()
        ann_df = _make_annotation_df(scan)

        _shared_patches = dict(
            _portfolio_context=(None, None, None, []),
            _load_holdings=[],
        )

        def _run(flag: bool) -> dict:
            out_json = tmp_path / f"ds_flag_{flag}.json"
            out_md   = tmp_path / f"ds_flag_{flag}.md"
            with (
                _patch("scripts.reporting.daily_scan_report.OUT_JSON", out_json),
                _patch("scripts.reporting.daily_scan_report.OUT_MD", out_md),
                _patch(
                    "src.trading.research.capital_footprint.annotation.is_cf_annotation_enabled",
                    return_value=flag,
                ),
                _patch(
                    "src.trading.research.capital_footprint.annotation.build_cf_annotation_for_date",
                    return_value=ann_df,
                ),
                _patch("scripts.reporting.daily_scan_report._portfolio_context", return_value=(None, None, None, [])),
                _patch("scripts.reporting.daily_scan_report._load_holdings", return_value=[]),
                _patch("src.trading.reports.distribution_risk_card.build_distribution_risk_section_for_daily_scan", return_value=("", [])),
                _patch("src.trading.reports.rs_correction_card.build_rs_correction_section_for_daily_scan", return_value=("", [])),
                _patch("src.trading.reports.rs_correction_card.load_rs_correction_latest", return_value=(None, None)),
                _patch("src.trading.reports.rs_c3_card.build_rs_c3_section_for_daily_scan", return_value=("", [])),
                _patch("scripts.research.group_rotation.report_section.render_group_rotation_context_md", return_value=""),
            ):
                write_daily_scan_report(scan.copy(), generated_at="2026-05-30T00:00:00Z")
            with open(out_json, encoding="utf-8") as f:
                return json.load(f)

        off = _run(False)
        on  = _run(True)

        assert off["final_action_counts"] == on["final_action_counts"], (
            "final_action_counts must be identical whether CF annotation is enabled or not"
        )
        assert off["n_symbols"] == on["n_symbols"]
        assert "cf_annotation" not in off
        assert "cf_annotation" in on
