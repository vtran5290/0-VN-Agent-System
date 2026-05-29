"""Output inventory mapping dashboard sections A–J to testable/display-only fields.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import pandas as pd

from .schema import RESEARCH_ONLY_LABEL

# Output type constants
TESTABLE_RETURN = "TESTABLE_RETURN"
TESTABLE_RISK = "TESTABLE_RISK"
WORKFLOW = "WORKFLOW"
DISPLAY_ONLY = "DISPLAY_ONLY"
CONTEXT_ONLY = "CONTEXT_ONLY"

_INVENTORY_ROWS: list[dict] = [
    # ── Section A: Header / Mode / NAV / Regime ───────────────────────────────
    {"section": "A", "section_name": "Header/Mode/NAV/Regime", "output_field": "regime_bull", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Risk control field; forward study blocked by insufficient scan history"},
    {"section": "A", "section_name": "Header/Mode/NAV/Regime", "output_field": "breadth_zone", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Risk control field; forward study blocked by insufficient scan history"},
    {"section": "A", "section_name": "Header/Mode/NAV/Regime", "output_field": "breadth_t1_permission", "output_type": TESTABLE_RISK, "test_available": False, "notes": "T1 gate; risk control; blocked by data"},
    {"section": "A", "section_name": "Header/Mode/NAV/Regime", "output_field": "breadth_t2_permission", "output_type": TESTABLE_RISK, "test_available": False, "notes": "T2 gate; risk control; blocked by data"},
    {"section": "A", "section_name": "Header/Mode/NAV/Regime", "output_field": "mode", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "Informational display; not a trading signal"},
    {"section": "A", "section_name": "Header/Mode/NAV/Regime", "output_field": "NAV", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "Portfolio NAV display"},
    {"section": "A", "section_name": "Header/Mode/NAV/Regime", "output_field": "as_of_date", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "Date display"},
    # ── Section B: Decision Summary ────────────────────────────────────────────
    {"section": "B", "section_name": "Decision Summary", "output_field": "ACTION_NOW_list", "output_type": WORKFLOW, "test_available": False, "notes": "Workflow summary of final_action; not independently testable"},
    {"section": "B", "section_name": "Decision Summary", "output_field": "WATCH_list", "output_type": WORKFLOW, "test_available": False, "notes": "Workflow watchlist"},
    {"section": "B", "section_name": "Decision Summary", "output_field": "DO_NOT_DO_list", "output_type": WORKFLOW, "test_available": False, "notes": "Workflow do-not-do list"},
    {"section": "B", "section_name": "Decision Summary", "output_field": "final_action_ssot_message", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "SSOT messaging is display-only"},
    # ── Section C: A3 Action Board ─────────────────────────────────────────────
    {"section": "C", "section_name": "A3 Action Board", "output_field": "NEW_T1", "output_type": TESTABLE_RETURN, "test_available": False, "notes": "Entry signal; event study blocked by N<5 in 1wk scan history"},
    {"section": "C", "section_name": "A3 Action Board", "output_field": "NEW_T1_MANUAL_REVIEW_BREADTH", "output_type": TESTABLE_RETURN, "test_available": False, "notes": "Entry signal with breadth caution; event study blocked"},
    {"section": "C", "section_name": "A3 Action Board", "output_field": "ADD_T2", "output_type": TESTABLE_RETURN, "test_available": False, "notes": "Add signal; event study blocked"},
    {"section": "C", "section_name": "A3 Action Board", "output_field": "NO_T2_BREADTH", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Risk control gate; blocked by data"},
    {"section": "C", "section_name": "A3 Action Board", "output_field": "WAIT_PB", "output_type": TESTABLE_RETURN, "test_available": False, "notes": "Pullback wait; blocked by data"},
    {"section": "C", "section_name": "A3 Action Board", "output_field": "TRAIL_EXIT", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Trail exit signal; exit logic not tested"},
    {"section": "C", "section_name": "A3 Action Board", "output_field": "TP1_PARTIAL", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Partial exit; blocked by data"},
    {"section": "C", "section_name": "A3 Action Board", "output_field": "HOLD_T1", "output_type": WORKFLOW, "test_available": False, "notes": "Holding instruction; workflow only"},
    {"section": "C", "section_name": "A3 Action Board", "output_field": "WATCH_ONLY", "output_type": WORKFLOW, "test_available": False, "notes": "Watchlist; workflow only"},
    {"section": "C", "section_name": "A3 Action Board", "output_field": "a3_rank_score", "output_type": TESTABLE_RETURN, "test_available": False, "notes": "Rank signal predictiveness; blocked by N<5"},
    {"section": "C", "section_name": "A3 Action Board", "output_field": "s3_lead_bucket", "output_type": WORKFLOW, "test_available": False, "notes": "S3 context display; workflow only"},
    # ── Section D: Portfolio Overlay ────────────────────────────────────────────
    {"section": "D", "section_name": "Portfolio Overlay", "output_field": "in_scan_check", "output_type": WORKFLOW, "test_available": False, "notes": "Holdings in scan consistency check"},
    {"section": "D", "section_name": "Portfolio Overlay", "output_field": "VERIFY", "output_type": WORKFLOW, "test_available": False, "notes": "Data verification workflow"},
    {"section": "D", "section_name": "Portfolio Overlay", "output_field": "TAKE_PARTIAL", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Blocked by data — no historical position snapshots"},
    {"section": "D", "section_name": "Portfolio Overlay", "output_field": "REVIEW_TRAIL_EXIT", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Blocked by data"},
    {"section": "D", "section_name": "Portfolio Overlay", "output_field": "ADD_BLOCKED_BY_BREADTH", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Breadth gate on held positions; blocked by data"},
    {"section": "D", "section_name": "Portfolio Overlay", "output_field": "PAPER_ONLY", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "Paper mode display"},
    {"section": "D", "section_name": "Portfolio Overlay", "output_field": "overlay_WATCH_ONLY", "output_type": WORKFLOW, "test_available": False, "notes": "Workflow watchlist"},
    # ── Section E: S3 Radar ──────────────────────────────────────────────────────
    {"section": "E", "section_name": "S3 Radar", "output_field": "s3_shadow_action", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "Paper-shadow only by design; s3_no_real_order_flag enforced"},
    {"section": "E", "section_name": "S3 Radar", "output_field": "s3_fresh_lead_flag", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "Paper-shadow context display"},
    {"section": "E", "section_name": "S3 Radar", "output_field": "gk5", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "GK5 paper display"},
    {"section": "E", "section_name": "S3 Radar", "output_field": "gk10", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "GK10 paper display"},
    {"section": "E", "section_name": "S3 Radar", "output_field": "s3_active", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "S3 status display only"},
    # ── Section F: Market/Breadth/Risk ──────────────────────────────────────────
    {"section": "F", "section_name": "Market/Breadth/Risk", "output_field": "VNINDEX_regime", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Regime risk control; forward study blocked"},
    {"section": "F", "section_name": "Market/Breadth/Risk", "output_field": "breadth_pct", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Breadth pct event study not run; blocked"},
    {"section": "F", "section_name": "Market/Breadth/Risk", "output_field": "distribution_risk", "output_type": TESTABLE_RISK, "test_available": True, "notes": "PARTIALLY_VALIDATED — vnindex_low_dist_forward_returns.json exists"},
    {"section": "F", "section_name": "Market/Breadth/Risk", "output_field": "ex_vin_proxy", "output_type": TESTABLE_RISK, "test_available": False, "notes": "ex-VIN series exists but forward event study not run"},
    {"section": "F", "section_name": "Market/Breadth/Risk", "output_field": "VIN_warning", "output_type": CONTEXT_ONLY, "test_available": False, "notes": "VIN return distortion context; caveat display"},
    # ── Section G: RS Correction ─────────────────────────────────────────────────
    {"section": "G", "section_name": "RS Correction", "output_field": "RS_leaders", "output_type": TESTABLE_RETURN, "test_available": True, "notes": "PARTIALLY_VALIDATED — rs_vs_vnindex_correction CSV exists"},
    {"section": "G", "section_name": "RS Correction", "output_field": "RS_defensive", "output_type": TESTABLE_RISK, "test_available": False, "notes": "Defensive bucket not separately validated"},
    {"section": "G", "section_name": "RS Correction", "output_field": "weakest_RS", "output_type": TESTABLE_RETURN, "test_available": False, "notes": "Weakest RS forward study not run"},
    {"section": "G", "section_name": "RS Correction", "output_field": "RS20_delta", "output_type": TESTABLE_RETURN, "test_available": False, "notes": "RS20 delta momentum; not yet tested"},
    # ── Section H: RS C3 ─────────────────────────────────────────────────────────
    {"section": "H", "section_name": "RS C3", "output_field": "C3_rating", "output_type": CONTEXT_ONLY, "test_available": False, "notes": "Review-ranking only per prior OOS IC analysis; IC near zero in 2024+"},
    {"section": "H", "section_name": "RS C3", "output_field": "EXTREME_RS", "output_type": CONTEXT_ONLY, "test_available": False, "notes": "IC near zero in OOS 2024+; context only"},
    # ── Section I: Delta ──────────────────────────────────────────────────────────
    {"section": "I", "section_name": "Delta", "output_field": "action_changes_since_yesterday", "output_type": WORKFLOW, "test_available": False, "notes": "Change tracking workflow; not independently testable"},
    {"section": "I", "section_name": "Delta", "output_field": "new_entries_delta", "output_type": WORKFLOW, "test_available": False, "notes": "Delta display"},
    {"section": "I", "section_name": "Delta", "output_field": "exits_delta", "output_type": WORKFLOW, "test_available": False, "notes": "Delta display"},
    # ── Section J: Appendix ───────────────────────────────────────────────────────
    {"section": "J", "section_name": "Appendix", "output_field": "full_scan_table", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "Full scan data appendix display"},
    {"section": "J", "section_name": "Appendix", "output_field": "schema_version", "output_type": DISPLAY_ONLY, "test_available": False, "notes": "Schema version display"},
]


def build_output_inventory() -> pd.DataFrame:
    """Build and return the output inventory DataFrame.

    Returns DataFrame with columns:
    section, section_name, output_field, output_type, test_available, notes
    """
    df = pd.DataFrame(_INVENTORY_ROWS)
    df["research_label"] = RESEARCH_ONLY_LABEL
    return df
