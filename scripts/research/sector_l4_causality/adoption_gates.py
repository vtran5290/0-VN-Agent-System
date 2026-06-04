"""
Evaluate all P0 adoption gates and produce adoption_gate_summary.csv.
Conservative default: DASHBOARD_WARNING_ONLY unless gates explicitly passed.
"""
from __future__ import annotations
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .config import OUTPUT_DIR

log = logging.getLogger(__name__)

VERDICTS = [
    "REJECT_SECTOR_LAYER",
    "DASHBOARD_WARNING_ONLY",
    "RANKING_FEATURE_ONLY",
    "SHADOW_RISK_CONTROL",
    "HARD_FILTER_CANDIDATE",
]


def evaluate_gates(
    lead_lag_summary: pd.DataFrame,
    ablation_full: pd.DataFrame,
    ablation_ex_vin: pd.DataFrame,
    ledger_replay: pd.DataFrame,
    placebo_summary: pd.DataFrame,
    coverage_audit: pd.DataFrame,
) -> pd.DataFrame:
    """
    Check all 10 hard-filter gates and 3 ranking-feature gates.
    Returns a gate-by-gate pass/fail table and final verdict.
    """
    gates = []

    # ── Helper to extract metric ──────────────────────────────────────────────
    def _get(df: pd.DataFrame, rule: str, col: str, default=np.nan):
        if df is None or df.empty:
            return default
        row = df[df.get("rule_id", df.get("metric", pd.Series(dtype=str))) == rule]
        if row.empty:
            return default
        return row.iloc[0].get(col, default)

    # ── Gate 1: Lead/lag — ≥15% excess stock turns in 10 sessions ───────────
    if lead_lag_summary is not None and not lead_lag_summary.empty:
        median_excess_pct = lead_lag_summary["excess_turn_pct_t1_t10"].median()
        passes_g1 = bool(median_excess_pct >= 0.15)
    else:
        median_excess_pct = np.nan
        passes_g1 = False
    gates.append({
        "gate_id":   "G1_lead_lag",
        "criterion": "Median excess stock-turn pct ≥ 15% vs matched random, within 10 sessions",
        "observed":  f"{median_excess_pct:.3f}" if not np.isnan(median_excess_pct) else "N/A",
        "passes":    int(passes_g1),
    })

    # ── Gate 2: Forward-return gate ──────────────────────────────────────────
    abl = ablation_full if ablation_full is not None else pd.DataFrame()
    gate_row_60 = abl[
        (abl.get("rule_id", pd.Series(dtype=str)) == "l4_equal_weight_ge_40pct") &
        (abl.get("horizon", pd.Series(dtype=int)) == 60)
    ] if not abl.empty and "rule_id" in abl.columns else pd.DataFrame()

    if not gate_row_60.empty:
        d_hit = float(gate_row_60.iloc[0].get("delta_hit_rate", 0))
        d_mean = float(gate_row_60.iloc[0].get("delta_mean", 0))
    else:
        d_hit, d_mean = np.nan, np.nan

    passes_g2 = (
        not np.isnan(d_hit) and not np.isnan(d_mean) and
        d_hit >= 0.03 and d_mean >= 0.01
    )
    gates.append({
        "gate_id":   "G2_forward_return",
        "criterion": "Δhit_rate_60d ≥ 3pp AND Δmean_return_60d ≥ 1% vs baseline",
        "observed":  f"Δhit={d_hit:.4f}, Δmean={d_mean:.4f}",
        "passes":    int(passes_g2),
    })

    # ── Gate 3: A3 ledger ΔMAR ≥ +0.05 ────────────────────────────────────────
    lr = ledger_replay if ledger_replay is not None else pd.DataFrame()
    if not lr.empty and "delta_mar" in lr.columns:
        delta_mar = float(lr.iloc[0]["delta_mar"]) if not lr.empty else np.nan
        delta_dd  = float(lr.iloc[0].get("delta_maxdd", 0)) if not lr.empty else 0
        losers_b  = int(lr.iloc[0].get("blocked_losers", 0)) if not lr.empty else 0
        winners_b = int(lr.iloc[0].get("blocked_winners", 1)) if not lr.empty else 1
        bl_ratio  = losers_b / max(winners_b, 1)
    else:
        delta_mar = np.nan
        delta_dd  = 0
        bl_ratio  = 0

    passes_g3 = (
        not np.isnan(delta_mar) and delta_mar >= 0.05 and
        delta_dd <= 0.01 and bl_ratio >= 1.2
    )
    gates.append({
        "gate_id":   "G3_a3_ledger_mar",
        "criterion": "ΔMAR ≥ +0.05 AND ΔmaxDD ≤ +1pp AND blocked_losers/winners ≥ 1.2",
        "observed":  f"ΔMAR={delta_mar:.4f}, Δdd={delta_dd:.4f}, bl_ratio={bl_ratio:.2f}",
        "passes":    int(passes_g3),
    })

    # ── Gate 4: Retention ≥ 85% ───────────────────────────────────────────────
    if not lr.empty and "n_trades_baseline" in lr.columns and "n_trades_rule" in lr.columns:
        try:
            ret_pct = float(lr.iloc[0]["n_trades_rule"]) / max(float(lr.iloc[0]["n_trades_baseline"]), 1)
        except (ValueError, TypeError):
            ret_pct = np.nan
    else:
        ret_pct = np.nan
    passes_g4 = not np.isnan(ret_pct) and ret_pct >= 0.85
    gates.append({
        "gate_id":   "G4_retention",
        "criterion": "Rule retains ≥ 85% of baseline A3 trades",
        "observed":  f"{ret_pct:.3f}" if not np.isnan(ret_pct) else "N/A",
        "passes":    int(passes_g4),
    })

    # ── Gate 5: Regime gate (positive in M0 normal/defensive) ────────────────
    # Check from regime_stratified table
    gates.append({
        "gate_id":   "G5_regime",
        "criterion": "Benefit positive in M0_normal + M0_defensive regimes",
        "observed":  "See regime_stratified_full_vs_ex_vin.csv",
        "passes":    0,  # Conservative default; operator must verify
    })

    # ── Gate 6: ex-VIN survives ────────────────────────────────────────────────
    abl_exv = ablation_ex_vin if ablation_ex_vin is not None else pd.DataFrame()
    if not abl_exv.empty and "delta_hit_rate" in abl_exv.columns:
        exv_row = abl_exv[
            abl_exv.get("rule_id", pd.Series(dtype=str)).str.contains("ge_40", na=False) &
            (abl_exv.get("horizon", pd.Series(dtype=int)) == 60)
        ]
        exv_dhr = float(exv_row.iloc[0]["delta_hit_rate"]) if not exv_row.empty else np.nan
    else:
        exv_dhr = np.nan
    passes_g6 = not np.isnan(exv_dhr) and exv_dhr >= 0.0
    gates.append({
        "gate_id":   "G6_ex_vin",
        "criterion": "Δhit_rate_60d sign same in ex-VIN universe",
        "observed":  f"ex_vin Δhit={exv_dhr:.4f}" if not np.isnan(exv_dhr) else "N/A",
        "passes":    int(passes_g6),
    })

    # ── Gate 7: Placebo ≥ 95th percentile ────────────────────────────────────
    ps = placebo_summary if placebo_summary is not None else pd.DataFrame()
    if not ps.empty and "passes_95th_gate" in ps.columns:
        passes_g7 = int(ps.iloc[0]["passes_95th_gate"])
        pct = ps.iloc[0].get("real_percentile", np.nan)
    else:
        passes_g7 = 0
        pct = np.nan
    gates.append({
        "gate_id":   "G7_placebo",
        "criterion": "Real result above 95th percentile of shuffled-label placebo",
        "observed":  f"Percentile={pct:.1f}%" if not np.isnan(pct) else "N/A",
        "passes":    passes_g7,
    })

    # ── Gate 8: Unknown sensitivity ──────────────────────────────────────────
    ca = coverage_audit if coverage_audit is not None else pd.DataFrame()
    unknown_frac = ca["is_unknown"].mean() if not ca.empty and "is_unknown" in ca.columns else np.nan
    passes_g8 = not np.isnan(unknown_frac) and unknown_frac < 0.30
    gates.append({
        "gate_id":   "G8_coverage",
        "criterion": "Unknown L4 fraction < 30% of universe",
        "observed":  f"{unknown_frac:.3f}" if not np.isnan(unknown_frac) else "N/A",
        "passes":    int(passes_g8),
    })

    # ── Gates 9, 10: Stability + Simplicity (operator review required) ────────
    gates.append({
        "gate_id":   "G9_stability",
        "criterion": "Same direction in 2012–2019 and 2020–latest; no subperiod >70%",
        "observed":  "See threshold_sweep_summary.csv train vs test periods",
        "passes":    0,  # Requires operator review of threshold_sweep_summary
    })
    gates.append({
        "gate_id":   "G10_simplicity",
        "criterion": "Rule explainable in one sentence; auditable daily",
        "observed":  "l4_breadth_equal_weight >= 40% with 35% reset",
        "passes":    1,  # Primary 40/35 rule is simple
    })

    gate_df = pd.DataFrame(gates)
    n_pass = gate_df["passes"].sum()
    all_hard = n_pass == 10

    # ── Ranking-feature gates ─────────────────────────────────────────────────
    ranking_passes = (passes_g1 or passes_g2) and passes_g6

    # ── Final verdict ─────────────────────────────────────────────────────────
    if all_hard:
        verdict = "HARD_FILTER_CANDIDATE"
    elif passes_g3 and passes_g6:
        verdict = "SHADOW_RISK_CONTROL"
    elif ranking_passes:
        verdict = "RANKING_FEATURE_ONLY"
    else:
        verdict = "DASHBOARD_WARNING_ONLY"

    summary = pd.DataFrame([{
        "gates_passed":      int(n_pass),
        "gates_total":       10,
        "hard_filter_all_pass": int(all_hard),
        "final_verdict":     verdict,
        "note":              "Default conservative verdict. Operator must review G5/G9.",
    }])

    gate_df.to_csv(OUTPUT_DIR / "adoption_gate_detail.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "adoption_gate_summary.csv", index=False)
    log.info("Adoption verdict: %s (%d/10 gates passed)", verdict, n_pass)
    return summary
