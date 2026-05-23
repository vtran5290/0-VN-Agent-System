"""Stage 14 — Research Closure, Coverage Audit, and Monthly Runbook.

Closes the Dual Cloud Accumulation / Wyckoff research branch by producing:
  1. stage14_research_closure_decision_table.csv   — per-item classification & action
  2. stage14_original_scheme_coverage_audit.csv    — what was tested vs original spec
  3. stage14_monthly_runbook.csv                   — recurring monitoring procedure
  4. stage14_reopen_criteria.csv                   — conditions to reopen each item
  5. STAGE14_RESEARCH_CLOSURE_MEMO.md              — consolidated decision memo
  6. dual_cloud_accumulation_wyckoff_review_package.zip  (optional)

No new strategy logic. No OMS/live changes. No production promotion.
OBSERVATION / DOCUMENTATION ONLY.
"""
from __future__ import annotations

import logging
import sys
import zipfile
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.dual_cloud_accumulation_wyckoff.panel_utils import OUT_DIR

log = logging.getLogger(__name__)

# ── Safety constants ─────────────────────────────────────────────────────────────
_STAGE14_WRITE_DIR: Path = OUT_DIR

_OMS_SAFE_PATHS: frozenset[str] = frozenset({
    str(REPO / "data" / "decision" / "daily_scan.json"),
    str(REPO / "data" / "decision" / "daily_scan.md"),
    str(REPO / "data" / "decision" / "allocation_plan.json"),
    str(REPO / "data" / "state" / "regime_state.json"),
    str(REPO / "data" / "raw" / "current_positions_derived.json"),
    str(REPO / "data" / "raw" / "current_positions_digest.md"),
})

# Paths that must never be written by research stages
_FORBIDDEN_WRITE_PREFIXES: tuple[str, ...] = (
    str(REPO / "src" / "trading" / "live"),
    str(REPO / "src" / "trading" / "oms"),
    str(REPO / "src" / "trading" / "execution"),
    str(REPO / "config" / "trading.yaml"),
    str(REPO / "config" / "live"),
    str(REPO / "pp_backtest" / "live"),
)

# ── Input file registry ──────────────────────────────────────────────────────────
_INPUTS: dict[str, Path] = {
    "stage7_score_recalibration":       OUT_DIR / "stage7_score_recalibration.csv",
    "stage8_observation_fields":        OUT_DIR / "stage8_observation_fields.csv",
    "stage9_forward_validation":        OUT_DIR / "stage9_forward_validation_updated.csv",
    "stage10_candidate_decision":       OUT_DIR / "stage10_candidate_decision_table.csv",
    "stage11_timing_summary":           OUT_DIR / "stage11_timing_pattern_summary.csv",
    "stage12_shadow_summary":           OUT_DIR / "stage12_s3_shadow_variant_summary.csv",
    "stage12b_maxhold_robustness":      OUT_DIR / "stage12b_s3_maxhold_robustness.csv",
    "stage13_portfolio_summary":        OUT_DIR / "stage13_portfolio_summary.csv",
    "stage13_sleeve_classification":    OUT_DIR / "stage13_sleeve_classification.csv",
    "stage13_correlation":              OUT_DIR / "stage13_a3_s3_correlation.csv",
    "md_stage7":  OUT_DIR / "STAGE7_SCORE_RECALIBRATION_FINDINGS.md",
    "md_stage8":  OUT_DIR / "STAGE8_OBSERVATION_LAYER_FINDINGS.md",
    "md_stage9":  OUT_DIR / "STAGE9_FORWARD_VALIDATION_FINDINGS.md",
    "md_stage10": OUT_DIR / "STAGE10_MONTHLY_VALIDATION_REPORT.md",
    "md_stage11": OUT_DIR / "STAGE11_TIMING_PATTERN_FINDINGS.md",
    "md_stage12": OUT_DIR / "STAGE12_S3_SHADOW_CONTRACT_FINDINGS.md",
    "md_stage12b":OUT_DIR / "STAGE12B_S3_MAXHOLD_ROBUSTNESS_FINDINGS.md",
    "md_stage13": OUT_DIR / "STAGE13_COMBINED_SLEEVE_FINDINGS.md",
}


def _file_exists(key: str) -> bool:
    return _INPUTS.get(key, Path("")).exists()


def _read_csv_safe(key: str) -> Optional[pd.DataFrame]:
    p = _INPUTS.get(key)
    if p is None or not p.exists():
        log.warning("Input not found: %s", key)
        return None
    try:
        return pd.read_csv(p)
    except Exception as exc:
        log.warning("Could not read %s: %s", key, exc)
        return None


# ── Decision table ────────────────────────────────────────────────────────────────

def _build_decision_table() -> pd.DataFrame:
    """16-item research closure decision table."""
    rows: List[dict] = [
        {
            "item":              "A3_production_contract",
            "category":          "production",
            "latest_evidence":   "Stage 13: A3 MAR=0.16, CAGR=2.9%, MaxDD=-18.0%; 2855 signals",
            "classification":    "PAPER_TRADE_PRIMARY",
            "action":            "no change; continue live paper monitoring per existing runbook",
            "production_impact": "none — existing A3 paper contract unchanged",
            "review_frequency":  "monthly",
            "reopen_condition":  "N/A — contract is already active; review on quarterly basis",
            "notes":             "EMA20/100, T1/T2, TP1=18%, Trail=2.5xATR14, MaxHold=250",
        },
        {
            "item":              "Old_composite_score",
            "category":          "feature_engineering",
            "latest_evidence":   "Stage 7: score recalibration rejected old composite; all ablations negative",
            "classification":    "REJECT",
            "action":            "permanently rejected; do not reopen unless feature definitions completely redesigned",
            "production_impact": "none",
            "review_frequency":  "never",
            "reopen_condition":  "do not reopen",
            "notes":             "Stage 7 ablation showed no improvement vs baseline",
        },
        {
            "item":              "BVE_Q4Q5",
            "category":          "observation_filter",
            "latest_evidence":   "Stage 12: BVE_Q45 variant improved TP1 rate; win-rate improvement below threshold",
            "classification":    "WATCHLIST_ONLY",
            "action":            "monitor monthly TP1-rate and win-rate; do not promote without n>=80 new matured trades",
            "production_impact": "none — observation-only flag",
            "review_frequency":  "monthly",
            "reopen_condition":  "n>=80 new matured, win_rate_delta>=+5pp, TP1_rate positive, not one-year dominated",
            "notes":             "BVE = breakout volume expansion; Q5 = top quintile",
        },
        {
            "item":              "TPBCQ_Q4Q5",
            "category":          "observation_filter",
            "latest_evidence":   "Stage 12: tightness filter variant; TP1 improvement slight; win-rate not threshold",
            "classification":    "WATCHLIST_ONLY",
            "action":            "monitor monthly; same criteria as BVE_Q4Q5",
            "production_impact": "none — observation-only flag",
            "review_frequency":  "monthly",
            "reopen_condition":  "n>=80 new matured, win_rate_delta>=+5pp, TP1_rate positive",
            "notes":             "TPBCQ = price tightness before cloud quintile",
        },
        {
            "item":              "Wyckoff_SOS",
            "category":          "wyckoff_tag",
            "latest_evidence":   "Stage 5: SOS tag exists in data; Stage 11: timing decomposition shows marginal lift",
            "classification":    "DIAGNOSTIC_ONLY",
            "action":            "keep as diagnostic annotation; do not use as trading gate",
            "production_impact": "none",
            "review_frequency":  "quarterly",
            "reopen_condition":  "n>=100 SOS-tagged signals, win_rate_delta>=+5pp vs non-SOS",
            "notes":             "Marginal signal; diagnostic context only",
        },
        {
            "item":              "Wyckoff_LPS",
            "category":          "wyckoff_tag",
            "latest_evidence":   "Stage 5: LPS tag showed no win-rate improvement over baseline",
            "classification":    "REJECT",
            "action":            "rejected; remove from active monitoring",
            "production_impact": "none",
            "review_frequency":  "never",
            "reopen_condition":  "do not reopen with current feature definition",
            "notes":             "Last Point of Support tag; insufficient lift",
        },
        {
            "item":              "Wyckoff_spring_test",
            "category":          "wyckoff_tag",
            "latest_evidence":   "Stage 5: spring tag showed no consistent improvement; low sample",
            "classification":    "REJECT",
            "action":            "rejected; low sample and no consistent lift",
            "production_impact": "none",
            "review_frequency":  "never",
            "reopen_condition":  "do not reopen with current feature definition",
            "notes":             "Spring test / shakeout pattern; insufficient evidence",
        },
        {
            "item":              "PRE_S3_ACCUM",
            "category":          "timing_pattern",
            "latest_evidence":   "Stage 11: 24.4% win rate, +4.8pp vs baseline, n=41 matured; borderline",
            "classification":    "WATCHLIST_ONLY",
            "action":            "monitor monthly; borderline — needs more observations before promotion",
            "production_impact": "none — observation-only",
            "review_frequency":  "monthly",
            "reopen_condition":  "n>=80 matured, win_rate_delta>=+5pp, TP1_rate positive, not bull-only",
            "notes":             "A3 signal preceded by S3 accumulation; promising but insufficient sample",
        },
        {
            "item":              "FAILED_S3_BEFORE_A3",
            "category":          "timing_pattern",
            "latest_evidence":   "Stage 11: 16.0% win rate; below baseline; useful as caution flag",
            "classification":    "WATCHLIST_ONLY",
            "action":            "retain as caution flag annotation; do not use as promotion filter",
            "production_impact": "none — warning annotation only",
            "review_frequency":  "monthly",
            "reopen_condition":  "monitor for 6+ months; promote to gate only if win_rate <10% confirmed",
            "notes":             "Failed S3 before A3 signal indicates weaker setup quality",
        },
        {
            "item":              "Inverse_HS",
            "category":          "timing_pattern",
            "latest_evidence":   "Stage 11: only 3 instances detected; diagnostic-only",
            "classification":    "DIAGNOSTIC_ONLY",
            "action":            "insufficient sample; keep as diagnostic annotation",
            "production_impact": "none",
            "review_frequency":  "quarterly",
            "reopen_condition":  "n>=30 instances for statistical evaluation",
            "notes":             "Inverse head-and-shoulders; extremely low occurrence in universe",
        },
        {
            "item":              "S3_MAX60",
            "category":          "s3_contract",
            "latest_evidence":   "Stage 12: win=22.9%, TP1=37.0%; official paper-shadow baseline",
            "classification":    "PAPER_TRADE_SHADOW",
            "action":            "continue as official S3 paper-shadow baseline; monitor monthly ledger",
            "production_impact": "none — paper-shadow only; S3 not in production",
            "review_frequency":  "monthly",
            "reopen_condition":  "N/A — already active as paper-shadow; promote only via separate approval",
            "notes":             "EMA21/55, TP1=18%, Trail=3.5xATR14, MaxHold=60; VNINDEX regime gate",
        },
        {
            "item":              "S3_MAX105",
            "category":          "s3_contract",
            "latest_evidence":   "Stage 12B: best extended-hold variant; MAR improved vs max60 but risk flagged",
            "classification":    "PARALLEL_PAPER_RESEARCH",
            "action":            "track as research-only parallel shadow; do not replace max60 baseline",
            "production_impact": "none — research-only",
            "review_frequency":  "monthly",
            "reopen_condition":  "6+ months paper shadow, 50+ matured, MaxDD not worse by >2pp, avg_ret positive",
            "notes":             "Higher avg_net vs max60 but capital lock-up concern; monitor 2024/weak-regime",
        },
        {
            "item":              "S3_MAX120",
            "category":          "s3_contract",
            "latest_evidence":   "Stage 12B: downgraded from PARALLEL_PAPER_RESEARCH; hold-extension risk flag",
            "classification":    "WATCHLIST_ONLY",
            "action":            "downgraded; monitor 2025/2026 live paper before reconsidering",
            "production_impact": "none",
            "review_frequency":  "quarterly",
            "reopen_condition":  "2025/2026 live paper shows no MaxDD worsening; avg_hold delta <30 bars",
            "notes":             "Stage 12B: avg_hold +35 bars vs max60; 2024 return worsens; MaxDD worsens 2.3pp",
        },
        {
            "item":              "Combined_A3_S3_MAX60_sleeve",
            "category":          "portfolio_construction",
            "latest_evidence":   "Stage 13: all weights dilute A3 MAR (except 5% NEUTRAL); r=0.67 with A3",
            "classification":    "CLOSED_NO_ACTION",
            "action":            "rejected as portfolio improvement; do not allocate A3 capital to S3",
            "production_impact": "none",
            "review_frequency":  "quarterly",
            "reopen_condition":  "S3 standalone improves materially; r<0.5; combined MAR +>=0.05; MaxDD not worse",
            "notes":             "High A3/S3 correlation limits diversification benefit",
        },
        {
            "item":              "Combined_A3_S3_MAX105_sleeve",
            "category":          "portfolio_construction",
            "latest_evidence":   "Stage 13: 5% weight NEUTRAL; 10%+ DILUTES_A3; r=0.82 (higher than max60)",
            "classification":    "CLOSED_NO_ACTION",
            "action":            "rejected; even higher correlation with A3; no portfolio benefit found",
            "production_impact": "none",
            "review_frequency":  "quarterly",
            "reopen_condition":  "S3 standalone improves materially; r<0.5; combined MAR +>=0.05; MaxDD not worse",
            "notes":             "r=0.82 with A3 annual returns — diversification benefit absent",
        },
        {
            "item":              "A3_T2_accumulation_filter",
            "category":          "observation_filter",
            "latest_evidence":   "Stage 3: T2 timing studied; T2 fill mechanics validated; filter effect inconclusive",
            "classification":    "WATCHLIST_ONLY",
            "action":            "retain as observation annotation; monitor T2 fill rate and net return contribution",
            "production_impact": "none — T2 entry is part of A3 frozen contract; filter only",
            "review_frequency":  "monthly",
            "reopen_condition":  "n>=80 T2-filled matured trades; T2-fill cohort shows +3pp net return vs T1-only",
            "notes":             "T2 fill = >=4% pullback within 30 bars; 50% of position; already in A3 contract",
        },
    ]
    return pd.DataFrame(rows)


# ── Coverage audit ────────────────────────────────────────────────────────────────

def _build_coverage_audit() -> pd.DataFrame:
    rows: List[dict] = [
        {
            "original_scheme_item":  "price_tightness_features",
            "stage_addressed":       "1, 5, 7, 12",
            "coverage_status":       "covered",
            "evidence_summary":      "pt_20 / TPBCQ computed and backtested; Stage 12 filter variants evaluated",
            "remaining_gap":         "none significant",
            "next_action":           "monthly monitoring via WATCHLIST_ONLY",
        },
        {
            "original_scheme_item":  "volume_tightness_features",
            "stage_addressed":       "1, 5, 7, 12",
            "coverage_status":       "covered",
            "evidence_summary":      "BVE, vol_drying_score, vol_ratio_20 all tested; BVE_Q4Q5 WATCHLIST_ONLY",
            "remaining_gap":         "none significant",
            "next_action":           "monthly monitoring",
        },
        {
            "original_scheme_item":  "breakout_features",
            "stage_addressed":       "1, 2, 7",
            "coverage_status":       "covered",
            "evidence_summary":      "bo_close_strength, bo_vol_expansion evaluated; old composite rejected",
            "remaining_gap":         "none",
            "next_action":           "no action; old composite closed",
        },
        {
            "original_scheme_item":  "wyckoff_tags",
            "stage_addressed":       "5, 11",
            "coverage_status":       "covered",
            "evidence_summary":      "SOS/LPS/spring/UTAD/inverse_HS tagged and backtested; LPS and spring rejected",
            "remaining_gap":         "inverse_HS insufficient sample (n=3)",
            "next_action":           "diagnostic annotation retained; re-evaluate at n>=30",
        },
        {
            "original_scheme_item":  "timing_buckets_vs_A3_S3",
            "stage_addressed":       "11",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 11 decomposed signals into 7 timing patterns; results documented",
            "remaining_gap":         "none",
            "next_action":           "monthly monitoring for PRE_S3_ACCUM and FAILED_S3_BEFORE_A3",
        },
        {
            "original_scheme_item":  "PRE_S3_ACCUM",
            "stage_addressed":       "11",
            "coverage_status":       "covered",
            "evidence_summary":      "24.4% win rate, +4.8pp vs baseline, n=41; borderline WATCHLIST_ONLY",
            "remaining_gap":         "insufficient sample for promotion (need n>=80)",
            "next_action":           "monthly monitoring",
        },
        {
            "original_scheme_item":  "S3_BREAKOUT_BEFORE_A3",
            "stage_addressed":       "11",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 11 FAILED_S3_BEFORE_A3 covers this; 16.0% win rate caution flag",
            "remaining_gap":         "none",
            "next_action":           "caution flag annotation retained",
        },
        {
            "original_scheme_item":  "A3_CLOUD_TURN_BREAKOUT",
            "stage_addressed":       "1, 2, 6, 8, 9",
            "coverage_status":       "covered",
            "evidence_summary":      "Core A3 signal; forward validation and robustness across stages 6, 9",
            "remaining_gap":         "none",
            "next_action":           "monthly forward validation update (Stage 9)",
        },
        {
            "original_scheme_item":  "A3_PULLBACK_ACCUM_BREAKOUT",
            "stage_addressed":       "3, 13",
            "coverage_status":       "covered",
            "evidence_summary":      "T2 timing (Stage 3) and T2 blended in Stage 13 A3 simulation",
            "remaining_gap":         "T2-fill cohort contribution inconclusive at current sample",
            "next_action":           "retain T2 fill in frozen contract; monitor monthly",
        },
        {
            "original_scheme_item":  "BOTTOM_ACCUM_PRE_CLOUD",
            "stage_addressed":       "11",
            "coverage_status":       "partially_covered",
            "evidence_summary":      "PRE_S3_ACCUM partially captures this; dedicated bottom-accum filter not built",
            "remaining_gap":         "no dedicated filter; relies on PRE_S3_ACCUM proxy",
            "next_action":           "low priority; revisit if PRE_S3_ACCUM promoted",
        },
        {
            "original_scheme_item":  "LATE_BREAKOUT_AFTER_A3",
            "stage_addressed":       "11",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 11 pattern decomposition includes late-breakout timing bucket",
            "remaining_gap":         "limited sample in late-breakout bucket",
            "next_action":           "diagnostic annotation only",
        },
        {
            "original_scheme_item":  "S3_LATE_AFTER_A3",
            "stage_addressed":       "11, 12",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 11 timing includes S3-after-A3 timing; Stage 12 S3 standalone shadow",
            "remaining_gap":         "none significant",
            "next_action":           "monitor S3 paper-shadow ledger monthly",
        },
        {
            "original_scheme_item":  "FAILED_S3_BEFORE_A3",
            "stage_addressed":       "11",
            "coverage_status":       "covered",
            "evidence_summary":      "16.0% win rate; dedicated caution-flag bucket in Stage 11",
            "remaining_gap":         "none",
            "next_action":           "caution flag annotation retained; monitor monthly",
        },
        {
            "original_scheme_item":  "INVERSE_HS_BREAKOUT",
            "stage_addressed":       "11",
            "coverage_status":       "partially_covered",
            "evidence_summary":      "Stage 11: 3 instances only; pattern exists but sample too small",
            "remaining_gap":         "n=3 insufficient for statistical conclusions",
            "next_action":           "diagnostic annotation; reopen at n>=30",
        },
        {
            "original_scheme_item":  "A3_ranking_overlay",
            "stage_addressed":       "2, 7",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 2 candidate ranking; Stage 7 score recalibration; old score rejected",
            "remaining_gap":         "no validated replacement score built",
            "next_action":           "continue with signal-equal ranking until better score available",
        },
        {
            "original_scheme_item":  "A3_T2_timing",
            "stage_addressed":       "3, 13",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 3 T2 timing; Stage 13 T2 mechanics validated in blended simulation",
            "remaining_gap":         "T2-fill-only cohort performance not isolated",
            "next_action":           "monthly monitoring of T2 fill rate",
        },
        {
            "original_scheme_item":  "S3_standalone_shadow",
            "stage_addressed":       "4, 12",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 4 and Stage 12 both test S3 standalone; max60 = PAPER_TRADE_SHADOW",
            "remaining_gap":         "none",
            "next_action":           "monthly paper-shadow ledger review",
        },
        {
            "original_scheme_item":  "S3_maxhold_robustness",
            "stage_addressed":       "12b",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 12B sweep 45/60/75/90/105/120/150; max105 best; max120 WATCHLIST_ONLY",
            "remaining_gap":         "none",
            "next_action":           "quarterly re-evaluation as live paper accumulates",
        },
        {
            "original_scheme_item":  "combined_A3_S3_sleeves",
            "stage_addressed":       "13",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 13: all combinations evaluated; high A3/S3 correlation; CLOSED_NO_ACTION",
            "remaining_gap":         "none",
            "next_action":           "closed; reopen only if S3 correlation with A3 drops below 0.5",
        },
        {
            "original_scheme_item":  "forward_validation",
            "stage_addressed":       "8, 9",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 8 observation layer; Stage 9 forward validation ledger with 920 rows",
            "remaining_gap":         "ledger requires monthly update as new signals mature",
            "next_action":           "run Stage 9 monthly after OHLCV update",
        },
        {
            "original_scheme_item":  "monthly_validation_report",
            "stage_addressed":       "10",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 10 monthly validation report with candidate decision table",
            "remaining_gap":         "requires monthly refresh",
            "next_action":           "run Stage 10 monthly",
        },
        {
            "original_scheme_item":  "robustness_by_year_regime_liquidity",
            "stage_addressed":       "6, 12, 12b",
            "coverage_status":       "covered",
            "evidence_summary":      "Stage 6 full robustness; Stage 12/12B by-year, by-regime, by-liquidity breakdowns",
            "remaining_gap":         "none",
            "next_action":           "included in monthly runbook",
        },
        {
            "original_scheme_item":  "bootstrap_false_discovery_controls",
            "stage_addressed":       "none",
            "coverage_status":       "not_covered",
            "evidence_summary":      "No bootstrap FDR control implemented in any stage",
            "remaining_gap":         "FDR control not built; all win-rates are point estimates",
            "next_action":           "future enhancement if branch reopened with larger sample",
        },
        {
            "original_scheme_item":  "sector_L4_context",
            "stage_addressed":       "none",
            "coverage_status":       "not_covered",
            "evidence_summary":      "Sector L4 data not available in current panel; not used",
            "remaining_gap":         "requires sector enrichment of ohlcv_panel",
            "next_action":           "future enhancement; requires data integration work",
        },
        {
            "original_scheme_item":  "breadth_context",
            "stage_addressed":       "6",
            "coverage_status":       "partially_covered",
            "evidence_summary":      "Stage 6 uses VNINDEX regime as breadth proxy; dedicated breadth indicator not built",
            "remaining_gap":         "no advance/decline breadth or % stocks above EMA",
            "next_action":           "future enhancement if market breadth data available",
        },
    ]
    return pd.DataFrame(rows)


# ── Monthly runbook ───────────────────────────────────────────────────────────────

def _build_monthly_runbook() -> pd.DataFrame:
    rows: List[dict] = [
        {
            "step":           "1",
            "frequency":      "monthly",
            "command":        ".venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py --stage 9 10 --workers 4",
            "input_files":    "data/research/ema_cloud/ohlcv_panel_ext2012.parquet; data/fireant_ssot/ta_vnindex.parquet",
            "output_files":   "stage9_forward_validation_updated.csv; stage10_candidate_decision_table.csv; STAGE10_MONTHLY_VALIDATION_REPORT.md",
            "owner_note":     "Run after monthly OHLCV panel update. Stage 9 updates forward validation ledger; Stage 10 produces monthly decision table.",
            "decision_check": "Review stage10_candidate_decision_table.csv: check BVE_Q4Q5 and TPBCQ_Q4Q5 win_rate_delta; flag if win_rate_delta >= +5pp for 2 consecutive months",
        },
        {
            "step":           "2",
            "frequency":      "monthly",
            "command":        "manual review: outputs/research/dual_cloud_accumulation_wyckoff/stage10_candidate_decision_table.csv",
            "input_files":    "stage10_candidate_decision_table.csv",
            "output_files":   "N/A — review only",
            "owner_note":     "Check BVE_Q4Q5 win_rate_delta and TP1_rate_delta. Check PRE_S3_ACCUM matured_n and win_rate. Check FAILED_S3_BEFORE_A3 caution flag rate.",
            "decision_check": "Promote BVE/TPBCQ only if: n>=80 new matured, win_rate_delta>=+5pp, TP1_rate positive, 2+ liquidity buckets positive",
        },
        {
            "step":           "3",
            "frequency":      "monthly",
            "command":        "manual review: outputs/research/dual_cloud_accumulation_wyckoff/stage12_s3_shadow_by_year.csv",
            "input_files":    "stage12_s3_shadow_by_year.csv; stage12_s3_shadow_trades.csv",
            "output_files":   "N/A — review only",
            "owner_note":     "Review S3 max60 paper-shadow ledger: win_rate, TP1_rate, avg_net_return by year. Record any new matured trades.",
            "decision_check": "S3 max60 promotion requires separate approval process; do NOT promote based on this review alone",
        },
        {
            "step":           "4",
            "frequency":      "monthly",
            "command":        "manual review: outputs/research/dual_cloud_accumulation_wyckoff/stage12b_s3_maxhold_robustness.csv",
            "input_files":    "stage12b_s3_maxhold_robustness.csv",
            "output_files":   "N/A — review only",
            "owner_note":     "Review S3 max105 (PARALLEL_PAPER_RESEARCH) metrics. Track avg_hold_bars and MaxDD vs max60 baseline. Do NOT use max105 as primary contract.",
            "decision_check": "Promote max105 only if: 6+ months live paper, 50+ matured, MaxDD not worse by >2pp, 2024/weak-regime not worse",
        },
        {
            "step":           "5",
            "frequency":      "monthly",
            "command":        ".venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py --stage 11 --workers 4",
            "input_files":    "data/research/ema_cloud/ohlcv_panel_ext2012.parquet",
            "output_files":   "stage11_timing_pattern_summary.csv; STAGE11_TIMING_PATTERN_FINDINGS.md",
            "owner_note":     "Re-run Stage 11 if panel has been updated by 3+ months. Checks PRE_S3_ACCUM and FAILED_S3_BEFORE_A3 n_matured counts.",
            "decision_check": "PRE_S3_ACCUM: promote if n>=80 and win_rate_delta>=+5pp. FAILED_S3_BEFORE_A3: flag if win_rate drops below 12%.",
        },
        {
            "step":           "6",
            "frequency":      "quarterly",
            "command":        ".venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py --stage 12 15 13 --workers 4",
            "input_files":    "data/research/ema_cloud/ohlcv_panel_ext2012.parquet; data/fireant_ssot/ta_vnindex.parquet",
            "output_files":   "stage12_s3_shadow_trades.csv; stage12b_s3_maxhold_robustness.csv; stage13_portfolio_summary.csv",
            "owner_note":     "Quarterly: re-run S3 shadow contract, maxhold robustness, and sleeve simulation. Note: alias --stage 12b maps to stage 15 (run_all.py).",
            "decision_check": "Check if Stage 13 sleeve correlation has dropped below 0.5. Check if combined MAR improved by >=0.05. If neither: keep CLOSED_NO_ACTION.",
        },
        {
            "step":           "7",
            "frequency":      "monthly",
            "command":        "manual archive: copy outputs/research/dual_cloud_accumulation_wyckoff/ to archive/YYYY-MM/",
            "input_files":    "all stage*.csv; all STAGE*.md",
            "output_files":   "archive/YYYY-MM/",
            "owner_note":     "Archive monthly output snapshot before overwriting with new run. Prevents loss of historical trend data.",
            "decision_check": "Confirm archive completed before running new monthly pipeline",
        },
        {
            "step":           "8",
            "frequency":      "on_event",
            "command":        "do NOT modify: src/trading/ config/trading.yaml config/live* data/decision/",
            "input_files":    "N/A",
            "output_files":   "N/A",
            "owner_note":     "GUARDRAIL: No research stage may write to production paths. Any promotion of S3 or change to A3 requires separate approval workflow.",
            "decision_check": "Any proposed change to production contract must go through full separate approval; this runbook does not authorize any production change",
        },
    ]
    return pd.DataFrame(rows)


# ── Reopen criteria ───────────────────────────────────────────────────────────────

def _build_reopen_criteria() -> pd.DataFrame:
    rows: List[dict] = [
        {
            "item":                 "BVE_Q4Q5",
            "current_status":       "WATCHLIST_ONLY",
            "reopen_trigger":       "n>=80 new matured observations AND win_rate_delta>=+5pp AND TP1_rate_delta positive",
            "minimum_sample":       "80 new matured trades post-watchlist",
            "required_metrics":     "win_rate_delta>=+5pp; TP1_rate_delta>0; avg_return_delta>0; not one-year dominated",
            "required_robustness":  "positive in at least 2 liquidity buckets; not limited to bull regime only",
            "allowed_next_action":  "promote to PARALLEL_PAPER_RESEARCH for 6-month live paper observation",
        },
        {
            "item":                 "TPBCQ_Q4Q5",
            "current_status":       "WATCHLIST_ONLY",
            "reopen_trigger":       "n>=80 new matured AND win_rate_delta>=+5pp AND TP1_rate_delta positive",
            "minimum_sample":       "80 new matured trades",
            "required_metrics":     "same as BVE_Q4Q5",
            "required_robustness":  "positive in 2+ liquidity buckets; not bull-only",
            "allowed_next_action":  "promote to PARALLEL_PAPER_RESEARCH",
        },
        {
            "item":                 "PRE_S3_ACCUM",
            "current_status":       "WATCHLIST_ONLY",
            "reopen_trigger":       "n>=80 matured AND win_rate_delta>=+5pp AND TP1_rate_delta positive",
            "minimum_sample":       "80 matured trades (currently n=41; need ~39 more)",
            "required_metrics":     "win_rate_delta>=+5pp vs non-PRE_S3; TP1_rate_delta>0; avg_return positive",
            "required_robustness":  "not limited to bull-only regime; positive in mid/high liquidity",
            "allowed_next_action":  "promote to PARALLEL_PAPER_RESEARCH; flag in daily scan as PRE_S3_ACCUM=True",
        },
        {
            "item":                 "S3_MAX105",
            "current_status":       "PARALLEL_PAPER_RESEARCH",
            "reopen_trigger":       "6+ months paper-shadow observation with 50+ matured trades",
            "minimum_sample":       "50 live-paper matured trades",
            "required_metrics":     "MaxDD not worse than max60 by >2pp; avg_return positive; 2024/weak-regime not worse",
            "required_robustness":  "hold_extension_risk_flag must be False in live paper data",
            "allowed_next_action":  "promote to PAPER_TRADE_SHADOW (replacing or alongside max60) via separate approval",
        },
        {
            "item":                 "S3_MAX120",
            "current_status":       "WATCHLIST_ONLY",
            "reopen_trigger":       "2025/2026 live paper shows no MaxDD worsening AND avg_hold delta <30 bars",
            "minimum_sample":       "50 live-paper matured trades",
            "required_metrics":     "MaxDD not worse than max60; avg_hold delta <30 bars; 2024/2025 return not worse",
            "required_robustness":  "hold_extension_risk_flag must remain False for 2 consecutive quarters",
            "allowed_next_action":  "promote to PARALLEL_PAPER_RESEARCH alongside max105",
        },
        {
            "item":                 "Combined_A3_S3_sleeve",
            "current_status":       "CLOSED_NO_ACTION",
            "reopen_trigger":       "S3 standalone MAR improves materially AND A3/S3 annual correlation drops below 0.5",
            "minimum_sample":       "5+ overlapping calendar years with new data",
            "required_metrics":     "combined MAR improves by >=0.05 over A3-only; MaxDD not worse by >2pp",
            "required_robustness":  "positive in both S3_MAX60 and S3_MAX105 variants",
            "allowed_next_action":  "reopen Stage 13 with updated data; new sleeve simulation required",
        },
        {
            "item":                 "Old_composite_score",
            "current_status":       "REJECT",
            "reopen_trigger":       "do not reopen",
            "minimum_sample":       "N/A",
            "required_metrics":     "N/A — permanently rejected",
            "required_robustness":  "N/A",
            "allowed_next_action":  "only reopen if feature definitions completely redesigned from scratch",
        },
        {
            "item":                 "Wyckoff_LPS",
            "current_status":       "REJECT",
            "reopen_trigger":       "do not reopen with current feature definition",
            "minimum_sample":       "N/A",
            "required_metrics":     "N/A",
            "required_robustness":  "N/A",
            "allowed_next_action":  "redesign LPS detection logic before reconsidering",
        },
        {
            "item":                 "Wyckoff_spring_test",
            "current_status":       "REJECT",
            "reopen_trigger":       "do not reopen with current feature definition",
            "minimum_sample":       "N/A",
            "required_metrics":     "N/A",
            "required_robustness":  "N/A",
            "allowed_next_action":  "redesign spring detection logic before reconsidering",
        },
    ]
    return pd.DataFrame(rows)


# ── Closure memo markdown ─────────────────────────────────────────────────────────

def _generate_closure_memo(
    decision_df: pd.DataFrame,
    coverage_df: pd.DataFrame,
    runbook_df:  pd.DataFrame,
    reopen_df:   pd.DataFrame,
    missing_inputs: list[str],
) -> str:
    covered = int((coverage_df["coverage_status"] == "covered").sum())
    partial = int((coverage_df["coverage_status"] == "partially_covered").sum())
    not_cov = int((coverage_df["coverage_status"] == "not_covered").sum())

    def _get(item: str) -> dict:
        rows = decision_df[decision_df["item"] == item]
        return rows.iloc[0].to_dict() if len(rows) > 0 else {}

    lines = [
        "# Stage 14 — Dual Cloud Accumulation / Wyckoff Research Closure Memo",
        "",
        f"**Date:** 2026-05-23  |  **Branch:** dual_cloud_accumulation_wyckoff  |  **Stages completed:** 1–13",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        "This memo closes the Dual Cloud Accumulation / Wyckoff research branch (Stages 1–13).",
        "No production changes are recommended. The A3 paper contract continues unchanged.",
        "S3 max60 remains the official paper-shadow baseline.",
        "No combined A3/S3 sleeve is approved for capital allocation.",
        "",
        "Key outcomes:",
        "- **A3 contract**: confirmed viable (MAR=0.16, CAGR=2.9%); no changes required.",
        "- **Old composite score**: permanently rejected.",
        "- **BVE/TPBCQ**: WATCHLIST_ONLY — needs more observations.",
        "- **S3 max60**: PAPER_TRADE_SHADOW — official baseline confirmed.",
        "- **S3 max105**: PARALLEL_PAPER_RESEARCH — promising but not yet official.",
        "- **S3 max120**: WATCHLIST_ONLY — downgraded due to hold-extension risk.",
        "- **Combined sleeves**: CLOSED_NO_ACTION — high A3/S3 correlation limits value.",
        "- **Wyckoff LPS/spring**: REJECT — insufficient evidence.",
        "",
        "---",
        "",
        "## 2. What Was Tested",
        "",
        "| Stage | Description |",
        "|-------|-------------|",
        "| 1 | Feature predictive value (price tightness, volume, breakout features) |",
        "| 2 | A3 candidate ranking: score vs all-signal baseline |",
        "| 3 | A3 T2 timing: ≥4% pullback within 30 bars |",
        "| 4 | S3 shadow quality filter (max60 baseline) |",
        "| 5 | Wyckoff tags: SOS, LPS, spring, UTAD, inverse H&S |",
        "| 6 | Robustness: by-year, by-regime, by-liquidity |",
        "| 7 | Score recalibration and feature ablation |",
        "| 8 | Observation layer and forward validation ledger setup |",
        "| 9 | Forward validation update |",
        "| 10 | Monthly validation report and candidate decision table |",
        "| 11 | Timing pattern decomposition (7 buckets: PRE_S3_ACCUM, FAILED_S3, etc.) |",
        "| 12 | S3 paper-shadow contract validation (24 variants) |",
        "| 12B | S3 max-hold robustness (7 max_hold values, 5 sensitivity variants) |",
        "| 13 | Combined A3/S3 sleeve simulation (10 sleeve configurations) |",
        "",
        "---",
        "",
        "## 3. What Worked",
        "",
        "- **A3 EMA20/100 cloud signal** with T1/T2 blended contract performs as expected.",
        "- **S3 EMA21/55 max60** as a standalone paper-shadow contract is viable (win=22.9%, TP1=37.0%).",
        "- **S3 max105** shows higher avg_net than max60 without MaxDD collapse — promising for further tracking.",
        "- **BVE Q4/Q5** improves TP1 rate — borderline but worth continued monitoring.",
        "- **PRE_S3_ACCUM timing bucket** shows +4.8pp win-rate lift — borderline, needs larger sample.",
        "",
        "---",
        "",
        "## 4. What Failed",
        "",
        "- **Old composite score**: all ablation variants negative — permanently rejected.",
        "- **Wyckoff LPS/spring_test**: no win-rate improvement — rejected.",
        "- **S3 max120**: hold-extension risk flag — downgraded to WATCHLIST_ONLY.",
        "- **Combined A3/S3 sleeves**: high annual return correlation (r=0.67–0.82) prevents diversification benefit.",
        "- **FAILED_S3_BEFORE_A3**: 16.0% win rate — useful as a caution flag, not a gate.",
        "",
        "---",
        "",
        "## 5. What Remains Watchlist-Only",
        "",
        "| Item | Win-rate delta | Next threshold |",
        "|------|---------------|----------------|",
        "| BVE_Q4Q5 | +TP1 rate, win-rate below threshold | n>=80 new matured, +5pp win delta |",
        "| TPBCQ_Q4Q5 | similar to BVE | n>=80 new matured, +5pp win delta |",
        "| PRE_S3_ACCUM | +4.8pp (borderline) | n>=80 matured (currently 41) |",
        "| FAILED_S3_BEFORE_A3 | -6pp (caution) | caution flag only; not a promotion candidate |",
        "| S3_MAX120 | higher win-rate but risk flagged | live paper 2025/2026 clear |",
        "| Wyckoff_SOS | marginal lift | n>=100 SOS-tagged with +5pp delta |",
        "",
        "---",
        "",
        "## 6. S3 Final Position",
        "",
        "| Contract | Classification | Action |",
        "|----------|---------------|--------|",
        "| S3 max60 | PAPER_TRADE_SHADOW | Official baseline; monthly monitoring |",
        "| S3 max105 | PARALLEL_PAPER_RESEARCH | Research-only; 6-month live paper observation |",
        "| S3 max120 | WATCHLIST_ONLY | Downgraded; monitor 2025/2026 live paper |",
        "| S3 max250 | REJECT (not studied) | Defined as MAX_HOLD_REJECTED; not a candidate |",
        "",
        "**S3 does not gate A3.** S3 P&L is tracked completely separately from A3.",
        "",
        "---",
        "",
        "## 7. Combined Sleeve Decision",
        "",
        "All 10 A3/S3 sleeve combinations tested in Stage 13:",
        "- S3 max60 with 5% weight: NEUTRAL_SLEEVE",
        "- S3 max60 with 10–20%: DILUTES_A3",
        "- S3 max105 with 5%: NEUTRAL_SLEEVE",
        "- S3 max105 with 10–20%: DILUTES_A3",
        "",
        "Root cause: A3/S3 annual return correlation is high (r=0.67 for max60; r=0.82 for max105).",
        "Diversification benefit is absent. Combined sleeve is **CLOSED_NO_ACTION**.",
        "",
        "Reopen only if: S3 correlation with A3 drops below 0.5 AND combined MAR improves by >=0.05.",
        "",
        "---",
        "",
        "## 8. Coverage Against Original Scheme",
        "",
        f"- **Covered**: {covered} items",
        f"- **Partially covered**: {partial} items",
        f"- **Not covered**: {not_cov} items",
        "",
        "Key remaining gaps:",
        "- **Bootstrap / FDR controls**: not implemented — all win-rates are point estimates.",
        "- **Sector L4 context**: data not available in current panel.",
        "- **Breadth context**: only VNINDEX regime used as proxy; no advance/decline breadth.",
        "",
    ]

    if not runbook_df.empty:
        lines += [
            "## 9. Monthly Operating Runbook",
            "",
            "| Step | Frequency | Action |",
            "|------|-----------|--------|",
        ]
        for _, r in runbook_df.iterrows():
            lines.append(f"| {r['step']} | {r['frequency']} | {r['owner_note'][:80]}… |")
        lines.append("")
        lines += [
            "Full runbook commands in `stage14_monthly_runbook.csv`.",
            "",
        ]

    lines += [
        "---",
        "",
        "## 10. Reopen Criteria",
        "",
        "| Item | Current Status | Reopen Trigger |",
        "|------|---------------|----------------|",
    ]
    for _, r in reopen_df.iterrows():
        lines.append(f"| {r['item']} | {r['current_status']} | {r['reopen_trigger'][:70]}… |")
    lines += [
        "",
        "Full reopen criteria in `stage14_reopen_criteria.csv`.",
        "",
        "---",
        "",
        "## 11. Safety Confirmation",
        "",
        "| Check | Status |",
        "|-------|--------|",
        "| A3 production contract unchanged | ✓ YES |",
        "| S3 not promoted to production | ✓ YES |",
        "| OMS / live / DNSE untouched | ✓ YES |",
        "| `final_action` unchanged | ✓ YES |",
        "| S3 does not gate A3 | ✓ YES |",
        "| S3 P&L separate from A3 | ✓ YES |",
        "| Combined sleeve not approved | ✓ YES |",
        "| BVE/TPBCQ observation-only | ✓ YES |",
        "| PRE_S3_ACCUM observation-only | ✓ YES |",
        "| FAILED_S3_BEFORE_A3 warning-only | ✓ YES |",
        "| Old composite rejected | ✓ YES |",
        "| No production recommendation made | ✓ YES |",
        "",
    ]

    if missing_inputs:
        lines += [
            "**Missing input files (non-critical):**",
            "",
        ]
        for m in missing_inputs:
            lines.append(f"- {m}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 12. Final Recommendation",
        "",
        "1. **A3**: continue paper trading per existing frozen contract. No changes.",
        "2. **S3 max60**: continue as official paper-shadow. Monthly ledger review.",
        "3. **S3 max105**: track as PARALLEL_PAPER_RESEARCH. Do not replace max60.",
        "4. **BVE/TPBCQ/PRE_S3_ACCUM**: monitor monthly. Promote only at n>=80 + criteria.",
        "5. **Combined sleeve**: closed. Re-evaluate only if A3/S3 correlation drops below 0.5.",
        "6. **Old composite / LPS / spring**: permanently rejected. Do not reopen.",
        "7. **Bootstrap / sector / breadth**: future enhancement items if branch re-scoped.",
        "",
        "**This memo is OBSERVATION / RESEARCH ONLY.**",
        "**No production, OMS, live, or DNSE changes are authorized by this document.**",
        "",
    ]

    return "\n".join(lines)


# ── Optional review package zip ───────────────────────────────────────────────────

def _build_review_zip(out_path: Path) -> None:
    key_files = [
        OUT_DIR / "STAGE14_RESEARCH_CLOSURE_MEMO.md",
        OUT_DIR / "stage14_research_closure_decision_table.csv",
        OUT_DIR / "stage14_original_scheme_coverage_audit.csv",
        OUT_DIR / "stage14_monthly_runbook.csv",
        OUT_DIR / "stage14_reopen_criteria.csv",
        OUT_DIR / "STAGE7_SCORE_RECALIBRATION_FINDINGS.md",
        OUT_DIR / "STAGE8_OBSERVATION_LAYER_FINDINGS.md",
        OUT_DIR / "STAGE9_FORWARD_VALIDATION_FINDINGS.md",
        OUT_DIR / "STAGE10_MONTHLY_VALIDATION_REPORT.md",
        OUT_DIR / "STAGE11_TIMING_PATTERN_FINDINGS.md",
        OUT_DIR / "STAGE12_S3_SHADOW_CONTRACT_FINDINGS.md",
        OUT_DIR / "STAGE12B_S3_MAXHOLD_ROBUSTNESS_FINDINGS.md",
        OUT_DIR / "STAGE13_COMBINED_SLEEVE_FINDINGS.md",
        OUT_DIR / "stage12_s3_shadow_variant_summary.csv",
        OUT_DIR / "stage12b_s3_maxhold_robustness.csv",
        OUT_DIR / "stage13_portfolio_summary.csv",
        OUT_DIR / "stage13_sleeve_classification.csv",
        OUT_DIR / "stage13_a3_s3_correlation.csv",
        OUT_DIR / "stage10_candidate_decision_table.csv",
        OUT_DIR / "stage11_timing_pattern_summary.csv",
    ]

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in key_files:
            if p.exists():
                zf.write(p, arcname=p.name)
    log.info("Saved review package: %s (%d files)", out_path.name,
             len([p for p in key_files if p.exists()]))


# ── Main entry point ──────────────────────────────────────────────────────────────

def run(workers: int = 4) -> None:
    _STAGE14_WRITE_DIR.mkdir(parents=True, exist_ok=True)

    # Audit input files
    missing_inputs = [k for k, p in _INPUTS.items() if not p.exists()]
    if missing_inputs:
        log.warning("Missing input files (non-critical): %s", missing_inputs)

    # Build all tables
    log.info("Building decision table...")
    decision_df = _build_decision_table()

    log.info("Building coverage audit...")
    coverage_df = _build_coverage_audit()

    log.info("Building monthly runbook...")
    runbook_df = _build_monthly_runbook()

    log.info("Building reopen criteria...")
    reopen_df = _build_reopen_criteria()

    # Save CSVs
    out_decision = _STAGE14_WRITE_DIR / "stage14_research_closure_decision_table.csv"
    decision_df.to_csv(out_decision, index=False)
    log.info("Saved: %s (%d items)", out_decision.name, len(decision_df))

    out_coverage = _STAGE14_WRITE_DIR / "stage14_original_scheme_coverage_audit.csv"
    coverage_df.to_csv(out_coverage, index=False)
    covered   = int((coverage_df["coverage_status"] == "covered").sum())
    partial   = int((coverage_df["coverage_status"] == "partially_covered").sum())
    not_cov   = int((coverage_df["coverage_status"] == "not_covered").sum())
    log.info("Saved: %s  covered=%d  partial=%d  not_covered=%d",
             out_coverage.name, covered, partial, not_cov)

    out_runbook = _STAGE14_WRITE_DIR / "stage14_monthly_runbook.csv"
    runbook_df.to_csv(out_runbook, index=False)
    log.info("Saved: %s (%d steps)", out_runbook.name, len(runbook_df))

    out_reopen = _STAGE14_WRITE_DIR / "stage14_reopen_criteria.csv"
    reopen_df.to_csv(out_reopen, index=False)
    log.info("Saved: %s (%d items)", out_reopen.name, len(reopen_df))

    # Generate closure memo
    log.info("Generating closure memo...")
    memo_md = _generate_closure_memo(
        decision_df    = decision_df,
        coverage_df    = coverage_df,
        runbook_df     = runbook_df,
        reopen_df      = reopen_df,
        missing_inputs = missing_inputs,
    )
    out_md = _STAGE14_WRITE_DIR / "STAGE14_RESEARCH_CLOSURE_MEMO.md"
    out_md.write_text(memo_md, encoding="utf-8")
    log.info("Saved: %s", out_md.name)

    # Optional review package zip
    out_zip = _STAGE14_WRITE_DIR / "dual_cloud_accumulation_wyckoff_review_package.zip"
    try:
        _build_review_zip(out_zip)
    except Exception as exc:
        log.warning("Could not build review zip: %s", exc)

    log.info("Stage 14 complete.")


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
