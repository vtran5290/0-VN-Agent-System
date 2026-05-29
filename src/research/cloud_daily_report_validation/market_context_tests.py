"""Market/Breadth/Risk context tests — section 5.6.

Tests breadth zone, T1/T2 permissions, distribution risk, ex-VIN proxy,
VIN basket warning, correction probabilities.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging

import pandas as pd

from .data_loader import LABEL_RECONSTRUCTED
from .evidence_inventory import parse_distribution_risk_json
from .schema import (
    OUTPUT_DIR,
    RESEARCH_ONLY_LABEL,
    _REPO,
    DashboardRecommendation,
    EvidenceLabel,
    EvidenceStatus,
)

logger = logging.getLogger(__name__)

_OUTPUT_FILE = OUTPUT_DIR / "market_context_validation.csv"

_DIST_RISK_JSON = _REPO / "data" / "research" / "vnindex_low_dist_forward_returns.json"
_DIST_RISK_EX_VIN_JSON = _REPO / "data" / "research" / "vnindex_low_dist_forward_returns_ex_vin.json"
_EX_VIN_SERIES = _REPO / "data" / "research" / "vnindex_ex_vin_daily_series.csv"
_DIST_SUMMARY = _REPO / "data" / "research" / "vnindex_dist_v2_summary.json"


def _run_distribution_risk_summary() -> dict:
    """Parse distribution risk JSON and summarize for market_context_validation."""
    parsed = parse_distribution_risk_json()
    return {
        "test": "distribution_risk_forward_returns",
        "source_file": str(_DIST_RISK_JSON),
        "sample_size": parsed["sample_size"],
        "horizons": str(parsed["horizons"][:5]),
        "drawdown_impact": parsed["drawdown_impact"],
        "benchmark_comparison": parsed["benchmark_comparison"],
        "ex_vin_file_exists": parsed["ex_vin_survives"],
        "parsed_ok": parsed["parsed_ok"],
        "evidence_status": (
            EvidenceStatus.PARTIALLY_VALIDATED.value if parsed["parsed_ok"]
            else EvidenceStatus.BLOCKED_BY_DATA.value
        ),
        "evidence_label": parsed["evidence_label"],
        "dashboard_recommendation": (
            DashboardRecommendation.KEEP_AS_RISK_CONTROL.value
            if parsed["evidence_label"] == EvidenceLabel.RISK_CONTROL_SUPPORTED.value
            else DashboardRecommendation.NEEDS_MORE_DATA.value
        ),
        "signal_integrity": LABEL_RECONSTRUCTED,
        "research_label": RESEARCH_ONLY_LABEL,
        "notes": (
            "PARSED from vnindex_low_dist_forward_returns.json. "
            f"ex-VIN file: {parsed['ex_vin_survives']}. "
            "Supports risk-control drawdown warning; not standalone alpha signal."
        ),
    }


def run_market_context_validation(scan_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Run market/breadth/risk context validation.

    Most tests are BLOCKED_BY_DATA due to insufficient scan history.
    Distribution risk uses existing JSON files.

    Parameters
    ----------
    scan_df: optional scan DataFrame; if None, data_loader.load_scan_files() is called

    Returns
    -------
    DataFrame written to market_context_validation.csv
    """
    rows: list[dict] = []
    base = {"signal_integrity": LABEL_RECONSTRUCTED, "research_label": RESEARCH_ONLY_LABEL}

    # --- Distribution Risk (has real data) ---
    rows.append(_run_distribution_risk_summary())

    # --- ex-VIN proxy ---
    ex_vin_exists = _EX_VIN_SERIES.is_file()
    rows.append({
        **base,
        "test": "ex_vin_proxy_series",
        "source_file": str(_EX_VIN_SERIES),
        "sample_size": None,
        "horizons": "NOT_COMPUTED",
        "drawdown_impact": None,
        "benchmark_comparison": None,
        "ex_vin_file_exists": ex_vin_exists,
        "parsed_ok": ex_vin_exists,
        "evidence_status": (
            EvidenceStatus.NOT_BACKTESTED.value if ex_vin_exists
            else EvidenceStatus.BLOCKED_BY_DATA.value
        ),
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": (
            f"ex-VIN daily series {'exists' if ex_vin_exists else 'NOT FOUND'}. "
            "Forward event study not yet run — BLOCKED_BY_DATA pending 90d+ scan history."
        ),
    })

    # --- Breadth zone forward returns ---
    rows.append({
        **base,
        "test": "breadth_zone_forward_returns",
        "source_file": "data/research/portfolio_optimization/missing_work/phase36_daily_scan_*.csv",
        "sample_size": len(scan_df) if scan_df is not None else None,
        "horizons": "NOT_COMPUTED",
        "drawdown_impact": None,
        "benchmark_comparison": None,
        "ex_vin_file_exists": None,
        "parsed_ok": False,
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": (
            "Breadth zone event study requires ≥90 days of scan history and "
            "matching VNINDEX forward returns. Currently BLOCKED_BY_DATA."
        ),
    })

    # --- T2 permission gate ---
    rows.append({
        **base,
        "test": "t2_permission_gate_forward_returns",
        "source_file": "data/research/portfolio_optimization/missing_work/phase36_daily_scan_*.csv",
        "sample_size": None,
        "horizons": "NOT_COMPUTED",
        "drawdown_impact": None,
        "benchmark_comparison": None,
        "ex_vin_file_exists": None,
        "parsed_ok": False,
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "T2 gate event study requires ≥90 days of scan history. BLOCKED_BY_DATA.",
    })

    # --- VIN basket warning ---
    rows.append({
        **base,
        "test": "vin_basket_warning",
        "source_file": "data/research/vnindex_ex_vin_daily_series.csv",
        "sample_size": None,
        "horizons": "NOT_COMPUTED",
        "drawdown_impact": None,
        "benchmark_comparison": None,
        "ex_vin_file_exists": ex_vin_exists,
        "parsed_ok": False,
        "evidence_status": EvidenceStatus.CONTEXT_ONLY.value,
        "evidence_label": EvidenceLabel.DISPLAY_ONLY.value,
        "dashboard_recommendation": DashboardRecommendation.KEEP_AS_DISPLAY_ONLY.value,
        "notes": "VIN basket distortion is a known cap-weight artifact; display/context only.",
    })

    # --- Sector L4 stress count ---
    rows.append({
        **base,
        "test": "sector_l4_stress_count",
        "source_file": "src/trading/reports/cloud_daily_report.py",
        "sample_size": None,
        "horizons": "NOT_COMPUTED",
        "drawdown_impact": None,
        "benchmark_comparison": None,
        "ex_vin_file_exists": None,
        "parsed_ok": False,
        "evidence_status": EvidenceStatus.NOT_BACKTESTED.value,
        "evidence_label": EvidenceLabel.BLOCKED_BY_DATA.value,
        "dashboard_recommendation": DashboardRecommendation.NEEDS_MORE_DATA.value,
        "notes": "Sector L4 stress count forward study not yet run. BLOCKED_BY_DATA.",
    })

    return pd.DataFrame(rows)


def run_market_context_validation_full() -> pd.DataFrame:
    """Run market context validation and write to CSV."""
    result = run_market_context_validation()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(_OUTPUT_FILE, index=False)
    logger.info("Market context validation written to %s (%d rows)", _OUTPUT_FILE, len(result))
    return result
