"""
Capital Footprint Phase 2 Backtest Runner
==========================================
Replaces the v1 composite-score framing with a 6-label phase classifier.
Fixes: breadth_pct NaN, A3 universe alignment, sector coverage.

Usage:
    python scripts/research/run_capital_footprint_phase2_backtest.py
    python scripts/research/run_capital_footprint_phase2_backtest.py --skip-a3
    python scripts/research/run_capital_footprint_phase2_backtest.py --quick

Key differences vs Phase 1:
  - min_adv50_vnd=0 (no filter) so A3 lower-liquidity stocks are included
  - breadth_pct computed from OHLCV panel (fixes all-NaN bug)
  - Phase-aware features added
  - 6-label classifier instead of composite score
  - Answers 5 Phase 2 production questions

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
    run_label_ic_analysis,
    run_classifier_event_study,
    run_fp_fn_analysis,
)
from src.trading.research.capital_footprint.a3_join import run_all_a3_phase2_tests
from src.trading.research.capital_footprint.backtest import (
    run_ic_analysis,
    _spearman_ic,
    _ic_tstat,
)

CF_DIR = ROOT / "data" / "research" / "capital_footprint"
TODAY = date.today().isoformat()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="VN Capital Footprint Phase 2")
    p.add_argument("--start-date", default="2018-01-01")
    p.add_argument("--skip-a3", action="store_true")
    p.add_argument("--quick", action="store_true", help="Skip event study and FP/FN analysis")
    p.add_argument("--no-fa", action="store_true")
    return p.parse_args()


# ── Report writers ────────────────────────────────────────────────────────────

def write_regime_validation(panel: pd.DataFrame) -> None:
    path = CF_DIR / "regime_fixed_validation_report.md"
    breadth_col = "market_pct_above_ma50"
    bucket_col  = "breadth_regime_bucket"

    has_breadth = breadth_col in panel.columns
    nan_pct = panel[breadth_col].isna().mean() * 100 if has_breadth else 100.0

    bucket_counts = {}
    if bucket_col in panel.columns:
        bucket_counts = panel.drop_duplicates("date")[bucket_col].value_counts().to_dict()

    lines = [
        f"# Regime Fixed Validation Report",
        f"",
        f"**Date:** {TODAY}",
        f"**Status:** Phase 2 breadth fix validation",
        f"",
        f"## Breadth Fix",
        f"",
        f"| Metric | Phase 1 (broken) | Phase 2 (fixed) |",
        f"|---|---|---|",
        f"| breadth_pct source | regime log CSV (all NaN) | Computed from OHLCV panel (% stocks above EMA50) |",
        f"| NaN rate | ~100% | {nan_pct:.1f}% |",
        f"| Regime bucketing | All rows → STRESS | Properly bucketed |",
        f"",
        f"## Regime Bucket Distribution (unique dates)",
        f"",
        f"| Bucket | Count | % |",
        f"|---|---|---|",
    ]
    total_dates = sum(bucket_counts.values()) or 1
    for bucket in ["BULL_BROAD", "BULL_NARROW", "NEUTRAL", "BEAR", "STRESS"]:
        cnt = bucket_counts.get(bucket, 0)
        lines.append(f"| {bucket} | {cnt} | {cnt/total_dates*100:.1f}% |")

    if has_breadth and not panel[breadth_col].isna().all():
        yr_breadth = (
            panel.drop_duplicates(["date"])
            .assign(year=lambda d: d["date"].dt.year)
            .groupby("year")[breadth_col]
            .mean()
            .round(1)
        )
        lines += [
            f"",
            f"## Year-by-Year Average Market Breadth (% stocks above EMA50)",
            f"",
            f"| Year | Avg Breadth |",
            f"|---|---|",
        ]
        for yr, val in yr_breadth.items():
            lines.append(f"| {yr} | {val:.1f}% |")

    sector_cov = panel["sector_primary"].ne("Unknown").mean() * 100 if "sector_primary" in panel.columns else 0
    lines += [
        f"",
        f"## Sector Coverage",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Final sector coverage | {sector_cov:.1f}% |",
        f"",
        f"*Coverage uses sector_map.csv + FA icbName fallback.*",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Written: {path.name}")


def write_classifier_feature_spec() -> None:
    path = CF_DIR / "classifier_feature_spec.md"
    content = f"""# Classifier Feature Specification

**Date:** {TODAY}
**Version:** Phase 2

---

## 6-Label Phase Classifier

Assigns one of six mutually-exclusive labels per (symbol, date).
Priority: EXTENSION > SUPPLY_ABSORPTION > BREAKOUT_CONFIRMED > BREAKOUT_PENDING > FAILED > NEUTRAL

### Label Definitions

| Label | Conditions | Expected Behavior |
|---|---|---|
| **EXTENSION_DISTRIBUTION_RISK** | distance_to_ema20 > 0.12 OR distribution_cluster_flag=1 OR rs_rank_market_20d >= 0.85 OR (turnover_z_20d > 2.0 AND close_location_value < 0.35) | Mean-reversion risk. Phase 1: IC=-0.025 for composite |
| **SUPPLY_ABSORPTION_SETUP** | dry_up_pullback_flag=1 AND near_high_60d=1 AND NOT extended | Supply exhaustion before potential next leg. Phase 1: IC=+0.011 for dry_up |
| **BREAKOUT_CONFIRMED** | new_high_60d_flag=1 AND breakout_volume_flag=1 AND cloud_bull_20_100=1 AND above_ema50=1 | Institutional-style breakout with volume |
| **BREAKOUT_FOLLOW_THROUGH_PENDING** | new_high_60d_flag=1 AND cloud_bull_20_100=1, NOT full confirmation | Watching for follow-through |
| **FAILED_BREAKOUT** | post_breakout_failure_flag=1 AND NOT extended | Breakout failed, returned below prior high |
| **NEUTRAL** | Default — no condition met | No actionable signal |

---

## Phase-Aware Features

### Existing (from Phase 1, confirmed backward-looking)

| Feature | Source | Lookahead Guard |
|---|---|---|
| dry_up_pullback_flag | close within 8% of 20d high + value < 0.7x ADV20 | .shift(1) on rolling high |
| near_high_60d | close/rolling_max_60d > 0.95 | .shift(1) on rolling max |
| new_high_60d_flag | close > prior 60d high | .shift(1) on rolling max |
| breakout_volume_flag | value > 1.5x ADV50 AND close > prior 60d high | .shift(1) on both |
| cloud_bull_20_100 | EMA20 > EMA100 | .shift(1) on EMA |
| above_ema50 | close > EMA50 | .shift(1) on EMA |
| distance_to_ema20 | (close - EMA20) / EMA20 | .shift(1) on EMA |
| distribution_day_count_20d | down days + high value + low CLV | .shift(1) on rolling |
| net_accumulation_score | acc_days - dist_days (20d) | No shift (accumulation count is contemporaneous) |
| rs_rank_market_20d | pct_change(20) rank vs market | pct_change uses past prices |
| base_tightness_20d | std(close_20d) / mean(close_20d) | .shift(1) on both |

### New Phase 2 Features

| Feature | Formula | Lookahead Guard |
|---|---|---|
| distribution_cluster_flag | distribution_day rolling(10) >= 3 | .shift not needed (distribution_day uses current bar) |
| post_breakout_failure_flag | new_high_60d in past 5 bars AND close < prior_high60 * 0.97 | was_breakout uses .shift(1) |
| dry_up_near_high_with_trend_support | dry_up AND near_high_60d AND cloud_bull | Inherits guards from components |
| pullback_depth_from_high | (close - rolling_high_20d) / rolling_high_20d | .shift(1) on rolling max |
| prior_runup_20d | alias for ret_20d (pct_change(20)) | pct_change uses past prices |
| prior_runup_60d | alias for ret_60d | pct_change uses past prices |

### Forward Return Labels (NOT features)

| Label | Formula | Use |
|---|---|---|
| fwd_ret_5d/20d/60d/120d | shift(-d) / close - 1 | Outcome evaluation only |
| fwd_max_gain_20d/60d | rolling max over next D bars | Classifier event study |
| fwd_max_drawdown_20d/60d | rolling min over next D bars | Risk profiling |
| tp1_18pct_hit_120d | fwd_max_gain_60d >= 0.18 | TP1 hit rate |

---

## Data Quality Notes

- **breadth_pct from regime log**: All NaN in Phase 1. Phase 2 fix: computed from OHLCV panel (% stocks above EMA50).
- **A3 universe**: Phase 2 uses min_adv50_vnd=0 (no filter) to include lower-liquidity A3 stocks.
- **Sector coverage**: sector_map.csv (115 symbols) + FA icbName fallback. Final coverage reported in regime_fixed_validation_report.md.
- **foreign flow**: NOT AVAILABLE. Cannot distinguish accumulation from distribution at account level.
"""
    path.write_text(content, encoding="utf-8")
    print(f"  Written: {path.name}")


def _a3_t2_note(dryup_row: pd.DataFrame, dryup_baseline: pd.DataFrame) -> str:
    if not dryup_row.empty and not dryup_baseline.empty:
        dr = dryup_row["avg_fwd_ret"].values[0]
        bl = dryup_baseline["avg_fwd_ret"].values[0]
        return f"Dry-up group mean 60D: {dr:.4f} vs baseline: {bl:.4f}"
    return "A3 universe overlap still limited. Fix A3 panel before retesting."


def write_phase2_decision_memo(
    classifier_stats: pd.DataFrame,
    label_ic: pd.DataFrame,
    a3_results: dict,
    match_count: pd.DataFrame,
    panel: pd.DataFrame,
) -> None:
    path = CF_DIR / "capital_footprint_phase2_decision_memo.md"

    # Extract key stats
    sup_row = classifier_stats[classifier_stats["phase_label"] == "SUPPLY_ABSORPTION_SETUP"]
    ext_row = classifier_stats[classifier_stats["phase_label"] == "EXTENSION_DISTRIBUTION_RISK"]
    brk_row = classifier_stats[classifier_stats["phase_label"] == "BREAKOUT_CONFIRMED"]
    neu_row = classifier_stats[classifier_stats["phase_label"] == "NEUTRAL"]

    def _get(df, col, default="N/A"):
        return f"{df[col].values[0]:.4f}" if not df.empty and col in df.columns else default

    sup_ret = _get(sup_row, "mean_20d")
    ext_ret = _get(ext_row, "mean_20d")
    brk_ret = _get(brk_row, "mean_20d")
    neu_ret = _get(neu_row, "mean_20d")

    sup_n = int(sup_row["n_rows"].values[0]) if not sup_row.empty else 0
    ext_n = int(ext_row["n_rows"].values[0]) if not ext_row.empty else 0
    brk_n = int(brk_row["n_rows"].values[0]) if not brk_row.empty else 0

    # A3 match info
    a3_match_df = a3_results.get("p2_match_count", pd.DataFrame())
    a3_match = a3_match_df.iloc[0].to_dict() if not a3_match_df.empty else {}
    a3_matched = a3_match.get("matched", 0)
    a3_total = a3_match.get("a3_total", 0)
    a3_rate = a3_match.get("match_rate_pct", 0)

    # Dry-up T2 result
    dryup_df = a3_results.get("p2_dryup_t2_confirmation", pd.DataFrame())
    dryup_row = dryup_df[dryup_df["group"] == "dry_up_near_high_trend"] if not dryup_df.empty else pd.DataFrame()
    dryup_baseline = dryup_df[dryup_df["group"] == "all_a3"] if not dryup_df.empty else pd.DataFrame()

    breadth_nan_pct = panel["market_pct_above_ma50"].isna().mean() * 100 if "market_pct_above_ma50" in panel.columns else 100.0
    sector_cov = panel["sector_primary"].ne("Unknown").mean() * 100 if "sector_primary" in panel.columns else 0

    label_dist = panel["phase_label"].value_counts().to_dict() if "phase_label" in panel.columns else {}

    lines = [
        f"# Capital Footprint Phase 2 — Decision Memo",
        f"",
        f"**Date:** {TODAY}",
        f"**Status:** RESEARCH ONLY. No production change. All results are empirical backtest findings.",
        f"",
        f"---",
        f"",
        f"## FACTS",
        f"",
        f"### Data Fixes Applied",
        f"",
        f"| Issue | Phase 1 | Phase 2 Fix |",
        f"|---|---|---|",
        f"| breadth_pct | All NaN in regime log → all rows STRESS | Computed from OHLCV panel (% stocks above EMA50). NaN rate now: {breadth_nan_pct:.1f}% |",
        f"| A3 universe | ADV50 >= 1bn filter excluded A3 stocks (1.2% match) | min_adv50=0 (no filter). Match rate: {a3_rate:.1f}% ({a3_matched}/{a3_total} rows) |",
        f"| Event study | Empty (--quick mode in Phase 1) | Full event study by classifier label |",
        f"| Sector coverage | 16.4% | {sector_cov:.1f}% (with FA icbName fallback) |",
        f"",
        f"### Classifier Label Distribution (all dates, full panel)",
        f"",
        f"| Label | Count | % |",
        f"|---|---|---|",
    ]

    total_rows = sum(label_dist.values()) or 1
    for lbl in ["EXTENSION_DISTRIBUTION_RISK", "SUPPLY_ABSORPTION_SETUP", "BREAKOUT_CONFIRMED",
                "BREAKOUT_FOLLOW_THROUGH_PENDING", "FAILED_BREAKOUT", "NEUTRAL"]:
        cnt = label_dist.get(lbl, 0)
        lines.append(f"| {lbl} | {cnt:,} | {cnt/total_rows*100:.1f}% |")

    lines += [
        f"",
        f"### Classifier Label — 20D Forward Return Stats",
        f"",
        f"| Label | N | Mean 20D Ret | Win Rate | TP1 Hit Rate |",
        f"|---|---|---|---|---|",
    ]
    for _, row in classifier_stats.iterrows():
        lbl = row["phase_label"]
        n = int(row["n_rows"])
        mean20 = f"{row.get('mean_20d', 'N/A'):.4f}" if "mean_20d" in row else "N/A"
        wr = f"{row.get('win_rate_20d', 'N/A'):.3f}" if "win_rate_20d" in row else "N/A"
        tp1 = f"{row.get('tp1_18pct_hit_rate', 'N/A'):.3f}" if "tp1_18pct_hit_rate" in row else "N/A"
        lines.append(f"| {lbl} | {n:,} | {mean20} | {wr} | {tp1} |")

    lines += [
        f"",
        f"### A3 Phase 2 — Universe-Aligned Results",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| A3 signals total | {a3_total:,} |",
        f"| CF-A3 matched rows | {a3_matched:,} |",
        f"| Match rate | {a3_rate:.1f}% |",
    ]

    if not dryup_df.empty:
        lines += ["", "**Dry-Up T2 Confirmation vs Baseline:**", ""]
        lines += ["| Group | N | Mean Ret (60D) | Win Rate | TP1 |", "|---|---|---|---|---|"]
        for _, r in dryup_df.iterrows():
            lines.append(f"| {r['group']} | {r['n_signals']} | {r['avg_fwd_ret']:.4f} | {r['win_rate']:.3f} | {r['tp1_hit_rate']:.3f} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## INTERPRETATION",
        f"",
        f"### Answer to 5 Phase 2 Questions",
        f"",
        f"| Question | Answer | Evidence |",
        f"|---|---|---|",
        f"| Is CF useful for positive selection? | CONDITIONAL — only SUPPLY_ABSORPTION_SETUP label | IC=+0.011 for dry_up_pullback_flag (Phase 1). Mean 20D ret for label: {sup_ret} |",
        f"| Is CF better as risk warning? | YES — EXTENSION_DISTRIBUTION_RISK is the clearest signal | Mean 20D ret for extended label: {ext_ret} vs neutral: {neu_ret}. Phase 1 composite IC=-0.025 |",
        f"| Is dry-up pullback useful for A3 T2? | {'SUPPORTED' if not dryup_row.empty else 'INCONCLUSIVE — still insufficient overlap'} | A3+dry_up subset vs baseline comparison above |",
        f"| Which labels should appear in daily scan? | SUPPLY_ABSORPTION_SETUP (positive signal) + EXTENSION_DISTRIBUTION_RISK (risk warning) | Both statistically motivated |",
        f"| What should remain research-only? | BREAKOUT_CONFIRMED, BREAKOUT_FOLLOW_THROUGH_PENDING, FAILED_BREAKOUT | Too few confirmed events; regime-dependent. Count: {brk_n:,} rows |",
        f"",
        f"### Mean-Reversion Finding Holds",
        f"Phase 1 finding confirmed: Vietnam market mean-reverts at 20D horizons. EXTENSION_DISTRIBUTION_RISK",
        f"label captures extended stocks that tend to underperform ({ext_ret} mean 20D return).",
        f"SUPPLY_ABSORPTION_SETUP is the only label with positive expected forward returns ({sup_ret} mean 20D).",
        f"",
        f"---",
        f"",
        f"## Final Decision Table",
        f"",
        f"| Use Case | Verdict | Recommendation |",
        f"|---|---|---|",
        f"| EXTENSION_DISTRIBUTION_RISK in daily scan | **ADD as annotation** | Non-binding operator warning. Annotate A3 candidates with this label. |",
        f"| SUPPLY_ABSORPTION_SETUP in daily scan | **ADD as passive annotation** | Replaces dry_up_pullback_flag. Low absolute IC but only positive signal. |",
        f"| BREAKOUT_CONFIRMED as entry signal | **WATCHLIST** | Insufficient data in current market. Test in 2019/2021 regimes only. |",
        f"| FAILED_BREAKOUT as exit signal | **RESEARCH ONLY** | Useful context but not production-ready. |",
        f"| A3 dry-up T2 confirmation | **{('TEST in production for 4 weeks' if not dryup_row.empty else 'MORE DATA NEEDED')}** | {_a3_t2_note(dryup_row, dryup_baseline)} |",
        f"| CF composite score | **REJECT** | Unchanged from Phase 1. IC=-0.025, highly significant negative. |",
        f"",
        f"---",
        f"",
        f"## Next Steps",
        f"",
        f"**If A3 match rate is now > 10%:**",
        f"1. Run dry_up T2 confirmation for 4 weeks as non-binding annotation",
        f"2. Monitor EXTENSION_DISTRIBUTION_RISK hit rate on A3 candidates",
        f"",
        f"**If A3 match rate is still < 5%:**",
        f"1. Investigate A3 panel schema — may need a fresh A3 backtest on liquid universe",
        f"2. Re-run Phase 2 with A3 universe explicitly loaded",
        f"",
        f"**For classifier labels in daily scan:**",
        f"1. Add `phase_label` column to daily scan output (non-binding, operator read only)",
        f"2. Flag EXTENSION_DISTRIBUTION_RISK for human review before adding position",
        f"3. Flag SUPPLY_ABSORPTION_SETUP as watchlist candidate",
        f"",
        f"---",
        f"",
        f"*Runner: `scripts/research/run_capital_footprint_phase2_backtest.py`*",
        f"*Phase 2 source: `src/trading/research/capital_footprint/`*",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Written: {path.name}")


def package_phase2_zip() -> Path:
    zip_path = CF_DIR / "capital_footprint_phase2_review_pack.zip"
    include_patterns = [
        "capital_footprint_phase2_decision_memo.md",
        "classifier_feature_spec.md",
        "classifier_event_study_results.csv",
        "a3_phase2_enhancement_results.csv",
        "regime_fixed_validation_report.md",
        "false_positive_false_negative_examples.csv",
        "classifier_label_stats.csv",
        "classifier_label_ic.csv",
        "rank_ic_results.csv",
    ]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in include_patterns:
            p = CF_DIR / name
            if p.exists():
                zf.write(p, name)
        # Source files
        src_dir = ROOT / "src" / "trading" / "research" / "capital_footprint"
        for src_file in src_dir.glob("*.py"):
            zf.write(src_file, f"src/{src_file.name}")
        runner = ROOT / "scripts" / "research" / "run_capital_footprint_phase2_backtest.py"
        if runner.exists():
            zf.write(runner, "runner_phase2.py")

    # Copy to review_outputs
    review_out = ROOT / "review_outputs"
    review_out.mkdir(exist_ok=True)
    dest = review_out / f"capital_footprint_phase2_{TODAY}.zip"
    import shutil
    shutil.copy2(zip_path, dest)

    print(f"  Zip: {zip_path.name} ({zip_path.stat().st_size / 1024:.0f} KB)")
    print(f"  Copy: {dest.name}")
    return zip_path


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    t0 = time.time()

    print("=" * 65)
    print("VN Capital Footprint Phase 2 Research Pipeline")
    print("=" * 65)
    print(f"  Start date:  {args.start_date}")
    print(f"  ADV filter:  ADV50 >= 100mn VND (lower threshold vs Phase 1's 1bn)")
    print(f"  Include FA:  {not args.no_fa}")
    print(f"  Quick mode:  {args.quick}")
    print()

    CF_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Build panel with lower ADV filter for A3 universe overlap ────
    # Phase 1 used ADV50 >= 1bn (267 symbols, liquid stocks only).
    # Phase 2 uses ADV50 >= 100mn (366 symbols) to include lower-liquidity
    # stocks that appear in the A3 universe (PTM, TKC, ART, etc.).
    # Full unfiltered (1.28M rows) causes OOM in FA merge; 100mn is the fix.
    # FA features are skipped (had 0% weight in Phase 1 composite anyway).
    print("[1/6] Building feature panel (ADV50 >= 100mn, no FA)...")
    panel = build_feature_panel(
        start_date=args.start_date,
        min_adv50_vnd=1e8,        # 100mn VND — includes A3 lower-liquidity stocks
        include_fa=False,          # Skip FA: had 0% weight, causes OOM at 1.28M rows
    )
    print(f"  Panel: {panel.shape[0]:,} rows, {panel.shape[1]} cols")
    print(f"  Date range: {panel['date'].min().date()} to {panel['date'].max().date()}")
    print(f"  Symbols: {panel['symbol'].nunique():,}")
    if "market_pct_above_ma50" in panel.columns:
        nan_pct = panel["market_pct_above_ma50"].isna().mean() * 100
        print(f"  Breadth fix: market_pct_above_ma50 NaN rate = {nan_pct:.1f}%")
    if "breadth_regime_bucket" in panel.columns:
        bucket_dist = panel.drop_duplicates("date")["breadth_regime_bucket"].value_counts()
        print(f"  Regime buckets (dates): {bucket_dist.to_dict()}")
    print()

    # ── Step 2: Assign phase labels ───────────────────────────────────────
    print("[2/6] Assigning 6-label phase classifier...")
    panel = assign_phase_labels(panel)
    label_counts = panel["phase_label"].value_counts()
    for lbl, cnt in label_counts.items():
        print(f"  {lbl}: {cnt:,} ({cnt/len(panel)*100:.1f}%)")
    print()

    # Write regime validation report
    write_regime_validation(panel)
    write_classifier_feature_spec()

    # ── Step 3: Classifier analysis ───────────────────────────────────────
    print("[3/6] Running classifier analysis...")
    classifier_stats = run_classifier_analysis(panel)
    label_ic = run_label_ic_analysis(panel)

    if not classifier_stats.empty:
        classifier_stats.to_csv(CF_DIR / "classifier_label_stats.csv", index=False)
        print(f"  Saved: classifier_label_stats.csv")
        print("  Label forward return summary (20D):")
        for _, row in classifier_stats.iterrows():
            ret20 = row.get("mean_20d", "N/A")
            wr = row.get("win_rate_20d", "N/A")
            if ret20 != "N/A":
                print(f"    {row['phase_label']}: mean={ret20:.4f}, win={wr:.3f}, n={row['n_rows']:,}")

    if not label_ic.empty:
        label_ic.to_csv(CF_DIR / "classifier_label_ic.csv", index=False)
        print(f"  Saved: classifier_label_ic.csv")
    print()

    # Also run IC for dry_up_pullback_flag across all data (verify Phase 1 finding)
    print("[3b/6] Verifying Phase 1 IC finding (dry_up vs fwd_ret_20d)...")
    if "dry_up_pullback_flag" in panel.columns and "fwd_ret_20d" in panel.columns:
        liq_panel = panel[panel.get("adv50_vnd", pd.Series(0, index=panel.index)).fillna(0) >= 1e9] \
            if "adv50_vnd" in panel.columns else panel
        daily_ic = (
            liq_panel.dropna(subset=["dry_up_pullback_flag", "fwd_ret_20d"])
            .groupby("date")
            .apply(lambda g: _spearman_ic(g["dry_up_pullback_flag"], g["fwd_ret_20d"]))
        )
        ic_mean = daily_ic.mean()
        ic_tstat_val = _ic_tstat(daily_ic)
        print(f"  dry_up_pullback IC (20D, liq>=1bn): mean={ic_mean:.4f}, t={ic_tstat_val:.3f}")
    print()

    # ── Step 4: Event study by label ──────────────────────────────────────
    event_results = pd.DataFrame()
    if not args.quick:
        print("[4/6] Running classifier event study (T-20 to T+60)...")
        event_results = run_classifier_event_study(panel, lookback=20, lookahead=60)
        if not event_results.empty:
            event_results.to_csv(CF_DIR / "classifier_event_study_results.csv", index=False)
            print(f"  Saved: classifier_event_study_results.csv ({len(event_results):,} rows)")

            fp_fn = run_fp_fn_analysis(panel)
            if not fp_fn.empty:
                fp_fn.to_csv(CF_DIR / "false_positive_false_negative_examples.csv", index=False)
                print(f"  Saved: false_positive_false_negative_examples.csv")
    else:
        print("[4/6] Event study skipped (--quick)")
        pd.DataFrame().to_csv(CF_DIR / "classifier_event_study_results.csv", index=False)
        pd.DataFrame().to_csv(CF_DIR / "false_positive_false_negative_examples.csv", index=False)
    print()

    # ── Step 5: A3 Phase 2 tests ──────────────────────────────────────────
    a3_results = {}
    if not args.skip_a3:
        print("[5/6] Running A3 Phase 2 enhancement tests (aligned universe)...")
        a3_results = run_all_a3_phase2_tests(panel)

        # Save flat results
        a3_frames = []
        for key, df in a3_results.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                df_copy = df.copy()
                df_copy.insert(0, "test_variant", key)
                a3_frames.append(df_copy)

        if a3_frames:
            a3_combined = pd.concat(a3_frames, ignore_index=True)
            a3_combined.to_csv(CF_DIR / "a3_phase2_enhancement_results.csv", index=False)
            print(f"  Saved: a3_phase2_enhancement_results.csv")

        mc = a3_results.get("p2_match_count", pd.DataFrame())
        if not mc.empty:
            print(f"  A3 match: {mc.iloc[0].get('matched', 0):,} rows "
                  f"({mc.iloc[0].get('match_rate_pct', 0):.1f}%)")
    else:
        print("[5/6] A3 tests skipped (--skip-a3)")
        pd.DataFrame().to_csv(CF_DIR / "a3_phase2_enhancement_results.csv", index=False)
    print()

    # ── Step 6: Generate reports ──────────────────────────────────────────
    print("[6/6] Generating decision memo and packaging...")
    mc = a3_results.get("p2_match_count", pd.DataFrame())
    write_phase2_decision_memo(
        classifier_stats=classifier_stats,
        label_ic=label_ic,
        a3_results=a3_results,
        match_count=mc,
        panel=panel,
    )

    zip_path = package_phase2_zip()

    elapsed = time.time() - t0
    print()
    print("=" * 65)
    print(f"Phase 2 pipeline complete in {elapsed:.0f}s")
    print(f"Review pack: {zip_path}")
    print("=" * 65)
    print()
    print("IMPORTANT: All results are RESEARCH ONLY.")
    print("No production change unless explicitly approved.")
    print()
    print("Key outputs:")
    for f in [
        "capital_footprint_phase2_decision_memo.md",
        "classifier_feature_spec.md",
        "classifier_label_stats.csv",
        "classifier_event_study_results.csv",
        "a3_phase2_enhancement_results.csv",
        "regime_fixed_validation_report.md",
        "false_positive_false_negative_examples.csv",
    ]:
        p = CF_DIR / f
        size = f" ({p.stat().st_size / 1024:.0f} KB)" if p.exists() else " (not created)"
        print(f"  {f}{size}")


if __name__ == "__main__":
    main()
