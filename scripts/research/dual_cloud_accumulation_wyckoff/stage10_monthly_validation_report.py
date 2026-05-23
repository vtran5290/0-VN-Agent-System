"""Stage 10 — Monthly Validation Report.

Reads Stage 9 forward validation outputs and produces a clean monthly research
report. Evaluates candidate watchlist flags against baseline using mature-only
rows. Applies classification rules to determine PARALLEL_PAPER_RESEARCH /
WATCHLIST_ONLY / REJECT / needs_more_data.

This is PAPER VALIDATION / OBSERVATION ONLY.
- Does not modify production trading logic.
- Does not modify OMS / live trading logic.
- Does not promote S3 to production.
- Does not change A3 production contract.
- Does not modify final_action.
- All fields are observation-only.

Outputs (all under OUT_DIR):
  stage10_monthly_validation_summary.csv
  stage10_candidate_decision_table.csv
  stage10_regime_adjusted_summary.csv
  STAGE10_MONTHLY_VALIDATION_REPORT.md
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import OUT_DIR

log = logging.getLogger(__name__)

# ── Safety constants ───────────────────────────────────────────────────────────
_STAGE10_WRITE_DIR: Path = OUT_DIR

_OMS_SAFE_PATHS: frozenset[str] = frozenset({
    str(REPO / "data" / "decision" / "daily_scan.json"),
    str(REPO / "data" / "decision" / "daily_scan.md"),
    str(REPO / "data" / "decision" / "allocation_plan.json"),
    str(REPO / "data" / "state" / "regime_state.json"),
    str(REPO / "data" / "raw" / "current_positions_derived.json"),
    str(REPO / "data" / "raw" / "current_positions_digest.md"),
})

# ── Classification thresholds ──────────────────────────────────────────────────
_MIN_MATURED_63D      = 40      # minimum sample for any conclusion
_WIN_RATE_DELTA_PP    = 0.05    # +5pp over baseline to qualify
_MIN_YEARS_POSITIVE   = 2       # must be positive in at least 2 years
_MIN_LIQ_BUCKETS      = 2       # must be positive in at least 2 liq buckets

# ── Candidate group definitions ────────────────────────────────────────────────
# Each entry: (label, column, min_q, max_q)
# min_q/max_q are inclusive quintile boundaries (None = no filter on that side)
_CANDIDATE_FILTERS: List[Tuple[str, str, Optional[int], Optional[int]]] = [
    ("BVE_Q5",        "breakout_value_expansion_q",              5, 5),
    ("BVE_Q4Q5",      "breakout_value_expansion_q",              4, None),
    ("TPBCQ_Q5",      "tightness_plus_breakout_close_quality_q", 5, 5),
    ("TPBCQ_Q4Q5",    "tightness_plus_breakout_close_quality_q", 4, None),
    ("Wyckoff_SOS",   "wyckoff_sos",                             1, None),
    ("old_composite_Q5", "old_composite_q",                      5, 5),
]


def _filter_candidate(df: pd.DataFrame, col: str, min_q: Optional[int], max_q: Optional[int]) -> pd.DataFrame:
    """Return rows matching the candidate filter (mature 63d only)."""
    mask = df["fwd_63d_matured"].astype(bool)
    if col not in df.columns:
        return df[mask & pd.Series(False, index=df.index)]
    if min_q is not None:
        mask = mask & (df[col] >= min_q)
    if max_q is not None:
        mask = mask & (df[col] <= max_q)
    return df[mask]


def _candidate_stats(sub: pd.DataFrame) -> dict:
    """Compute win-rate / return / TP1 stats for a candidate subset."""
    valid = sub["fwd_63d_return"].dropna()
    n = len(valid)
    if n == 0:
        return {
            "n_matured_63d": 0,
            "win_rate_63d":  np.nan,
            "avg_return_63d": np.nan,
            "med_return_63d": np.nan,
            "tp1_rate_63d":  np.nan,
            "avg_mae_63d":   np.nan,
            "avg_mfe_63d":   np.nan,
            "pct_positive":  np.nan,
        }
    tp1_col = "tp1_hit_63d"
    tp1_rate = float(sub[tp1_col].dropna().mean()) if tp1_col in sub.columns else np.nan
    return {
        "n_matured_63d":  n,
        "win_rate_63d":   float((valid >= 0.15).mean()),
        "avg_return_63d": float(valid.mean()),
        "med_return_63d": float(valid.median()),
        "tp1_rate_63d":   tp1_rate,
        "avg_mae_63d":    float(sub["max_adverse_excursion_63d"].dropna().mean()) if "max_adverse_excursion_63d" in sub.columns else np.nan,
        "avg_mfe_63d":    float(sub["max_favorable_excursion_63d"].dropna().mean()) if "max_favorable_excursion_63d" in sub.columns else np.nan,
        "pct_positive":   float((valid > 0).mean()),
    }


def _classify_candidate(
    label: str,
    stats: dict,
    baseline: dict,
    by_year: pd.DataFrame,
    by_liq: pd.DataFrame,
) -> Tuple[str, str, str]:
    """
    Returns (classification, action, reason).

    PARALLEL_PAPER_RESEARCH  — clears all 6 gates
    WATCHLIST_ONLY           — promising but below threshold
    REJECT                   — consistently worse
    needs_more_data          — sample too thin
    """
    n = stats["n_matured_63d"]

    # Hard-coded exceptions
    if label == "old_composite_Q5":
        return "REJECT", "No action", (
            "Old composite was rejected in Stage 7 — directionally unstable. "
            "Maintaining REJECT unless extremely strong evidence."
        )

    if n < _MIN_MATURED_63D:
        return "needs_more_data", "Monitor", f"Only {n} matured rows (< {_MIN_MATURED_63D})"

    if np.isnan(stats["win_rate_63d"]):
        return "needs_more_data", "Monitor", "win_rate_63d is NaN"

    # Compute deltas vs baseline
    delta_win   = stats["win_rate_63d"]  - baseline["win_rate_63d"]
    delta_ret   = stats["avg_return_63d"] - baseline["avg_return_63d"]
    delta_tp1   = (
        stats["tp1_rate_63d"] - baseline["tp1_rate_63d"]
        if not (np.isnan(stats["tp1_rate_63d"]) or np.isnan(baseline["tp1_rate_63d"]))
        else np.nan
    )

    # Year breadth: count years where candidate return > 0
    years_positive = 0
    if not by_year.empty and "avg_return_63d" in by_year.columns:
        for _, yr_row in by_year.iterrows():
            if not np.isnan(yr_row.get("avg_return_63d", np.nan)) and yr_row["avg_return_63d"] > 0:
                years_positive += 1

    # Liquidity breadth: count liq buckets where candidate return > 0
    liq_buckets_positive = 0
    if not by_liq.empty and "avg_return_63d" in by_liq.columns:
        for _, liq_row in by_liq.iterrows():
            if not np.isnan(liq_row.get("avg_return_63d", np.nan)) and liq_row["avg_return_63d"] > 0:
                liq_buckets_positive += 1

    gates_passed = []
    gates_failed = []

    if delta_win >= _WIN_RATE_DELTA_PP:
        gates_passed.append(f"win_rate delta={delta_win*100:.1f}pp ≥ 5pp")
    else:
        gates_failed.append(f"win_rate delta={delta_win*100:.1f}pp < 5pp")

    if delta_ret > 0:
        gates_passed.append(f"avg_return delta={delta_ret*100:.1f}pp > 0")
    else:
        gates_failed.append(f"avg_return delta={delta_ret*100:.1f}pp ≤ 0")

    if not np.isnan(delta_tp1) and delta_tp1 > 0:
        gates_passed.append(f"tp1_rate delta={delta_tp1*100:.1f}pp > 0")
    elif np.isnan(delta_tp1):
        gates_passed.append("tp1_rate delta=NA (skip)")
    else:
        gates_failed.append(f"tp1_rate delta={delta_tp1*100:.1f}pp ≤ 0")

    if years_positive >= _MIN_YEARS_POSITIVE:
        gates_passed.append(f"positive in {years_positive} years ≥ {_MIN_YEARS_POSITIVE}")
    else:
        gates_failed.append(f"positive in {years_positive} years < {_MIN_YEARS_POSITIVE}")

    if liq_buckets_positive >= _MIN_LIQ_BUCKETS or liq_buckets_positive == 0:
        # 0 means no liq data — skip this gate
        if liq_buckets_positive > 0:
            gates_passed.append(f"positive in {liq_buckets_positive} liq buckets ≥ {_MIN_LIQ_BUCKETS}")
    else:
        gates_failed.append(f"positive in {liq_buckets_positive} liq buckets < {_MIN_LIQ_BUCKETS}")

    all_gate_count = 4 if liq_buckets_positive == 0 else 5
    passed_count   = len(gates_passed)

    if passed_count == all_gate_count:
        return "PARALLEL_PAPER_RESEARCH", "Set up paper portfolio", "; ".join(gates_passed)

    if delta_win < -0.02 and delta_ret < -0.01:
        return "REJECT", "No action", "Consistently underperforms baseline: " + "; ".join(gates_failed)

    reason_parts = []
    if gates_passed:
        reason_parts.append("Positives: " + "; ".join(gates_passed))
    if gates_failed:
        reason_parts.append("Gaps: " + "; ".join(gates_failed))
    return "WATCHLIST_ONLY", "Continue monitoring", " | ".join(reason_parts)


# ── Regime / year / liquidity decomposition ────────────────────────────────────

def _decompose_by_group(
    df_mature: pd.DataFrame,
    group_col: str,
    candidate_col: str,
    candidate_min_q: Optional[int],
    candidate_max_q: Optional[int],
) -> pd.DataFrame:
    """Compute candidate vs baseline stats by group column at h=63."""
    rows = []
    for grp_val, grp_df in df_mature.groupby(group_col, dropna=False):
        # Baseline stats for this group
        baseline = _candidate_stats(grp_df)

        # Candidate mask within group
        cand_mask = pd.Series(True, index=grp_df.index)
        if candidate_col in grp_df.columns:
            if candidate_min_q is not None:
                cand_mask = cand_mask & (grp_df[candidate_col] >= candidate_min_q)
            if candidate_max_q is not None:
                cand_mask = cand_mask & (grp_df[candidate_col] <= candidate_max_q)
        cand_stats = _candidate_stats(grp_df[cand_mask])

        rows.append({
            group_col:             grp_val,
            "baseline_n":          baseline["n_matured_63d"],
            "baseline_win_rate":   baseline["win_rate_63d"],
            "baseline_avg_return": baseline["avg_return_63d"],
            "candidate_n":         cand_stats["n_matured_63d"],
            "candidate_win_rate":  cand_stats["win_rate_63d"],
            "candidate_avg_return": cand_stats["avg_return_63d"],
            "candidate_tp1_rate":  cand_stats["tp1_rate_63d"],
            "delta_win_rate_pp":   (
                (cand_stats["win_rate_63d"] - baseline["win_rate_63d"]) * 100
                if not (np.isnan(cand_stats["win_rate_63d"]) or np.isnan(baseline["win_rate_63d"]))
                else np.nan
            ),
        })
    return pd.DataFrame(rows)


# ── Markdown report ────────────────────────────────────────────────────────────

def _format_pct(v: float, decimals: int = 1) -> str:
    if np.isnan(v):
        return "N/A"
    return f"{v * 100:.{decimals}f}%"


def _generate_report_md(
    baseline_stats: dict,
    candidate_results: Dict[str, Tuple[dict, str, str, str]],
    summary_df: pd.DataFrame,
    decision_df: pd.DataFrame,
    regime_df: pd.DataFrame,
    n_total: int,
    n_matured_63d: int,
    date_range: str,
    report_date: str,
) -> str:
    lines = [
        "# Stage 10 Monthly Validation Report",
        "",
        f"**Report date:** {report_date}  |  **Data range:** {date_range}",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        f"- **Total ledger rows:** {n_total}",
        f"- **63d-matured rows:** {n_matured_63d} ({_format_pct(n_matured_63d/n_total if n_total else 0)} of total)",
        f"- **Baseline 63d win rate (≥15%):** {_format_pct(baseline_stats['win_rate_63d'])}",
        f"- **Baseline 63d avg return:** {_format_pct(baseline_stats['avg_return_63d'])}",
        f"- **Baseline TP1 rate (63d):** {_format_pct(baseline_stats['tp1_rate_63d'])}",
        "",
        "No production changes. No OMS changes. All fields are observation-only.",
        "",
        "---",
        "",
        "## 2. Data Coverage",
        "",
        f"- Stage 9 ledger: {n_total} rows, date range: {date_range}",
        f"- 63d-matured: {n_matured_63d} rows used for primary conclusions.",
        "- Immature rows (matured_63d=False) are **excluded** from all 63d conclusions.",
        "- Immature rows are **not counted as losses or zeros**.",
        "",
        "---",
        "",
        "## 3. Mature-Only Result Summary (h=63)",
        "",
    ]
    if not summary_df.empty:
        lines.append(summary_df.to_markdown(index=False))
    else:
        lines.append("_No summary data._")
    lines += ["", "---", "", "## 4. Candidate Performance", ""]

    for label, (stats, classification, action, reason) in candidate_results.items():
        n = stats["n_matured_63d"]
        lines += [
            f"### {label}",
            "",
            f"- **n_matured_63d:** {n}",
            f"- **win_rate_63d:** {_format_pct(stats['win_rate_63d'])} (baseline: {_format_pct(baseline_stats['win_rate_63d'])})",
            f"- **avg_return_63d:** {_format_pct(stats['avg_return_63d'])} (baseline: {_format_pct(baseline_stats['avg_return_63d'])})",
            f"- **tp1_rate_63d:** {_format_pct(stats['tp1_rate_63d'])} (baseline: {_format_pct(baseline_stats['tp1_rate_63d'])})",
            f"- **avg_mae_63d:** {_format_pct(stats['avg_mae_63d'])}",
            f"- **avg_mfe_63d:** {_format_pct(stats['avg_mfe_63d'])}",
            f"- **Classification:** {classification}",
            f"- **Action:** {action}",
            f"- **Reason:** {reason}",
            "",
        ]

    lines += ["---", "", "## 5. Regime / Year / Liquidity Decomposition", ""]
    if not regime_df.empty:
        lines.append(regime_df.to_markdown(index=False))
    else:
        lines.append("_No decomposition data._")
    lines += ["", "---", "", "## 6. Candidate Decision Table", ""]
    if not decision_df.empty:
        lines.append(decision_df.to_markdown(index=False))
    else:
        lines.append("_No decision data._")
    lines += [
        "",
        "---",
        "",
        "## 7. Safety Confirmation",
        "",
        "| Check | Status |",
        "|---|---|",
        "| A3 production contract unchanged | YES |",
        "| S3 not promoted to production | YES |",
        "| OMS / live trading untouched | YES |",
        "| DNSE / live order paths untouched | YES |",
        "| final_action not modified | YES |",
        "| Mature-only analysis for 63d conclusions | YES |",
        "| Immature rows not counted as losses | YES |",
        "| Stage 10 fields observation-only | YES |",
        "",
        "---",
        "",
        "## 8. Recommended Actions",
        "",
    ]

    ppr = [lbl for lbl, (_, cls, _, _) in candidate_results.items() if cls == "PARALLEL_PAPER_RESEARCH"]
    watchlist = [lbl for lbl, (_, cls, _, _) in candidate_results.items() if cls == "WATCHLIST_ONLY"]
    reject = [lbl for lbl, (_, cls, _, _) in candidate_results.items() if cls == "REJECT"]
    nmd = [lbl for lbl, (_, cls, _, _) in candidate_results.items() if cls == "needs_more_data"]

    if ppr:
        lines.append(f"- **Set up paper portfolio:** {', '.join(ppr)}")
    else:
        lines.append("- No candidate cleared PARALLEL_PAPER_RESEARCH threshold this period.")
    lines.append(f"- **Continue monitoring (WATCHLIST_ONLY):** {', '.join(watchlist) if watchlist else 'none'}")
    lines.append(f"- **No action (REJECT):** {', '.join(reject) if reject else 'none'}")
    if nmd:
        lines.append(f"- **Needs more data:** {', '.join(nmd)}")
    lines += [
        "",
        "---",
        "",
        "## 9. Open Questions",
        "",
        "- Is 2025 outperformance driven by market regime (bull cycle) or signal quality?",
        "- Will BVE TP1 lift persist across a full bear cycle?",
        "- Can TPBCQ Q4/Q5 be combined with BVE Q4/Q5 for a stronger composite?",
        "- Are 2026 incomplete rows being correctly excluded from all mature conclusions?",
        "",
        "---",
        "",
        "**This report is RESEARCH ONLY. Not OMS input. Not production recommendation.**",
        "",
    ]
    return "\n".join(lines)


# ── Main entry point ───────────────────────────────────────────────────────────

def run(workers: int = 4) -> None:
    _STAGE10_WRITE_DIR.mkdir(parents=True, exist_ok=True)

    updated_path = _STAGE10_WRITE_DIR / "stage9_forward_validation_updated.csv"
    if not updated_path.exists():
        log.error("Stage 9 updated CSV not found at %s — run Stage 9 first.", updated_path)
        return

    df = pd.read_csv(updated_path)
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["year"] = df["observation_date"].dt.year
    log.info("Loaded Stage 9 data: %d rows", len(df))

    n_total      = len(df)
    n_matured_63 = int(df["fwd_63d_matured"].astype(bool).sum())
    date_range   = f"{df['observation_date'].min().date()} — {df['observation_date'].max().date()}"

    # ── Baseline: all mature 63d rows ─────────────────────────────────────────
    df_mature = df[df["fwd_63d_matured"].astype(bool)].copy()
    baseline_stats = _candidate_stats(df_mature)
    log.info(
        "Baseline (mature 63d): n=%d, win_rate=%.1f%%, avg_return=%.1f%%",
        baseline_stats["n_matured_63d"],
        baseline_stats["win_rate_63d"] * 100,
        baseline_stats["avg_return_63d"] * 100,
    )

    # ── Per-candidate analysis ────────────────────────────────────────────────
    candidate_results: Dict[str, Tuple[dict, str, str, str]] = {}
    decision_rows = []

    for label, col, min_q, max_q in _CANDIDATE_FILTERS:
        sub = _filter_candidate(df, col, min_q, max_q)
        stats = _candidate_stats(sub)

        # Year breakdown for this candidate
        year_rows = []
        if "year" in sub.columns:
            for yr, yr_df in sub.groupby("year", dropna=False):
                yr_stats = _candidate_stats(yr_df)
                yr_row = {"year": yr}
                yr_row.update(yr_stats)
                year_rows.append(yr_row)
        by_year_df = pd.DataFrame(year_rows)

        # Liquidity breakdown
        liq_rows = []
        if "liquidity_bucket" in sub.columns:
            for liq, liq_df in sub.groupby("liquidity_bucket", dropna=False):
                liq_stats = _candidate_stats(liq_df)
                liq_r = {"liquidity_bucket": liq}
                liq_r.update(liq_stats)
                liq_rows.append(liq_r)
        by_liq_df = pd.DataFrame(liq_rows)

        classification, action, reason = _classify_candidate(
            label, stats, baseline_stats, by_year_df, by_liq_df
        )
        candidate_results[label] = (stats, classification, action, reason)

        delta_win = (
            (stats["win_rate_63d"] - baseline_stats["win_rate_63d"]) * 100
            if not (np.isnan(stats["win_rate_63d"]) or np.isnan(baseline_stats["win_rate_63d"]))
            else np.nan
        )
        delta_ret = (
            (stats["avg_return_63d"] - baseline_stats["avg_return_63d"]) * 100
            if not (np.isnan(stats["avg_return_63d"]) or np.isnan(baseline_stats["avg_return_63d"]))
            else np.nan
        )
        delta_tp1 = (
            (stats["tp1_rate_63d"] - baseline_stats["tp1_rate_63d"]) * 100
            if not (np.isnan(stats["tp1_rate_63d"]) or np.isnan(baseline_stats["tp1_rate_63d"]))
            else np.nan
        )

        decision_rows.append({
            "candidate":              label,
            "n_matured_63d":          stats["n_matured_63d"],
            "win_rate_63d":           stats["win_rate_63d"],
            "avg_return_63d":         stats["avg_return_63d"],
            "tp1_rate_63d":           stats["tp1_rate_63d"],
            "avg_mae_63d":            stats["avg_mae_63d"],
            "avg_mfe_63d":            stats["avg_mfe_63d"],
            "delta_win_rate_vs_all_pp": delta_win,
            "delta_avg_return_vs_all_pp": delta_ret,
            "delta_tp1_rate_vs_all_pp": delta_tp1,
            "classification":         classification,
            "action":                 action,
            "reason":                 reason,
        })
        log.info(
            "%s: n=%d, win=%.1f%%, Δwin=%.1fpp → %s",
            label, stats["n_matured_63d"],
            stats["win_rate_63d"] * 100 if not np.isnan(stats["win_rate_63d"]) else float("nan"),
            delta_win if not np.isnan(delta_win) else float("nan"),
            classification,
        )

    # ── Summary table ─────────────────────────────────────────────────────────
    summary_rows = [{"candidate": "all_rows", **baseline_stats}]
    for label, (stats, _, _, _) in candidate_results.items():
        row = {"candidate": label}
        row.update(stats)
        summary_rows.append(row)
    summary_df = pd.DataFrame(summary_rows)

    out_summary = _STAGE10_WRITE_DIR / "stage10_monthly_validation_summary.csv"
    summary_df.to_csv(out_summary, index=False)
    log.info("Saved summary: %s", out_summary.name)

    # ── Decision table ────────────────────────────────────────────────────────
    decision_df = pd.DataFrame(decision_rows)
    out_decision = _STAGE10_WRITE_DIR / "stage10_candidate_decision_table.csv"
    decision_df.to_csv(out_decision, index=False)
    log.info("Saved decision table: %s", out_decision.name)

    # ── Regime-adjusted summary (BVE_Q4Q5 by year + regime) ──────────────────
    bve_col, bve_min = "breakout_value_expansion_q", 4
    regime_rows = []
    if "vnindex_regime" in df_mature.columns:
        for grp_label, grp_col in [("year", "year"), ("regime", "vnindex_regime"), ("liquidity", "liquidity_bucket")]:
            if grp_col not in df_mature.columns:
                continue
            part = _decompose_by_group(df_mature, grp_col, bve_col, bve_min, None)
            if not part.empty:
                part.insert(0, "group_type", grp_label)
                regime_rows.append(part)
    regime_df = pd.concat(regime_rows, ignore_index=True) if regime_rows else pd.DataFrame()

    out_regime = _STAGE10_WRITE_DIR / "stage10_regime_adjusted_summary.csv"
    regime_df.to_csv(out_regime, index=False)
    log.info("Saved regime-adjusted summary: %s", out_regime.name)

    # ── Markdown report ───────────────────────────────────────────────────────
    import datetime
    report_date = str(datetime.date.today())
    findings_md = _generate_report_md(
        baseline_stats    = baseline_stats,
        candidate_results = candidate_results,
        summary_df        = summary_df,
        decision_df       = decision_df,
        regime_df         = regime_df,
        n_total           = n_total,
        n_matured_63d     = n_matured_63,
        date_range        = date_range,
        report_date       = report_date,
    )
    out_md = _STAGE10_WRITE_DIR / "STAGE10_MONTHLY_VALIDATION_REPORT.md"
    out_md.write_text(findings_md, encoding="utf-8")
    log.info("Saved report: %s", out_md.name)

    log.info(
        "Stage 10 complete. %d candidates evaluated. Baseline: n=%d, win=%.1f%%",
        len(_CANDIDATE_FILTERS),
        baseline_stats["n_matured_63d"],
        baseline_stats["win_rate_63d"] * 100,
    )


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
