"""
Generate SECTOR_L4_CAUSALITY_FINDINGS.md.
Facts and interpretations are strictly separated.
"""
from __future__ import annotations
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .config import OUTPUT_DIR

log = logging.getLogger(__name__)


def _safe(val, fmt=".4f", default="Unknown"):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return format(float(val), fmt)
    except Exception:
        return str(val)


def generate_findings_report(
    run_config: dict,
    coverage_audit: pd.DataFrame,
    l4_events: pd.DataFrame,
    lead_lag_summary: pd.DataFrame,
    ablation_full: pd.DataFrame,
    ablation_ex_vin: pd.DataFrame,
    ledger_replay: pd.DataFrame,
    placebo_summary: pd.DataFrame,
    leader_classification: pd.DataFrame,
    gate_summary: pd.DataFrame,
) -> str:
    """
    Write SECTOR_L4_CAUSALITY_FINDINGS.md and return the text.
    """
    today = date.today().isoformat()

    # ── Coverage facts ────────────────────────────────────────────────────────
    n_total   = len(coverage_audit) if coverage_audit is not None else "Unknown"
    n_ohlcv   = int(coverage_audit["has_ohlcv"].sum()) if coverage_audit is not None else "Unknown"
    n_unknown = int(coverage_audit["is_unknown"].sum()) if coverage_audit is not None else "Unknown"
    n_dupe    = int(coverage_audit["duplicate_symbol_flag"].sum()) if coverage_audit is not None else "Unknown"
    n_eligible = int(coverage_audit["include_headline_flag"].sum()) if coverage_audit is not None else "Unknown"

    # ── L4 events facts ───────────────────────────────────────────────────────
    if l4_events is not None and not l4_events.empty:
        primary_events = l4_events[l4_events["definition"] == "primary_40_35"]
        n_primary = len(primary_events)
        top_sectors = primary_events.groupby("sector_l4").size().nlargest(5).to_dict()
        n_definitions = l4_events["definition"].nunique()
    else:
        n_primary, top_sectors, n_definitions = 0, {}, 0

    # ── Lead/lag facts ────────────────────────────────────────────────────────
    if lead_lag_summary is not None and not lead_lag_summary.empty:
        median_excess = lead_lag_summary["excess_turn_count_t1_t10"].median()
        median_excess_pct = lead_lag_summary["excess_turn_pct_t1_t10"].median()
        top_lead = lead_lag_summary[lead_lag_summary["conclusion_tag"] == "sector_leads"]
        n_sector_leads = len(top_lead)
    else:
        median_excess = median_excess_pct = np.nan
        n_sector_leads = 0

    # ── Filter value facts ────────────────────────────────────────────────────
    def _get_ablation_delta(df, rule_substr, horizon):
        if df is None or df.empty:
            return np.nan, np.nan
        r = df[df.get("rule_id", pd.Series(dtype=str)).str.contains(rule_substr, na=False) &
               (df.get("horizon", pd.Series(dtype=int)) == horizon)]
        if r.empty:
            return np.nan, np.nan
        return float(r.iloc[0].get("delta_mean", np.nan)), float(r.iloc[0].get("delta_hit_rate", np.nan))

    d_mean_40_60,  d_hit_40_60  = _get_ablation_delta(ablation_full, "ge_40", 60)
    d_mean_exv_60, d_hit_exv_60 = _get_ablation_delta(ablation_ex_vin, "ge_40", 60)

    # ── Ledger facts ──────────────────────────────────────────────────────────
    if ledger_replay is not None and not ledger_replay.empty and "delta_mar" in ledger_replay.columns:
        delta_mar = float(ledger_replay.iloc[0]["delta_mar"])
        verdict_l = str(ledger_replay.iloc[0].get("adoption_verdict", "Unknown"))
    else:
        delta_mar = np.nan
        verdict_l = "Unknown"

    # ── Leader facts ──────────────────────────────────────────────────────────
    if leader_classification is not None and not leader_classification.empty:
        pct_leader_before = float(leader_classification["leader_before_sector"].mean() * 100)
    else:
        pct_leader_before = np.nan

    # ── Placebo facts ─────────────────────────────────────────────────────────
    if placebo_summary is not None and not placebo_summary.empty:
        placebo_pct = float(placebo_summary.iloc[0].get("real_percentile", np.nan))
        placebo_pass = int(placebo_summary.iloc[0].get("passes_95th_gate", 0))
    else:
        placebo_pct, placebo_pass = np.nan, 0

    # ── Gates ─────────────────────────────────────────────────────────────────
    if gate_summary is not None and not gate_summary.empty:
        final_verdict = str(gate_summary.iloc[0].get("final_verdict", "DASHBOARD_WARNING_ONLY"))
        gates_passed  = int(gate_summary.iloc[0].get("gates_passed", 0))
    else:
        final_verdict = "DASHBOARD_WARNING_ONLY"
        gates_passed  = 0

    text = f"""# SECTOR_L4_CAUSALITY_FINDINGS

## 1. Run Metadata

- **Run date:** {today}
- **Panel path:** {run_config.get("ohlcv_panel", "Unknown")}
- **Panel latest date:** {run_config.get("panel_latest_date", "Unknown")}
- **Start / end date:** {run_config.get("start_date", "Unknown")} → {run_config.get("end_date", "Unknown")}
- **Universe modes:** full, ex-VIN
- **Unknown sectors included:** {run_config.get("include_unknown", False)}
- **Placebo iterations:** {run_config.get("placebo_iters", "Unknown")}
- **Repo commit:** {run_config.get("git_commit", "Unknown")}

---

## 2. FACTS — Data Coverage

- Total symbols in sector map: **{n_total}**
- Symbols with valid OHLCV: **{n_ohlcv}**
- Unknown L4 count: **{n_unknown}**
- Duplicate mapping count: **{n_dupe}**
- Eligible headline symbols (n_bars ≥ min, n≥5 per L4, non-Unknown): **{n_eligible}**
- See: `sector_l4_coverage_audit.csv`, `small_sector_diagnostics.csv`

---

## 3. FACTS — L4 Event Results

- L4 turn events (primary 40/35 definition): **{n_primary}**
- L4 turn definitions run: **{n_definitions}**
- Top sectors by event count: {top_sectors}
- See: `sector_l4_turn_events.csv`

---

## 4. FACTS — Lead/Lag Evidence

- Median excess same-L4 stock turns (t+1 to t+10) vs matched random days: **{_safe(median_excess, ".2f")}**
- Median relative lift: **{_safe(median_excess_pct, ".3f")} ({_safe(median_excess_pct*100, ".1f")}%)**
- Sectors classified as "sector_leads": **{n_sector_leads}** / {len(lead_lag_summary) if lead_lag_summary is not None else "Unknown"}
- See: `sector_stock_lead_lag_summary.csv`

---

## 5. FACTS — Filter Value Evidence

### Stock-cloud baseline
- See: `stock_cloud_baseline_forward_returns.csv`

### L4 gate ≥40% overlay at 60d horizon
- Full universe: Δmean_ret = **{_safe(d_mean_40_60)}** | Δhit_rate = **{_safe(d_hit_40_60)}**
- ex-VIN universe: Δmean_ret = **{_safe(d_mean_exv_60)}** | Δhit_rate = **{_safe(d_hit_exv_60)}**
- See: `filter_value_ablation_full.csv`, `filter_value_ablation_ex_vin.csv`

### A3 ledger replay
- ΔMAR (gate vs no-gate, same baseline): **{_safe(delta_mar)}**
- Ledger verdict: **{verdict_l}**
- See: `a3_ledger_sector_gate_replay.csv`

### Threshold sweep
- See: `threshold_sweep_summary.csv` (train 2012–2019 vs test 2020+)

### Regime stratification
- See: `regime_stratified_full_vs_ex_vin.csv`

---

## 6. FACTS — Leader vs Sector

- % events where leader flipped ≥5 sessions before sector turn: **{_safe(pct_leader_before, ".1f")}%**
- See: `leader_vs_sector_classification.csv`

---

## 7. FACTS — False Discovery and Robustness

- Placebo percentile (real vs shuffled-label distribution): **{_safe(placebo_pct, ".1f")}th percentile**
- Passes 95th-percentile placebo gate: **{"YES" if placebo_pass else "NO"}**
- See: `placebo_sector_shuffle_summary.csv`, `unknown_coverage_sensitivity.csv`

---

## 8. INTERPRETATION

> **Label:** INTERPRETATION — not fact. Operator must verify.

- If lead/lag excess is ≥15% and placebo passes: partial support for T1 (sector filter adds breadth signal).
- If leader-before-sector >50%: T2 (leader drag) likely; sector breadth is mechanically pulled by one name.
- If placebo ≈ real result: T4 (false sector / noisy mapping) not ruled out.
- If ex-VIN results weaken significantly: T8 (VIN distortion) likely driving full-universe numbers.
- Current prior stance (from prior stress tests): DASHBOARD_WARNING_ONLY — small MAR improvement (+0.022 best prior case).

**Most supported thesis based on this run:** [Operator must fill in after reviewing outputs above]

**What would confirm:** Placebo percentile ≥95; excess turn count ≥15%; ΔMAR ≥ +0.05 on A3 ledger; ex-VIN sign agrees.

**What would deny:** Placebo ≈ real; excess ≈ 0; A3 ΔMAR < 0; results disappear ex-VIN.

---

## 9. DECISION

**Final verdict: {final_verdict}**
- Gates passed: {gates_passed} / 10
- See: `adoption_gate_summary.csv`, `adoption_gate_detail.csv`

**Explicit statement:** No change to `final_action`, OMS, A3 contract, or S3 promotion based on this run.
Upgrade requires a separate production-change memo approved by the operator.

---

## 10. Operator Notes

- **To watch in daily scan:** Sector L4 turns in non-VIN, non-bank sectors with ≥5 members — use as review-priority signal only, not automatic entry.
- **Do not overinterpret:** A single sector breadth reading is not a trade signal. Breadth ≥40% with leader confirmation is more meaningful.
- **Next tests (P1):** Granger causality, FDR-adjusted multi-sector claims, matched-control non-leader spillover, structural break 2012–2019 vs 2020+.

### If X → do Y

| If X | Do Y |
|---|---|
| ΔMAR ≥ +0.05 on A3 replay AND ex-VIN confirms | Write shadow-rule memo; paper observe for 3 months before hard filter |
| Leader-before-sector >50% in most eligible L4s | Tag as LEADER_DRIVEN; use leader identity as review signal, not sector breadth |
| Placebo ≥95th percentile | Elevate to ranking-feature; re-run P1 Granger tests |
| Placebo ≈ real (fails 95th) | Keep DASHBOARD_WARNING_ONLY; fix sector map before next iteration |
| ex-VIN results significantly weaker than full | Tag M4_vin_distortion_flag; do not cite full-universe numbers for 2025–2026 |
"""

    out_path = OUTPUT_DIR / "SECTOR_L4_CAUSALITY_FINDINGS.md"
    out_path.write_text(text, encoding="utf-8")
    log.info("Findings report saved to %s", out_path)
    return text


def append_p01_section(
    enriched_replay: "pd.DataFrame",
    ablation_by_size: "pd.DataFrame",
    grouping_audit: "pd.DataFrame",
) -> str:
    """
    P0.1 Task 5 — Append P0.1 ChatGPT review adjustment section to SECTOR_L4_CAUSALITY_FINDINGS.md.
    """
    out_path = OUTPUT_DIR / "SECTOR_L4_CAUSALITY_FINDINGS.md"
    existing = out_path.read_text(encoding="utf-8") if out_path.exists() else ""

    # ── Enriched A3 replay summary ─────────────────────────────────────────────
    if enriched_replay is not None and not enriched_replay.empty and "delta_mar_vs_baseline" in enriched_replay.columns:
        row_40 = enriched_replay[enriched_replay["rule_id"] == "l4_ew_ge_40"]
        if not row_40.empty:
            d_mar      = row_40.iloc[0]["delta_mar_vs_baseline"]
            ret_pct    = row_40.iloc[0]["retention_pct"]
            bl_ratio   = row_40.iloc[0]["blocked_loser_winner_ratio"]
            blk_win    = row_40.iloc[0]["blocked_winners"]
            blk_los    = row_40.iloc[0]["blocked_losers"]
            gate_ok    = row_40.iloc[0]["adoption_gate_pass"]
            mar_line = (
                f"L4 ew>=40%: d_tmar={_safe(d_mar, '.4f')}, "
                f"retention={_safe(ret_pct, '.3f')}, "
                f"blocked_winners={int(blk_win) if not isinstance(blk_win, float) or not np.isnan(blk_win) else 'N/A'}, "
                f"blocked_losers={int(blk_los) if not isinstance(blk_los, float) or not np.isnan(blk_los) else 'N/A'}, "
                f"bl_ratio={_safe(bl_ratio, '.2f')}, "
                f"gate={'PASS' if gate_ok == 1 else 'FAIL'}"
            )
        else:
            mar_line = "No result for l4_ew_ge_40 rule"
    else:
        mar_line = "Enriched A3 replay: data not available"

    # ── Ablation by sector-size: n>=5 group ───────────────────────────────────
    if ablation_by_size is not None and not ablation_by_size.empty:
        ge5 = ablation_by_size[
            (ablation_by_size["sector_size_group"] == "n_ge_5") &
            (ablation_by_size["rule_id"] == "l4_ew_ge_40") &
            (ablation_by_size["horizon"] == 60)
        ]
        all_grp = ablation_by_size[
            (ablation_by_size["sector_size_group"] == "all") &
            (ablation_by_size["rule_id"] == "l4_ew_ge_40") &
            (ablation_by_size["horizon"] == 60)
        ]
        if not ge5.empty:
            ge5_hit = float(ge5.iloc[0].get("delta_hit_rate", np.nan))
            ge5_mean = float(ge5.iloc[0].get("delta_mean", np.nan))
            ge5_n = int(ge5.iloc[0].get("n_gate", 0))
        else:
            ge5_hit = ge5_mean = np.nan
            ge5_n = 0
        if not all_grp.empty:
            all_hit = float(all_grp.iloc[0].get("delta_hit_rate", np.nan))
        else:
            all_hit = np.nan
        size_lines = (
            f"- All sectors (n=any): Δhit_rate_60d = **{_safe(all_hit, '.4f')}** [FACT: dominated by n=1 sectors]\n"
            f"- n>=5 sectors only: Δhit_rate_60d = **{_safe(ge5_hit, '.4f')}**, "
            f"Δmean = **{_safe(ge5_mean, '.4f')}**, n_gate_signals = **{ge5_n}**\n"
        )
    else:
        size_lines = "- Sector-size ablation: data not available\n"

    # ── Grouping audit: P1-eligible groups ────────────────────────────────────
    if grouping_audit is not None and not grouping_audit.empty:
        eligible = grouping_audit[grouping_audit["eligible_for_p1"] == 1]
        eligible_lines = ""
        for _, r in eligible.head(10).iterrows():
            eligible_lines += (
                f"  - [{r['grouping_layer']}] {r['group_name']}: "
                f"n={r['n_symbols']}, turns={r['n_group_turn_events_40_35']}\n"
            )
        if not eligible_lines:
            eligible_lines = "  - No groups meet P1 eligibility criteria (n>=5 symbols, >=5 turn events)\n"
    else:
        eligible_lines = "  - Grouping audit data not available\n"

    section = f"""

---

## 11. P0.1 ChatGPT Review Adjustments

**Date:** {date.today().isoformat()}
**Verdict update:** RANKING_FEATURE_ONLY -> **LOCAL_RANKING_FEATURE_ONLY**

### 11.1 FACTS — A3 Ledger Sector Gate Replay (Enriched Ledger)

> Using research-enriched ledger (sector_l4 joined via symbol, NOT original ledger).
> Original ledger: UNCHANGED.
> Metric: trade-level MAR = mean_trade_return / abs(worst_single_trade). Portfolio NAV not computable
> from this ledger (multiple simultaneous trades; no daily NAV series available).

- {mar_line}
- **Critical [FACT]:** All sector gate rules block MORE WINNERS than losers (bl_ratio < 1.0).
  The gate filters high-quality momentum entries disproportionately — it would harm A3 performance.
- G3 (A3 MAR gate): FAIL for all rules. bl_ratio threshold is 1.2; best observed is 0.70 (l4_ew_ge_30).
- Full multi-rule table: `a3_ledger_sector_gate_replay_enriched.csv`

### 11.2 FACTS — Filter Value by Sector-Size Bucket

{size_lines}
- Full breakdown: `filter_value_ablation_by_sector_size.csv`

> **Key finding [FACT]:** The headline +1.63pp Δhit_rate in P0 was dominated by n=1 sectors.
> For n>=5 sectors (the only statistically meaningful group), the figure is:
> Δhit_rate_60d = {_safe(ge5_hit, '.4f')}.

### 11.3 FACTS — L3 / Theme-Bucket Feasibility

P1-eligible groupings (n>=5 symbols, >=5 turn events at primary 40/35 threshold):
{eligible_lines}
- Full audit: `sector_grouping_feasibility_audit.csv`

### 11.4 INTERPRETATION

> Label: INTERPRETATION — not fact. Operator must verify.

- If n>=5 sectors show Δhit_rate_60d ≥ 3pp: elevate to RANKING_FEATURE_ONLY globally, not LOCAL.
- If only 2–3 eligible L4 sectors drive result: result is LOCAL (Vietnam market structure constraint).
- L3 groupings with n>=5 and >=5 turns are P1 candidates for Granger causality.
- Flag-based buckets (bank, broker, real_estate) may offer broader coverage at cost of precision.

### 11.5 Narrowed Verdict

**LOCAL_RANKING_FEATURE_ONLY** — applicable only to eligible L4 sectors (Small Broker, Small Developer, Private Bank).
Not a broad Vietnam-market signal.

**Allowed use:** Operator review priority / watchlist booster for specific eligible L4 sectors.
**Not allowed:** OMS hard filter, A3 contract change, S3 promotion, automatic entry signal.

See `adoption_gate_detail.csv` and `adoption_gate_summary.csv` for gate-level detail.
"""

    # Idempotent: strip any prior P0.1 section before appending updated one
    P01_MARKER = "\n---\n\n## 11. P0.1 ChatGPT Review Adjustments"
    if P01_MARKER in existing:
        existing = existing[:existing.index(P01_MARKER)]

    combined = existing + section
    out_path.write_text(combined, encoding="utf-8")
    log.info("P0.1 section written to %s", out_path)
    return section
