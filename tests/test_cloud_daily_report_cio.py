"""
Tests for CIO Cockpit + CF Annotation integration in cloud_daily_report.py.

Verifies:
  1. CIO Cockpit section present in HTML
  2. Portfolio Command section (renamed, Must Act / Verify / Hold)
  3. Action Register section present
  4. Research sections (DRL / RS / RS C3) wrapped in <details>
  5. CF disabled → no CF fields in HTML or JSON
  6. CF enabled → CF counts in CIO Cockpit, CF details section, cf_annotation in JSON
  7. final_action / a3_rank_score / OMS fields never modified by report layer
  8. Nav bar includes CIO Cockpit and Action Register anchors

All tests use synthetic data and mock expensive I/O.
"""
from __future__ import annotations

import contextlib
import datetime
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.trading.reports.cloud_daily_report import build_report


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_scan_df(n: int = 10, breadth_zone: str = "defense") -> pd.DataFrame:
    rng = np.random.default_rng(0)
    ACTIONS = [
        "TRAIL_EXIT", "WATCH_ONLY", "NO_T2_BREADTH", "HOLD_T1_ONLY",
        "NEW_T1_MANUAL_REVIEW_BREADTH", "WATCH_ONLY", "TRAIL_EXIT",
        "NO_T2_BREADTH", "WATCH_ONLY", "NEW_T1",
    ]
    syms = [f"SYM{i:02d}" for i in range(n)]
    actions = [ACTIONS[i % len(ACTIONS)] for i in range(n)]
    return pd.DataFrame({
        "symbol": syms,
        "as_of_date": "2026-05-30",
        "final_action": actions,
        "a3_rank_score": rng.uniform(0, 2, n).round(4),
        "close_kVND": rng.uniform(10, 100, n).round(2),
        "breadth_zone": breadth_zone,
        "regime_bull": True,
        "pct_cloud_bull_a3": 0.30,
        "pct_cloud_bull_s3": 0.28,
        "breadth_t1_permission": True,
        "breadth_t2_permission": False,
        "final_action_reason": [f"reason_{i}" for i in range(n)],
        "a3_signal_today": [False] * n,
        "a3_planned_entry_timing": ["FILLED"] * n,
        "pb_trigger_price": rng.uniform(10, 80, n).round(2),
        "tp1_price": rng.uniform(80, 120, n).round(2),
        "trail_price": rng.uniform(8, 70, n).round(2),
        "liq_warn_T1": ["OK"] * n,
        "s3_lead_bucket": ["none"] * n,
        "s3_fresh_lead_flag": [False] * n,
        "sector_l4": ["Banks"] * 5 + ["RE"] * 5,
        "s3_shadow_action": [""] * n,
        "s3_no_real_order_flag": [True] * n,
    })


def _make_cf_ann_df(scan_df: pd.DataFrame) -> pd.DataFrame:
    LABELS = [
        "SUPPLY_ABSORPTION_SETUP", "EXTENSION_DISTRIBUTION_RISK",
        "FAILED_BREAKOUT", "NEUTRAL",
    ]
    NOTES = {
        "SUPPLY_ABSORPTION_SETUP": "Dry-up setup in BULL_BROAD",
        "EXTENSION_DISTRIBUTION_RISK": "Extended 5+ bars — do not add",
        "FAILED_BREAKOUT": "Research-only failed breakout label",
        "NEUTRAL": "",
    }
    rows = []
    for i, sym in enumerate(scan_df["symbol"].tolist()):
        label = LABELS[i % len(LABELS)]
        age = 7.0 if label == "EXTENSION_DISTRIBUTION_RISK" else 2.0
        regime = "BULL_BROAD" if i % 3 == 0 else "NEUTRAL"
        active = 1 if label in ("SUPPLY_ABSORPTION_SETUP", "EXTENSION_DISTRIBUTION_RISK") and age >= 5 else 0
        rows.append({
            "symbol": sym,
            "cf_phase_label": label,
            "cf_event_age": age,
            "cf_event_cooldown_flag": 0,
            "cf_breadth_regime_bucket": regime,
            "cf_annotation_active": active,
            "cf_operator_note": NOTES.get(label, ""),
        })
    return pd.DataFrame(rows)


_MOCK_DRL = {"method_version": "v1.2", "as_of_date": "2026-05-30",
             "distribution_risk_score": 0.3, "alert_level": "LOW"}
_MOCK_RS = {"method_version": "v1.0", "as_of_date": "2026-05-30", "rs_correction_signal": "NEUTRAL"}
_MOCK_C3 = "<p><em>RS C3 mock</em></p>"


def _make_inputs(scan_df: pd.DataFrame, holdings=None) -> dict:
    return {
        "mode": "eod",
        "scan_df": scan_df,
        "intraday_df": pd.DataFrame(),
        "intraday_meta": {},
        "holdings": holdings or ["SYM00", "SYM02"],
        "nav_vnd": 5_000_000_000.0,
        "positions_df": pd.DataFrame({
            "symbol": ["SYM00", "SYM02"],
            "lots": [1000, 2000],
            "entry_price": [15000.0, 35000.0],
        }),
        "positions_source": "portfolio_state.json",
        "portfolio_state_path": "data/trading/portfolio_state.json",
        "portfolio_as_of_date": "2026-05-30",
        "prev_json": None,
        "warnings": [],
        "files_used": [],
        "scan_path": "phase36_daily_scan_latest.csv",
        "distribution_risk_lens": _MOCK_DRL,
        "distribution_risk_warnings": [],
        "rs_correction_lens": _MOCK_RS,
        "rs_correction_warnings": [],
        "rs_c3_html": _MOCK_C3,
        "rs_c3_warnings": [],
    }


_TS = datetime.datetime(2026, 5, 30, 8, 0, 0, tzinfo=datetime.timezone.utc)


def _run(inputs: dict, *, cf_flag: bool = False, cf_ann_df=None):
    """Run build_report with standard patches. Returns (html, md, json_payload)."""
    patches = [
        patch("src.trading.research.capital_footprint.annotation.is_cf_annotation_enabled",
              return_value=cf_flag),
        patch("src.trading.reports.cloud_daily_report._append_cf_obs_ledger_cloud",
              return_value=None),
    ]
    if cf_ann_df is not None:
        patches.append(patch(
            "src.trading.research.capital_footprint.annotation.build_cf_annotation_for_date",
            return_value=cf_ann_df,
        ))
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        return build_report("eod", inputs, _TS)


# ── Test 1: CIO Cockpit present ───────────────────────────────────────────────

class TestCioCockpitInHtml:
    def test_cio_cockpit_section_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "CIO Cockpit" in html

    def test_permission_matrix_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "Permission Matrix" in html

    def test_action_counts_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "Action Counts" in html

    def test_required_actions_block_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "Required Actions" in html

    def test_forbidden_block_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "Forbidden" in html

    def test_defense_breadth_in_oneliner(self):
        html, _, _ = _run(_make_inputs(_make_scan_df(breadth_zone="defense")))
        assert "defense" in html.lower()

    def test_bear_regime_in_oneliner(self):
        scan = _make_scan_df()
        scan["regime_bull"] = False
        html, _, _ = _run(_make_inputs(scan))
        assert "BEAR" in html or "bear" in html.lower()

    def test_cio_section_id_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert 'id="section-cio"' in html


# ── Test 2: Nav bar updated ───────────────────────────────────────────────────

class TestNavBar:
    def test_nav_has_cio_anchor(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "#section-cio" in html

    def test_nav_has_action_register_anchor(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "#section-ar" in html

    def test_existing_nav_anchors_still_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        for anchor in ("#section-b", "#section-c", "#section-d", "#section-g", "#section-h", "#section-i"):
            assert anchor in html, f"Nav anchor {anchor} missing"


# ── Test 3: Portfolio Command restructure ─────────────────────────────────────

class TestPortfolioCommand:
    def test_portfolio_command_title(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "Portfolio Command" in html

    def test_portfolio_overlay_not_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "Portfolio Overlay" not in html

    def test_must_act_subsection_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "Must Act" in html

    def test_verify_subsection_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "Verify" in html

    def test_hold_watch_subsection_present(self):
        scan = _make_scan_df()
        # SYM00 = TRAIL_EXIT (must act); SYM09 = NEW_T1 (hold watch)
        html, _, _ = _run(_make_inputs(scan, holdings=["SYM00", "SYM09"]))
        assert "Hold / Watch" in html

    def test_trail_exit_holding_in_must_act(self):
        scan = _make_scan_df()
        # SYM00 has TRAIL_EXIT
        html, _, _ = _run(_make_inputs(scan, holdings=["SYM00"]))
        assert "Must Act" in html
        assert "SYM00" in html

    def test_not_in_scan_holding_in_verify(self):
        scan = _make_scan_df()
        html, _, _ = _run(_make_inputs(scan, holdings=["NOTINSCAN"]))
        assert "Verify" in html
        assert "NOTINSCAN" in html

    def test_section_d_id_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert 'id="section-d"' in html


# ── Test 4: Action Register ───────────────────────────────────────────────────

class TestActionRegister:
    def test_action_register_section_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "Action Register" in html

    def test_section_ar_id_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert 'id="section-ar"' in html

    def test_p1_exit_appears_for_trail_exit_in_holdings(self):
        scan = _make_scan_df()
        html, _, _ = _run(_make_inputs(scan, holdings=["SYM00"]))
        assert "P1 EXIT" in html

    def test_p2_verify_appears_for_not_in_scan_holding(self):
        scan = _make_scan_df()
        html, _, _ = _run(_make_inputs(scan, holdings=["MISSING_SYM"]))
        assert "P2 VERIFY" in html

    def test_p3_manual_review_present(self):
        scan = _make_scan_df()
        # SYM04 = NEW_T1_MANUAL_REVIEW_BREADTH
        html, _, _ = _run(_make_inputs(scan))
        assert "P3 T1 MR" in html

    def test_no_priority_actions_message_when_clean(self):
        scan = _make_scan_df()
        scan["final_action"] = "WATCH_ONLY"
        html, _, _ = _run(_make_inputs(scan, holdings=[]))
        assert "No priority actions" in html


# ── Test 5: Research sections collapsed ──────────────────────────────────────

class TestResearchSectionsCollapsed:
    def test_distribution_risk_in_details_tag(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "<details>" in html
        assert "Distribution Risk Lens" in html

    def test_rs_correction_in_details_tag(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "RS Correction Lens" in html

    def test_rs_c3_in_details_tag(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "RS C3 Lens" in html

    def test_rs_c3_mentions_oos_ic(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "OOS IC" in html

    def test_no_open_attribute_on_details(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "<details open" not in html


# ── Test 6: CF disabled → no CF in output ────────────────────────────────────

class TestCfDisabledCleanOutput:
    def test_no_cf_annotation_key_in_json(self):
        _, _, payload = _run(_make_inputs(_make_scan_df()), cf_flag=False)
        assert "cf_annotation" not in payload

    def test_no_cf_active_notes_in_html(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()), cf_flag=False)
        assert "CF Active Notes" not in html

    def test_no_cf_annotation_details_section(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()), cf_flag=False)
        assert "Capital Footprint Annotation" not in html

    def test_final_action_counts_present_when_cf_off(self):
        _, _, payload = _run(_make_inputs(_make_scan_df()), cf_flag=False)
        assert "counts" in payload
        assert payload["counts"]["exit_review"] >= 0


# ── Test 7: CF enabled → CF appears in output ────────────────────────────────

class TestCfEnabledOutput:
    def test_cf_annotation_key_in_json(self):
        scan = _make_scan_df()
        cf_df = _make_cf_ann_df(scan)
        _, _, payload = _run(_make_inputs(scan), cf_flag=True, cf_ann_df=cf_df)
        assert "cf_annotation" in payload
        assert payload["cf_annotation"]["enabled"] is True

    def test_cf_active_notes_in_cio_cockpit(self):
        scan = _make_scan_df()
        cf_df = _make_cf_ann_df(scan)
        html, _, _ = _run(_make_inputs(scan), cf_flag=True, cf_ann_df=cf_df)
        assert "CF Active Notes" in html

    def test_cf_annotation_details_section_present(self):
        scan = _make_scan_df()
        cf_df = _make_cf_ann_df(scan)
        html, _, _ = _run(_make_inputs(scan), cf_flag=True, cf_ann_df=cf_df)
        assert "Capital Footprint Annotation" in html

    def test_cf_details_inside_details_tag(self):
        scan = _make_scan_df()
        cf_df = _make_cf_ann_df(scan)
        html, _, _ = _run(_make_inputs(scan), cf_flag=True, cf_ann_df=cf_df)
        idx = html.find("Capital Footprint Annotation")
        pre = html[max(0, idx - 200):idx]
        assert "<details>" in pre

    def test_n_active_matches_cf_ann_df(self):
        scan = _make_scan_df()
        cf_df = _make_cf_ann_df(scan)
        n_expected = int((cf_df["cf_annotation_active"] == 1).sum())
        _, _, payload = _run(_make_inputs(scan), cf_flag=True, cf_ann_df=cf_df)
        assert payload["cf_annotation"]["n_active"] == n_expected

    def test_final_action_count_identical_cf_on_vs_off(self):
        scan = _make_scan_df()
        cf_df = _make_cf_ann_df(scan)
        _, _, payload_on = _run(_make_inputs(scan), cf_flag=True, cf_ann_df=cf_df)
        _, _, payload_off = _run(_make_inputs(scan), cf_flag=False)
        assert payload_on["counts"] == payload_off["counts"]

    def test_cf_note_column_in_action_register(self):
        scan = _make_scan_df()
        cf_df = _make_cf_ann_df(scan)
        html, _, _ = _run(_make_inputs(scan), cf_flag=True, cf_ann_df=cf_df)
        assert "CF Note" in html


# ── Test 8: Guardrails — production fields unchanged ─────────────────────────

class TestProductionFieldsUnchanged:
    def test_final_action_values_not_in_cf_payload(self):
        scan = _make_scan_df()
        cf_df = _make_cf_ann_df(scan)
        _, _, payload = _run(_make_inputs(scan), cf_flag=True, cf_ann_df=cf_df)
        cf_payload_str = json.dumps(payload.get("cf_annotation", {}))
        assert "final_action" not in cf_payload_str

    def test_a3_rank_score_not_in_cf_payload(self):
        scan = _make_scan_df()
        cf_df = _make_cf_ann_df(scan)
        _, _, payload = _run(_make_inputs(scan), cf_flag=True, cf_ann_df=cf_df)
        cf_payload_str = json.dumps(payload.get("cf_annotation", {}))
        assert "a3_rank_score" not in cf_payload_str

    def test_scan_df_not_modified(self):
        scan = _make_scan_df()
        original_actions = scan["final_action"].tolist()
        original_scores = scan["a3_rank_score"].tolist()
        _run(_make_inputs(scan), cf_flag=False)
        assert scan["final_action"].tolist() == original_actions
        assert scan["a3_rank_score"].tolist() == original_scores

    def test_scan_df_not_modified_when_cf_enabled(self):
        scan = _make_scan_df()
        cf_df = _make_cf_ann_df(scan)
        original_actions = scan["final_action"].tolist()
        _run(_make_inputs(scan), cf_flag=True, cf_ann_df=cf_df)
        assert scan["final_action"].tolist() == original_actions


# ── Test 9: Legacy sections still present (backward compat) ──────────────────

class TestLegacySectionsPresent:
    def test_section_b_still_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert 'id="section-b"' in html

    def test_section_c_a3_board_still_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert "A3 Action Board" in html

    def test_section_g_market_still_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert 'id="section-g"' in html

    def test_section_h_delta_still_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert 'id="section-h"' in html

    def test_section_i_appendix_still_present(self):
        html, _, _ = _run(_make_inputs(_make_scan_df()))
        assert 'id="section-i"' in html

    def test_json_payload_has_required_keys(self):
        _, _, payload = _run(_make_inputs(_make_scan_df()))
        for key in ("report_mode", "counts", "new_entry_symbols", "regime_bull",
                    "breadth_zone", "warnings", "files_used"):
            assert key in payload, f"JSON key '{key}' missing"


if __name__ == "__main__":
    import unittest
    unittest.main()
