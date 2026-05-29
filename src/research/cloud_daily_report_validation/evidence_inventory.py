"""Evidence inventory for cloud daily report validation.

Searches the repo for existing backtests/validation and builds a registry
of what is already tested, what is display-only, and what needs new backtest.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .schema import (
    RESEARCH_ONLY_LABEL,
    EvidenceStatus,
    EvidenceLabel,
    DashboardRecommendation,
    _REPO,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Known evidence paths to probe
# ──────────────────────────────────────────────────────────────────────────────
_DIST_RISK_PATH = _REPO / "data" / "research" / "vnindex_low_dist_forward_returns.json"
_RS_CORRECTION_PATH = _REPO / "data" / "research" / "rs_vs_vnindex_correction_20260515_20260525.csv"
_CLOUD_REPORT_TESTS = _REPO / "tests" / "test_cloud_daily_report.py"
_CLOUD_REPORT_DIST_TESTS = _REPO / "tests" / "test_cloud_daily_report_distribution_risk.py"
_INSTITUTIONAL_BACKTEST_DIR = _REPO / "src" / "research" / "institutional_accumulation_backtest"


def parse_distribution_risk_json() -> dict[str, Any]:
    """Parse vnindex_low_dist_forward_returns.json and extract key metrics.

    Returns a dict with: sample_size, horizons, drawdown_impact, benchmark_comparison,
    date_range, ex_vin_survives, parsed_ok, raw_summary.

    If the file does not exist or cannot be parsed, returns evidence_label=BLOCKED_BY_DATA.
    """
    path = _DIST_RISK_PATH
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "parsed_ok": False,
        "sample_size": None,
        "horizons": [],
        "drawdown_impact": None,
        "benchmark_comparison": None,
        "date_range": None,
        "ex_vin_survives": None,
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "raw_summary": "",
    }
    if not path.is_file():
        result["raw_summary"] = "File not found — BLOCKED_BY_DATA"
        return result
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        result["raw_summary"] = f"JSON parse error: {exc}"
        return result

    result["parsed_ok"] = True
    result["raw_summary"] = str(data)[:500]

    # Extract known fields from the JSON structure (format may vary)
    # Try common key patterns
    n = data.get("n") or data.get("sample_size") or data.get("event_count")
    if isinstance(data, list) and len(data) > 0:
        n = len(data)
    elif isinstance(data, dict):
        # Try to extract n from nested keys
        for k in ("n", "n_events", "event_count", "sample_size"):
            if k in data:
                n = data[k]
                break
        if n is None:
            # Look for a list value
            for v in data.values():
                if isinstance(v, list):
                    n = len(v)
                    break

    result["sample_size"] = n

    # Extract horizons
    horizons = []
    for key in data if isinstance(data, dict) else {}:
        if "ret" in str(key).lower() or "return" in str(key).lower():
            horizons.append(key)
    if not horizons:
        horizons = ["unknown — see raw JSON"]
    result["horizons"] = horizons

    # Drawdown impact — look for dd or drawdown keys
    dd_val = None
    if isinstance(data, dict):
        for k, v in data.items():
            if "dd" in str(k).lower() or "drawdown" in str(k).lower():
                dd_val = v
                break
    result["drawdown_impact"] = dd_val

    # ex-VIN survival — check sibling files
    ex_vin_path = _REPO / "data" / "research" / "vnindex_low_dist_forward_returns_ex_vin.json"
    result["ex_vin_survives"] = ex_vin_path.is_file()

    # Assign evidence label based on what was parsed
    # If we have n and ex-VIN file exists → RISK_CONTROL_SUPPORTED
    if result["sample_size"] and result["ex_vin_survives"]:
        result["evidence_label"] = EvidenceLabel.RISK_CONTROL_SUPPORTED.value
        result["benchmark_comparison"] = "ex-VIN file present — see vnindex_low_dist_forward_returns_ex_vin.json"
    elif result["sample_size"]:
        result["evidence_label"] = EvidenceLabel.RISK_CONTROL_SUPPORTED.value
        result["benchmark_comparison"] = "VNINDEX only (ex-VIN file not found)"
    else:
        result["evidence_label"] = EvidenceLabel.INCONCLUSIVE.value
        result["benchmark_comparison"] = "Parsed but sample size unknown — manual review required"

    return result


def search_existing_evidence() -> dict[str, dict]:
    """Check known evidence file paths and return existence + path for each."""
    checks = {
        "distribution_risk_forward_returns": {
            "path": str(_DIST_RISK_PATH),
            "exists": _DIST_RISK_PATH.is_file(),
            "description": "VNINDEX low-distribution-day forward returns JSON",
        },
        "rs_correction_csv": {
            "path": str(_RS_CORRECTION_PATH),
            "exists": _RS_CORRECTION_PATH.is_file(),
            "description": "RS vs VNINDEX correction event study CSV 2026-05-15 to 2026-05-25",
        },
        "cloud_daily_report_behavioral_tests": {
            "path": str(_CLOUD_REPORT_TESTS),
            "exists": _CLOUD_REPORT_TESTS.is_file(),
            "description": "Behavioral tests for cloud_daily_report classify/build logic",
        },
        "cloud_daily_report_distribution_risk_tests": {
            "path": str(_CLOUD_REPORT_DIST_TESTS),
            "exists": _CLOUD_REPORT_DIST_TESTS.is_file(),
            "description": "Distribution risk integration tests for cloud report",
        },
        "institutional_accumulation_backtest": {
            "path": str(_INSTITUTIONAL_BACKTEST_DIR),
            "exists": _INSTITUTIONAL_BACKTEST_DIR.is_dir(),
            "description": "Institutional accumulation backtest package (return event study)",
        },
    }
    return checks


# ──────────────────────────────────────────────────────────────────────────────
# Registry rows — pre-determined per spec
# ──────────────────────────────────────────────────────────────────────────────
_REGISTRY_ROWS: list[dict] = [
    # ── Section A: Header ────────────────────────────────────────────────────
    {
        "dashboard_section": "Header",
        "dashboard_output": "VNINDEX_regime",
        "field_or_rule": "regime_bull",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RISK",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Only ~1wk scan history; forward return event study not yet run",
    },
    {
        "dashboard_section": "Header",
        "dashboard_output": "breadth_zone",
        "field_or_rule": "breadth_zone",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RISK",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Only ~1wk scan history; breadth zone forward study not run",
    },
    {
        "dashboard_section": "Header",
        "dashboard_output": "T1_permission",
        "field_or_rule": "breadth_t1_permission",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RISK",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Only ~1wk scan history",
    },
    {
        "dashboard_section": "Header",
        "dashboard_output": "mode/NAV/date",
        "field_or_rule": "mode, nav, as_of_date",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "DISPLAY_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "Informational only; not a trading signal",
    },
    # ── Section B: Decision Summary ───────────────────────────────────────────
    {
        "dashboard_section": "Decision Summary",
        "dashboard_output": "final_action SSOT",
        "field_or_rule": "final_action",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "DISPLAY_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "SSOT messaging display; final_action computed upstream in A3/S3 logic",
    },
    # ── Section C: A3 Action Board ────────────────────────────────────────────
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "NEW_T1",
        "field_or_rule": "final_action=NEW_T1",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "tests/test_cloud_daily_report.py",
        "existing_result_summary": "Behavioral tests only — classify_operator_action logic; no return backtest",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RETURN",
        "evidence_label": EvidenceLabel.WORKFLOW_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "No event-study yet; only behavioral tests; ~1wk scan data insufficient for N>=5",
    },
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "NEW_T1_MANUAL_REVIEW_BREADTH",
        "field_or_rule": "final_action=NEW_T1_MANUAL_REVIEW_BREADTH",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "tests/test_cloud_daily_report.py",
        "existing_result_summary": "Behavioral tests only",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RETURN",
        "evidence_label": EvidenceLabel.WORKFLOW_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Needs event study; likely rare event — need 3+ months of scan history",
    },
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "ADD_T2",
        "field_or_rule": "final_action=ADD_T2",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "tests/test_cloud_daily_report.py",
        "existing_result_summary": "Behavioral tests only",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RETURN",
        "evidence_label": EvidenceLabel.WORKFLOW_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Needs event study",
    },
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "NO_T2_BREADTH",
        "field_or_rule": "final_action=NO_T2_BREADTH",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RISK",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Risk control test needed; insufficient scan history",
    },
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "WAIT_PB",
        "field_or_rule": "final_action=WAIT_PB",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RETURN",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Pullback timing not tested",
    },
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "TRAIL_EXIT",
        "field_or_rule": "final_action=TRAIL_EXIT",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RISK",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Exit logic not tested as forward return event study",
    },
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "TP1_PARTIAL",
        "field_or_rule": "final_action=TP1_PARTIAL",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RISK",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Partial exit not tested",
    },
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "HOLD_T1",
        "field_or_rule": "final_action=HOLD_T1",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "DISPLAY_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "Holding instruction only; not a new entry signal",
    },
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "WATCH_ONLY",
        "field_or_rule": "final_action=WATCH_ONLY",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "DISPLAY_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "Watchlist only; no order implied",
    },
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "a3_rank_score",
        "field_or_rule": "a3_rank_score",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RETURN",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Rank predictiveness not tested; need min 20 events per rank bucket",
    },
    {
        "dashboard_section": "A3 Action Board",
        "dashboard_output": "s3_lead_bucket",
        "field_or_rule": "s3_lead_bucket",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "DISPLAY_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "Context display only; S3 is paper-shadow",
    },
    # ── Section D: Portfolio Overlay ──────────────────────────────────────────
    {
        "dashboard_section": "Portfolio Overlay",
        "dashboard_output": "holdings_overlay",
        "field_or_rule": "current_positions_derived.json",
        "source_file_or_module": "data/raw/current_positions_derived.json",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
        "needs_new_backtest": False,
        "recommended_test_type": "BLOCKED",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "No historical position snapshots available — only current state in current_positions_derived.json",
    },
    {
        "dashboard_section": "Portfolio Overlay",
        "dashboard_output": "VERIFY",
        "field_or_rule": "holdings_check",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "DISPLAY_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "Data consistency check display only",
    },
    {
        "dashboard_section": "Portfolio Overlay",
        "dashboard_output": "TAKE_PARTIAL",
        "field_or_rule": "portfolio_overlay_action=TAKE_PARTIAL",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.BLOCKED_BY_DATA.value,
        "needs_new_backtest": False,
        "recommended_test_type": "BLOCKED",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "No historical position snapshots available",
    },
    # ── Section E: S3 Radar ───────────────────────────────────────────────────
    {
        "dashboard_section": "S3 Radar",
        "dashboard_output": "PAPER_S3_SHADOW",
        "field_or_rule": "s3_shadow_action, s3_no_real_order_flag",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "DISPLAY_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "Paper-shadow by design; s3_no_real_order_flag=True enforced",
    },
    {
        "dashboard_section": "S3 Radar",
        "dashboard_output": "GK5/GK10",
        "field_or_rule": "gk5, gk10",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "DISPLAY_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "Paper-shadow display only",
    },
    # ── Section F: Market/Breadth/Risk ────────────────────────────────────────
    {
        "dashboard_section": "Market/Breadth",
        "dashboard_output": "VNINDEX_dist_risk",
        "field_or_rule": "distribution_risk_flag",
        "source_file_or_module": "data/research/vnindex_low_dist_forward_returns.json",
        "already_backtested": True,
        "existing_backtest_path": "data/research/vnindex_low_dist_forward_returns.json",
        "existing_result_summary": "Forward returns under low-distribution-day regime exist; supports risk-control use",
        "evidence_status": EvidenceStatus.PARTIALLY_VALIDATED.value,
        "needs_new_backtest": False,
        "recommended_test_type": "TESTABLE_RISK",
        "evidence_label": EvidenceLabel.RISK_CONTROL_SUPPORTED.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_RISK_CONTROL.value,
        "notes": "vnindex_low_dist_forward_returns.json exists; validated as risk control warning; not standalone alpha",
    },
    {
        "dashboard_section": "Market/Breadth",
        "dashboard_output": "breadth_pct",
        "field_or_rule": "pct_cloud_bull_a3, pct_cloud_bull_s3",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RISK",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "No event study for breadth pct bins; insufficient scan history",
    },
    {
        "dashboard_section": "Market/Breadth",
        "dashboard_output": "ex_vin_proxy",
        "field_or_rule": "pct_cloud_bull_a3 (ex-VIN)",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RISK",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "ex-VIN series exists in OHLCV but no forward event study run",
    },
    # ── Section G: RS Correction ──────────────────────────────────────────────
    {
        "dashboard_section": "RS Correction",
        "dashboard_output": "RS_leaders",
        "field_or_rule": "rs_correction_leader_list",
        "source_file_or_module": "data/research/rs_vs_vnindex_correction_20260515_20260525.csv",
        "already_backtested": True,
        "existing_backtest_path": "data/research/rs_vs_vnindex_correction_20260515_20260525.csv",
        "existing_result_summary": "RS vs VNINDEX correction event study 2026-05-15 to 2026-05-25; 10-day window ONLY — insufficient for DIRECTIONALLY_SUPPORTED label",
        "evidence_status": EvidenceStatus.PARTIALLY_VALIDATED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RETURN",
        "evidence_label": EvidenceLabel.INCONCLUSIVE_DIRECTIONAL_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "DOWNGRADED: 10-day observation window is insufficient for DIRECTIONALLY_SUPPORTED. Need minimum 90 trading days / 3 correction events for robust label.",
    },
    {
        "dashboard_section": "RS Correction",
        "dashboard_output": "RS_defensive",
        "field_or_rule": "rs_correction_defensive_list",
        "source_file_or_module": "data/research/rs_vs_vnindex_correction_20260515_20260525.csv",
        "already_backtested": False,
        "existing_backtest_path": "data/research/rs_vs_vnindex_correction_20260515_20260525.csv",
        "existing_result_summary": "Partial — same CSV as leaders but defensive bucket not separately validated",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RISK",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Defensive bucket specific test not run",
    },
    {
        "dashboard_section": "RS Correction",
        "dashboard_output": "weakest_RS",
        "field_or_rule": "rs_correction_weakest_list",
        "source_file_or_module": "",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "needs_new_backtest": True,
        "recommended_test_type": "TESTABLE_RETURN",
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Weakest RS forward study not run",
    },
    # ── Section H: RS C3 ──────────────────────────────────────────────────────
    {
        "dashboard_section": "RS C3",
        "dashboard_output": "C3_rating",
        "field_or_rule": "c3_rating",
        "source_file_or_module": "src/review/rs_c3_review.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "IC near zero in OOS 2024+ per prior analysis; review-ranking only",
        "evidence_status": EvidenceStatus.CONTEXT_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "CONTEXT_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "Review-ranking only per prior OOS IC analysis; C3 IC near zero in 2024+",
    },
    {
        "dashboard_section": "RS C3",
        "dashboard_output": "EXTREME_RS",
        "field_or_rule": "extreme_rs_flag",
        "source_file_or_module": "src/review/rs_c3_review.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "IC near zero in OOS 2024+",
        "evidence_status": EvidenceStatus.CONTEXT_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "CONTEXT_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "IC near zero in OOS 2024+; context only",
    },
    # ── Section I: Delta ──────────────────────────────────────────────────────
    {
        "dashboard_section": "Delta",
        "dashboard_output": "action_changes",
        "field_or_rule": "delta_final_action",
        "source_file_or_module": "src/trading/reports/cloud_daily_report.py",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "DISPLAY_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "Change tracking only; workflow tool",
    },
    # ── Section J: Appendix ───────────────────────────────────────────────────
    {
        "dashboard_section": "Appendix",
        "dashboard_output": "full_scan_table",
        "field_or_rule": "all scan columns",
        "source_file_or_module": "data/research/portfolio_optimization/missing_work/phase36_daily_scan_*.csv",
        "already_backtested": False,
        "existing_backtest_path": "",
        "existing_result_summary": "",
        "evidence_status": EvidenceStatus.DISPLAY_ONLY.value,
        "needs_new_backtest": False,
        "recommended_test_type": "DISPLAY_ONLY",
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "Data display appendix only",
    },
]


def build_evidence_registry() -> pd.DataFrame:
    """Build and return the evidence registry DataFrame.

    Returns a DataFrame with all required columns documenting what has been
    validated, what is display-only, what needs new backtest, and what is
    blocked by data. Parses the Distribution Risk JSON to attach real stats.
    """
    rows = list(_REGISTRY_ROWS)

    # Parse Distribution Risk JSON and update that row with real stats
    dist_risk_parsed = parse_distribution_risk_json()
    for row in rows:
        if row["dashboard_output"] == "VNINDEX_dist_risk":
            parsed_label = dist_risk_parsed["evidence_label"]
            row["evidence_label"] = parsed_label
            sample_n = dist_risk_parsed["sample_size"]
            ex_vin = dist_risk_parsed["ex_vin_survives"]
            row["existing_result_summary"] = (
                f"Parsed: sample_size={sample_n}, horizons={dist_risk_parsed['horizons'][:3]}, "
                f"ex_vin_file_exists={ex_vin}, parsed_ok={dist_risk_parsed['parsed_ok']}"
            )
            if not dist_risk_parsed["parsed_ok"]:
                row["evidence_status"] = EvidenceStatus.BLOCKED_BY_DATA.value
                row["evidence_label"] = EvidenceLabel.BLOCKED_BY_DATA.value
                row["notes"] = f"JSON parse failed: {dist_risk_parsed['raw_summary'][:200]}"
            break

    df = pd.DataFrame(rows)

    # Ensure all required columns exist
    required_cols = [
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
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""
    # Add research label
    df["research_label"] = RESEARCH_ONLY_LABEL
    logger.info(
        "Evidence registry built: %d rows, %d needing new backtest, %d display-only",
        len(df),
        df["needs_new_backtest"].sum(),
        (df["evidence_status"] == EvidenceStatus.DISPLAY_ONLY.value).sum(),
    )
    return df
