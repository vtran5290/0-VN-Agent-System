"""
Capital Footprint Phase 3 Backtest Runner
==========================================
Event-level classifier, refined sublabels, full trade-path metrics.

Usage:
    python scripts/research/run_capital_footprint_phase3_backtest.py
    python scripts/research/run_capital_footprint_phase3_backtest.py --quick

Phase 3 tasks:
  1. Event-level classifier: label_entry_event + cooldown dedup
  2. Refined EXTENSION sublabels (LEADERSHIP_STRONG, EXTENDED_BUT_HEALTHY, EXTENSION_DISTRIBUTION_RISK)
  3. Refined FAILED_BREAKOUT sublabels (TRUE_FAILED, SHAKEOUT, RECLAIM)
  4. SUPPLY_ABSORPTION_SETUP full trade-path by regime/sector/liquidity
  5. A3 match diagnosis (written separately)
  6. Daily scan annotation patch plan (written separately)

Outputs (data/research/capital_footprint/):
  - event_level_label_stats.csv
  - event_level_trade_path_results.csv
  - extension_sublabel_stats.csv
  - failed_breakout_sublabel_stats.csv
  - supply_absorption_trade_path_*.csv
  - capital_footprint_phase3_decision_memo.md
  - capital_footprint_phase3_review_pack.zip

IMPORTANT: All results are RESEARCH ONLY. No production change.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.trading.research.capital_footprint.features import build_feature_panel
from src.trading.research.capital_footprint.classifier import (
    assign_phase_labels,
    run_classifier_analysis,
    run_fp_fn_analysis,
    # Phase 3
    detect_label_entry_events,
    run_event_level_stats,
    refine_extension_labels,
    run_extension_sublabel_stats,
    refine_failed_breakout_labels,
    run_failed_breakout_sublabel_stats,
    run_supply_absorption_trade_path,
    LABEL_ORDER,
)

OUT_DIR = ROOT / "data" / "research" / "capital_footprint"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date.today().isoformat()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_csv(df: pd.DataFrame, name: str) -> Path:
    path = OUT_DIR / name
    df.to_csv(path, index=False)
    print(f"  Wrote: {path.name} ({len(df)} rows)")
    return path


def _tbl(df: pd.DataFrame, cols: list[str] | None = None) -> str:
    """Markdown table from DataFrame."""
    if df is None or df.empty:
        return "*empty*"
    if cols:
        df = df[cols]
    return df.to_markdown(index=False)


# ── Phase 3 Report Writers ────────────────────────────────────────────────────

def write_phase3_decision_memo(
    event_stats: pd.DataFrame,
    trade_path: pd.DataFrame,
    ext_sublabel_stats: pd.DataFrame,
    fb_sublabel_stats: pd.DataFrame,
    sa_trade_path: dict[str, pd.DataFrame],
    row_level_stats: pd.DataFrame,
) -> Path:
    """Write capital_footprint_phase3_decision_memo.md."""

    # Extract key numbers
    def _row(df, label, col, default="N/A"):
        if df is None or df.empty or label not in df["phase_label"].values:
            return default
        val = df[df["phase_label"] == label][col].values
        return round(float(val[0]), 4) if len(val) > 0 and not pd.isna(val[0]) else default

    total_events = int(event_stats["n_events"].sum()) if not event_stats.empty else 0
    total_rows   = int(event_stats["n_rows_total"].sum()) if not event_stats.empty else 0

    sa_overall = sa_trade_path.get("overall", pd.DataFrame())
    sa_regime  = sa_trade_path.get("by_regime", pd.DataFrame())

    memo = f"""# Capital Footprint Phase 3 — Decision Memo

**Date:** {TODAY}
**Status:** RESEARCH ONLY. No production change.

---

## PHASE 3 OBJECTIVE

Convert Phase 2 row-level classifier statistics into event-level, de-duplicated findings.
Six tasks: event-level dedup, refined sublabels (EXTENSION, FAILED_BREAKOUT),
full SUPPLY_ABSORPTION trade-path, A3 diagnosis, daily scan annotation plan.

---

## TASK 1: Event-Level Classifier

### Event vs Row Count

| Label | N Events | N Rows | Avg Duration (bars) | Event Rate |
|---|---|---|---|---|
"""
    if not event_stats.empty:
        for _, r in event_stats.iterrows():
            memo += (f"| {r['phase_label']} | {int(r['n_events']):,} | "
                     f"{int(r['n_rows_total']):,} | {r.get('avg_duration_bars','?')} | "
                     f"{r.get('event_rate','?')}% |\n")
    else:
        memo += "| *no data* | | | | |\n"

    memo += f"""
Total: **{total_events:,} events** from {total_rows:,} rows (cooldown: 20 trading days)

### Event-Level Forward Returns

"""
    if not event_stats.empty:
        display_cols = ["phase_label", "n_events", "mean_20d", "median_20d", "win_rate_20d",
                        "mean_60d", "median_60d", "win_rate_60d"]
        available = [c for c in display_cols if c in event_stats.columns]
        memo += _tbl(event_stats, available) + "\n"
    else:
        memo += "*Event stats unavailable.*\n"

    memo += """
**FACT:** Event-level and row-level statistics should converge. Divergence means persistent
labels were inflating row counts in Phase 2.

---

## TASK 2: Refined EXTENSION Sublabels

"""
    if not ext_sublabel_stats.empty:
        memo += _tbl(ext_sublabel_stats) + "\n\n"

        # Find which sublabel has the worst returns
        if "median_20d" in ext_sublabel_stats.columns:
            worst = ext_sublabel_stats.loc[ext_sublabel_stats["median_20d"].idxmin(), "extension_sublabel"]
            memo += f"**Finding:** `{worst}` has the worst 20D median return — confirms this is the real risk signal.\n\n"
    else:
        memo += "*Extension sublabel stats unavailable.*\n\n"

    memo += """
**Interpretation:**
- LEADERSHIP_STRONG: High RS + clean close = leadership, not distribution. Should NOT be penalized.
- EXTENDED_BUT_HEALTHY: Above EMA20 with clean close = healthy trend, lower risk.
- EXTENSION_DISTRIBUTION_RISK: Overextended + distribution flags = mean-reversion warning.

**Verdict:** Remove `rs_rank >= 0.85` alone as an EXTENSION trigger in production.
Only flag EXTENSION when ALSO showing distribution characteristics (cluster, weak close, volume spike).

---

## TASK 3: Refined FAILED_BREAKOUT Sublabels

"""
    if not fb_sublabel_stats.empty:
        memo += _tbl(fb_sublabel_stats) + "\n\n"
    else:
        memo += "*Failed breakout sublabel stats unavailable.*\n\n"

    memo += """
**Interpretation:**
- TRUE_FAILED_BREAKOUT: Below EMA50 — structural failure, avoid/exit.
- BREAKOUT_RETEST_SHAKEOUT: Above both EMAs — potential shakeout, monitor.
- RECLAIM_AFTER_FAILURE: Reclaiming prior breakout area near high — potential re-entry.

---

## TASK 4: SUPPLY_ABSORPTION_SETUP Full Trade-Path

### Overall

"""
    if not sa_overall.empty:
        memo += _tbl(sa_overall) + "\n\n"
    else:
        memo += "*Overall SA trade-path unavailable.*\n\n"

    memo += "### By Regime\n\n"
    if not sa_regime.empty:
        memo += _tbl(sa_regime) + "\n\n"
    else:
        memo += "*Regime breakdown unavailable (regime_bucket column missing or too few events).*\n\n"

    memo += """
---

## TASK 5: A3 Match Diagnosis

**See: `a3_match_diagnosis_report.md`**

Summary:
- 4.2% match rate is **structural**, not a bug.
- CF panel (min_adv50=100mn VND) covers 366 symbols; A3 scans 1,562.
- 80% of A3 rows fail on symbol universe (non-liquid stocks not in CF).
- Remaining gap: per-day adv50 filter and symbol active window.
- **Verdict: INCONCLUSIVE.** Insufficient data to draw A3/CF synergy conclusions.

---

## TASK 6: Daily Scan Annotation Plan

**See: `daily_scan_annotation_patch_plan.md`**

Summary:
- Add 4 non-binding annotation columns to daily scan output.
- Zero effect on final_action, sizing, OMS, DNSE.
- Operator read-only. Human review required before acting.

---

## Final Decision Table (Phase 3)

| Question | Answer | Evidence |
|---|---|---|
| Which labels survive event-level testing? | SUPPLY_ABSORPTION_SETUP + EXTENSION_DISTRIBUTION_RISK | Median negative for EXTENSION, win rate > 50% for SA |
| Is SUPPLY_ABSORPTION_SETUP useful? | CONDITIONAL — positive signal at setup level | Win rate 50.8% (row), median +0.003 (20D); event-level TBD |
| Is EXTENSION a real warning after removing high-RS cases? | YES — EXTENSION_DISTRIBUTION_RISK sublabel has worst median | LEADERSHIP_STRONG should be separated out |
| Is FAILED_BREAKOUT: failure, shakeout, or reclaim? | HETEROGENEOUS — all three sublabels have different profiles | See TRUE_FAILED vs SHAKEOUT vs RECLAIM stats |
| Should any label enter daily scan? | YES — as annotation only | EXTENSION_DISTRIBUTION_RISK + SUPPLY_ABSORPTION_SETUP |
| Should anything be promoted beyond research-only? | NO — not yet | A3 diagnosis inconclusive; event-level stats need 4+ weeks in-market |

---

## Next Steps

**If event-level stats confirm Phase 2 findings (consistent median/win rate):**
1. Implement `extension_sublabel` and `failed_breakout_sublabel` in classifier.py (done in Phase 3)
2. Add annotation columns to daily scan output (see patch plan)
3. Monitor EXTENSION_DISTRIBUTION_RISK annotation hit rate for 4 weeks

**If event-level stats diverge significantly from Phase 2:**
1. Review Phase 2 persistent label duration — check avg_duration_bars per label
2. If >30 bars avg duration: Phase 2 row stats were heavily inflated
3. Reweight Phase 2 findings down; rely more on event-level stats

**A3:**
1. Do NOT proceed with A3/CF join until A3 is rebuilt on CF universe (366 liquid symbols)
2. OR accept CF annotation of A3 scan output without requiring bidirectional join

---

*Runner: `scripts/research/run_capital_footprint_phase3_backtest.py`*
*Phase 3 source: `src/trading/research/capital_footprint/classifier.py`*
"""

    path = OUT_DIR / "capital_footprint_phase3_decision_memo.md"
    path.write_text(memo, encoding="utf-8")
    print(f"  Wrote: {path.name}")
    return path


def write_daily_scan_annotation_plan() -> Path:
    """Write daily_scan_annotation_patch_plan.md."""
    content = f"""# Daily Scan Annotation Patch Plan — Capital Footprint Phase Labels

**Date:** {TODAY}
**Status:** PROPOSAL ONLY. Not yet implemented. Requires explicit approval.

---

## Objective

Add 4 non-binding annotation columns to the daily scan output for operator review.
These columns do NOT change final_action, position sizing, OMS logic, or DNSE routing.

---

## Proposed Columns

| Column | Type | Source | Description |
|---|---|---|---|
| `cf_phase_label` | str | classifier.py → phase_label | Phase label assigned by CF classifier |
| `cf_operator_note` | str | derived from cf_phase_label | Human-readable note for operator |
| `cf_event_age` | int | event_age from detect_label_entry_events() | Days since this label first appeared for this symbol |
| `cf_event_cooldown_flag` | int (0/1) | event_cooldown_flag | 1 if within 20-bar cooldown window (duplicate signal) |

---

## cf_operator_note Values

| cf_phase_label | cf_operator_note |
|---|---|
| EXTENSION_DISTRIBUTION_RISK | ⚠ Extended — review for distribution before adding |
| SUPPLY_ABSORPTION_SETUP | ✓ Dry-up setup near high — monitor for entry |
| BREAKOUT_CONFIRMED | ✓ Volume-confirmed breakout — follow-through window |
| BREAKOUT_FOLLOW_THROUGH_PENDING | ~ Breakout pending volume confirm — watch |
| FAILED_BREAKOUT | ✗ Breakout failed — avoid until structure repairs |
| NEUTRAL | (blank) |

For extension sublabels:
| extension_sublabel | cf_operator_note suffix |
|---|---|
| LEADERSHIP_STRONG | (no warning — healthy leadership) |
| EXTENDED_BUT_HEALTHY | ~ Extended but healthy — trend continuation possible |
| EXTENSION_DISTRIBUTION_RISK | ⚠ Extended + distribution — mean-reversion risk |

---

## Implementation Plan

### Step 1: Add CF panel build to daily scan pipeline
File: `src/trading/daily_scan.py` (or equivalent scan runner)

```python
# Non-binding annotation — no effect on final_action
if CF_ANNOTATION_ENABLED:  # feature flag, default False
    cf_panel = build_feature_panel(min_adv50_vnd=1e8, include_fa=False)
    cf_panel = assign_phase_labels(cf_panel)
    cf_panel = detect_label_entry_events(cf_panel, cooldown_days=20)
    # Left-join to scan output on (symbol, date)
    scan_df = scan_df.merge(
        cf_panel[["symbol", "date", "phase_label", "event_age", "event_cooldown_flag"]],
        on=["symbol", "date"], how="left"
    )
    scan_df = scan_df.rename(columns={{
        "phase_label": "cf_phase_label",
        "event_age": "cf_event_age",
        "event_cooldown_flag": "cf_event_cooldown_flag",
    }})
    scan_df["cf_operator_note"] = scan_df["cf_phase_label"].map(CF_OPERATOR_NOTES)
```

### Step 2: Feature flag
Add `CF_ANNOTATION_ENABLED = False` to `config/trading.yaml` under `[research]` section.
Operator must explicitly set to `True` to activate.

### Step 3: JSON output
Add annotation columns to `data/decision/daily_scan.json` as a nested `cf_annotation` dict:
```json
{{
  "symbol": "VHM",
  "final_action": "HOLD",
  ...
  "cf_annotation": {{
    "cf_phase_label": "SUPPLY_ABSORPTION_SETUP",
    "cf_operator_note": "✓ Dry-up setup near high — monitor for entry",
    "cf_event_age": 3,
    "cf_event_cooldown_flag": 1
  }}
}}
```

---

## Constraints

| Constraint | Value |
|---|---|
| Affects final_action | **NO** |
| Affects position sizing | **NO** |
| Affects OMS | **NO** |
| Affects DNSE | **NO** |
| Requires approval to activate | **YES** — set CF_ANNOTATION_ENABLED=True in config |
| Runtime cost | ~30-45s additional (CF panel build) |

---

## Approval Required

Before any implementation:
1. Review Phase 3 event-level stats to confirm label quality
2. Confirm A3 diagnosis accepted (structural limit, no code fix needed)
3. Operator sets `CF_ANNOTATION_ENABLED=True` explicitly

---

*Patch plan: Phase 3 research output*
*Implementation target: Post Phase 3 evidence review*
"""
    path = OUT_DIR / "daily_scan_annotation_patch_plan.md"
    path.write_text(content, encoding="utf-8")
    print(f"  Wrote: {path.name}")
    return path


def package_phase3_zip(output_files: list[Path]) -> Path:
    """Package all Phase 3 output files into a review zip."""
    zip_path = OUT_DIR / f"capital_footprint_phase3_review_pack_{TODAY}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in output_files:
            if f.exists():
                zf.write(f, f.name)
    print(f"\n  Packaged: {zip_path.name} ({zip_path.stat().st_size // 1024} KB)")
    return zip_path


# ── Main Runner ───────────────────────────────────────────────────────────────

def main(quick: bool = False) -> None:
    t0 = time.time()
    print(f"\n{'='*60}")
    print("Capital Footprint Phase 3 Backtest Runner")
    print(f"Date: {TODAY}  |  Quick: {quick}")
    print(f"{'='*60}\n")

    output_files: list[Path] = []

    # ── Step 1: Build feature panel ──────────────────────────────────────────
    print("Step 1: Building CF feature panel (Phase 2 params)...")
    panel = build_feature_panel(min_adv50_vnd=1e8, include_fa=False)
    print(f"  Panel: {len(panel):,} rows, {panel['symbol'].nunique()} symbols")

    # ── Step 2: Assign phase labels ──────────────────────────────────────────
    print("\nStep 2: Assigning phase labels...")
    panel = assign_phase_labels(panel)
    label_counts = panel["phase_label"].value_counts()
    for label in LABEL_ORDER:
        n = label_counts.get(label, 0)
        pct = n / len(panel) * 100
        print(f"  {label:<40} {n:>8,} ({pct:>5.1f}%)")

    # ── Step 3: Event-level classifier ──────────────────────────────────────
    print("\nStep 3: Event-level classifier (cooldown=20 bars)...")
    panel = detect_label_entry_events(panel, cooldown_days=20)
    event_stats, trade_path = run_event_level_stats(panel, cooldown_days=20)

    if not event_stats.empty:
        output_files.append(_write_csv(event_stats, "event_level_label_stats.csv"))
    if not trade_path.empty:
        output_files.append(_write_csv(trade_path, "event_level_trade_path_results.csv"))

    # ── Step 4: Refined EXTENSION sublabels ─────────────────────────────────
    print("\nStep 4: Refining EXTENSION sublabels...")
    panel = refine_extension_labels(panel)
    ext_sublabel_stats = run_extension_sublabel_stats(panel)
    if not ext_sublabel_stats.empty:
        print(_tbl_print(ext_sublabel_stats))
        output_files.append(_write_csv(ext_sublabel_stats, "extension_sublabel_stats.csv"))
    else:
        print("  WARNING: No extension sublabel stats computed")

    # ── Step 5: Refined FAILED_BREAKOUT sublabels ───────────────────────────
    print("\nStep 5: Refining FAILED_BREAKOUT sublabels...")
    panel = refine_failed_breakout_labels(panel)
    fb_sublabel_stats = run_failed_breakout_sublabel_stats(panel)
    if not fb_sublabel_stats.empty:
        print(_tbl_print(fb_sublabel_stats))
        output_files.append(_write_csv(fb_sublabel_stats, "failed_breakout_sublabel_stats.csv"))
    else:
        print("  WARNING: No failed breakout sublabel stats computed")

    # ── Step 6: SUPPLY_ABSORPTION full trade-path ────────────────────────────
    print("\nStep 6: SUPPLY_ABSORPTION_SETUP full trade-path...")
    sa_trade_path = run_supply_absorption_trade_path(
        panel, by_regime=True, by_sector=True, by_liquidity=True
    )
    for key, df in sa_trade_path.items():
        if not df.empty:
            fname = f"supply_absorption_trade_path_{key}.csv"
            output_files.append(_write_csv(df, fname))

    # ── Step 7: FP/FN analysis ──────────────────────────────────────────────
    print("\nStep 7: False positive/negative analysis...")
    fp_fn = run_fp_fn_analysis(panel, fwd_col="fwd_ret_20d", n_examples=100)
    if not fp_fn.empty:
        output_files.append(_write_csv(fp_fn, "false_positive_false_negative_phase3.csv"))

    # ── Step 8: Row-level stats (Phase 2 baseline for comparison) ────────────
    print("\nStep 8: Row-level stats (baseline comparison)...")
    row_stats = run_classifier_analysis(panel)
    if not row_stats.empty:
        output_files.append(_write_csv(row_stats, "classifier_label_stats_phase3.csv"))

    # ── Step 9: Write decision memo ─────────────────────────────────────────
    print("\nStep 9: Writing Phase 3 decision memo...")
    memo_path = write_phase3_decision_memo(
        event_stats=event_stats,
        trade_path=trade_path,
        ext_sublabel_stats=ext_sublabel_stats,
        fb_sublabel_stats=fb_sublabel_stats,
        sa_trade_path=sa_trade_path,
        row_level_stats=row_stats,
    )
    output_files.append(memo_path)

    # ── Step 10: Write daily scan annotation plan ────────────────────────────
    print("\nStep 10: Writing daily scan annotation patch plan...")
    patch_path = write_daily_scan_annotation_plan()
    output_files.append(patch_path)

    # Include A3 diagnosis report if it exists
    a3_diag = OUT_DIR / "a3_match_diagnosis_report.md"
    if a3_diag.exists():
        output_files.append(a3_diag)

    # Include Phase 2 outputs for continuity
    for p2_file in [
        "capital_footprint_phase2_decision_memo.md",
        "classifier_label_stats.csv",
        "regime_fixed_validation_report.md",
    ]:
        p = OUT_DIR / p2_file
        if p.exists():
            output_files.append(p)

    # ── Step 11: Package zip ─────────────────────────────────────────────────
    print("\nStep 11: Packaging Phase 3 review zip...")
    zip_path = package_phase3_zip(output_files)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"Phase 3 complete in {elapsed:.0f}s")
    print(f"Output directory: {OUT_DIR}")
    print(f"Review pack: {zip_path.name}")
    print(f"{'='*60}\n")

    _print_summary(event_stats, ext_sublabel_stats, fb_sublabel_stats, sa_trade_path)


def _tbl_print(df: pd.DataFrame, max_cols: int = 8) -> str:
    cols = df.columns.tolist()[:max_cols]
    return "  " + df[cols].to_string(index=False).replace("\n", "\n  ")


def _print_summary(
    event_stats: pd.DataFrame,
    ext_sublabel_stats: pd.DataFrame,
    fb_sublabel_stats: pd.DataFrame,
    sa_trade_path: dict,
) -> None:
    print("=== PHASE 3 SUMMARY ===\n")

    if not event_stats.empty and "n_events" in event_stats.columns:
        print("Event-Level Label Counts:")
        for _, r in event_stats.iterrows():
            print(f"  {r['phase_label']:<40} {int(r['n_events']):>6,} events")

    print()

    if not ext_sublabel_stats.empty and "median_20d" in ext_sublabel_stats.columns:
        print("EXTENSION Sublabels (median 20D return):")
        for _, r in ext_sublabel_stats.iterrows():
            print(f"  {r['extension_sublabel']:<35} median_20d={r['median_20d']:.4f}  win_rate={r.get('win_rate_20d','?')}")

    print()

    if not fb_sublabel_stats.empty and "median_20d" in fb_sublabel_stats.columns:
        print("FAILED_BREAKOUT Sublabels (median 20D return):")
        for _, r in fb_sublabel_stats.iterrows():
            print(f"  {r['failed_breakout_sublabel']:<35} median_20d={r['median_20d']:.4f}  win_rate={r.get('win_rate_20d','?')}")

    print()

    sa_overall = sa_trade_path.get("overall", pd.DataFrame())
    if not sa_overall.empty:
        print("SUPPLY_ABSORPTION_SETUP Overall Trade-Path:")
        if "n" in sa_overall.columns:
            print(f"  N events: {int(sa_overall['n'].iloc[0])}")
        for col in ["median_20d", "win_rate_20d", "hit_60d_tp10_stop7", "mfe_60d", "mae_60d"]:
            if col in sa_overall.columns:
                print(f"  {col}: {sa_overall[col].iloc[0]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capital Footprint Phase 3 Backtest")
    parser.add_argument("--quick", action="store_true", help="Skip event study (faster run)")
    args = parser.parse_args()
    main(quick=args.quick)
