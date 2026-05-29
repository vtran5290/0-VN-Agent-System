"""Cloud validation summary — aggregates all section results into one table.

Creates cloud_validation_summary.csv, cloud_action_portfolio_metrics.csv,
cloud_action_equity_curves.csv, cloud_action_turnover_capacity.csv.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .schema import (
    OUTPUT_DIR,
    RESEARCH_ONLY_LABEL,
    EvidenceLabel,
    EvidenceStatus,
    DashboardRecommendation,
    FINAL_ACTIONS,
)

logger = logging.getLogger(__name__)


def build_portfolio_metrics_blocked() -> pd.DataFrame:
    """Return cloud_action_portfolio_metrics.csv with BLOCKED_BY_DATA rows.

    Columns match Phase 6 spec; all rows are blocked pending scan history accumulation.
    """
    rows = []
    strategies = [
        "baseline_equal_weight_liquid",
        "NEW_T1_only",
        "NEW_T1_excl_manual_breadth",
        "NEW_T1_plus_allowed_T2",
        "NEW_T1_T2_blocked_breadth_lt40",
        "exit_respecting_portfolio",
        "exit_ignored_portfolio_comparison",
    ]
    for strat in strategies:
        rows.append({
            "strategy": strat,
            "cagr": None,
            "total_return": None,
            "volatility": None,
            "sharpe": None,
            "sortino": None,
            "max_drawdown": None,
            "hit_rate": None,
            "turnover": None,
            "avg_holdings": None,
            "excess_vs_vnindex": None,
            "excess_vs_equal_weight_universe": None,
            "ex_vin_result": None,
            "gross_return": None,
            "cost_adjusted_return": None,
            "capacity_estimate": None,
            "slippage_assumption": "N/A",
            "transaction_cost_assumption": "N/A",
            "acceptance_label": "BLOCKED_BY_DATA",
            "signal_integrity": "RECONSTRUCTED_NOT_LIVE_SCAN",
            "research_label": RESEARCH_ONLY_LABEL,
            "notes": (
                "BLOCKED_BY_DATA: Portfolio simulation requires ≥6 months of true historical "
                "scan outputs with timestamped final_action. Current scan history: ~2 weeks. "
                "Framework is ready; re-run when history accumulates."
            ),
        })
    return pd.DataFrame(rows)


def build_equity_curves_blocked() -> pd.DataFrame:
    """Return cloud_action_equity_curves.csv with BLOCKED_BY_DATA rows."""
    rows = []
    for strat in ["baseline", "NEW_T1_only", "NEW_T1_plus_T2", "exit_respecting"]:
        rows.append({
            "strategy": strat,
            "date": None,
            "equity_index": None,
            "drawdown": None,
            "acceptance_label": "BLOCKED_BY_DATA",
            "research_label": RESEARCH_ONLY_LABEL,
            "notes": "BLOCKED_BY_DATA: No scan history for equity curve computation.",
        })
    return pd.DataFrame(rows)


def build_turnover_capacity_blocked() -> pd.DataFrame:
    """Return cloud_action_turnover_capacity.csv with BLOCKED_BY_DATA rows."""
    rows = []
    for strat in ["NEW_T1_only", "NEW_T1_plus_T2", "exit_respecting"]:
        rows.append({
            "strategy": strat,
            "avg_monthly_turnover": None,
            "annual_turnover": None,
            "avg_adv50_b": None,
            "capacity_estimate_b": None,
            "cost_sensitivity_low": None,
            "cost_sensitivity_high": None,
            "acceptance_label": "BLOCKED_BY_DATA",
            "research_label": RESEARCH_ONLY_LABEL,
            "notes": "BLOCKED_BY_DATA: Requires ≥6 months of scan history.",
        })
    return pd.DataFrame(rows)


def build_validation_summary(output_dir: Path | None = None) -> pd.DataFrame:
    """Aggregate all section validation CSVs into a single summary table.

    Reads all existing validation CSVs from OUTPUT_DIR and summarizes their
    evidence_label and dashboard_recommendation columns.
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR

    # Map of CSV filename → section label
    csv_map: dict[str, str] = {
        "cloud_dashboard_evidence_registry.csv": "Phase0 Evidence Registry",
        "cloud_dashboard_output_inventory.csv": "Phase1 Output Inventory",
        "final_action_validation.csv": "Phase5.1 Final Action Tests",
        "t1_t2_gate_validation.csv": "Phase5.2 T1/T2 Gate Tests",
        "exit_logic_validation.csv": "Phase5.3 Exit Logic Tests",
        "ranking_validation.csv": "Phase5.4 Ranking Tests",
        "s3_radar_validation.csv": "Phase5.5 S3 Radar Tests",
        "market_context_validation.csv": "Phase5.6 Market Context Tests",
        "rs_correction_validation.csv": "Phase5.7 RS Correction Tests",
        "rs_c3_validation.csv": "Phase5.8 RS C3 Tests",
        "portfolio_overlay_validation.csv": "Phase5.9 Portfolio Overlay Tests",
        "cloud_action_portfolio_metrics.csv": "Phase6 Portfolio Simulation",
        "evidence_search_hits.csv": "Phase3 Evidence Search",
    }

    rows: list[dict] = []
    for fname, section in csv_map.items():
        fpath = output_dir / fname
        if not fpath.is_file():
            rows.append({
                "section": section,
                "file": fname,
                "n_rows": 0,
                "n_blocked": 0,
                "n_display_only": 0,
                "n_validated": 0,
                "n_inconclusive": 0,
                "top_evidence_label": "FILE_MISSING",
                "top_dashboard_recommendation": "FILE_MISSING",
                "status": "FILE_MISSING",
                "research_label": RESEARCH_ONLY_LABEL,
                "notes": f"File not found at {fpath}",
            })
            continue

        try:
            df = pd.read_csv(fpath)
        except Exception as exc:
            rows.append({
                "section": section,
                "file": fname,
                "n_rows": 0,
                "n_blocked": 0,
                "n_display_only": 0,
                "n_validated": 0,
                "n_inconclusive": 0,
                "top_evidence_label": "READ_ERROR",
                "top_dashboard_recommendation": "READ_ERROR",
                "status": "READ_ERROR",
                "research_label": RESEARCH_ONLY_LABEL,
                "notes": str(exc)[:200],
            })
            continue

        # Count evidence labels
        ev_col = next(
            (c for c in ("evidence_label", "evidence_status") if c in df.columns), None
        )
        rec_col = next(
            (c for c in ("dashboard_recommendation",) if c in df.columns), None
        )
        blocked = int((df[ev_col] == "BLOCKED_BY_DATA").sum()) if ev_col else 0
        display = int((df[ev_col] == "DISPLAY_ONLY").sum()) if ev_col else 0
        validated = int(
            df[ev_col].isin([
                "STATISTICALLY_SUPPORTED",
                "DIRECTIONALLY_SUPPORTED",
                "RISK_CONTROL_SUPPORTED",
                "ALREADY_VALIDATED",
            ]).sum()
        ) if ev_col else 0
        inconclusive = int(
            df[ev_col].isin([
                "INCONCLUSIVE",
                "INCONCLUSIVE_DIRECTIONAL_ONLY",
                "WORKFLOW_ONLY",
                "PARTIALLY_VALIDATED",
            ]).sum()
        ) if ev_col else 0
        top_ev = df[ev_col].value_counts().index[0] if (ev_col and not df.empty) else "N/A"
        top_rec = df[rec_col].value_counts().index[0] if (rec_col and not df.empty) else "N/A"

        rows.append({
            "section": section,
            "file": fname,
            "n_rows": len(df),
            "n_blocked": blocked,
            "n_display_only": display,
            "n_validated": validated,
            "n_inconclusive": inconclusive,
            "top_evidence_label": top_ev,
            "top_dashboard_recommendation": top_rec,
            "status": "OK",
            "research_label": RESEARCH_ONLY_LABEL,
            "notes": "",
        })

    return pd.DataFrame(rows)


def write_all_portfolio_outputs() -> None:
    """Write all portfolio simulation CSVs with BLOCKED_BY_DATA rows."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = build_portfolio_metrics_blocked()
    metrics.to_csv(OUTPUT_DIR / "cloud_action_portfolio_metrics.csv", index=False)
    curves = build_equity_curves_blocked()
    curves.to_csv(OUTPUT_DIR / "cloud_action_equity_curves.csv", index=False)
    turnover = build_turnover_capacity_blocked()
    turnover.to_csv(OUTPUT_DIR / "cloud_action_turnover_capacity.csv", index=False)
    logger.info("Portfolio simulation CSVs written (all BLOCKED_BY_DATA)")


def write_validation_summary() -> pd.DataFrame:
    """Build and write cloud_validation_summary.csv."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = build_validation_summary()
    out = OUTPUT_DIR / "cloud_validation_summary.csv"
    summary.to_csv(out, index=False)
    logger.info("Validation summary written to %s (%d rows)", out, len(summary))
    return summary
