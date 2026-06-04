"""
Capital Footprint Backtest Runner
====================================
Main entry point for the VN Capital Footprint research pipeline.

Usage:
    python scripts/research/run_capital_footprint_backtest.py
    python scripts/research/run_capital_footprint_backtest.py --no-fa
    python scripts/research/run_capital_footprint_backtest.py --min-adv 5e9

Outputs: data/research/capital_footprint/
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.capital_footprint.features import build_feature_panel
from src.trading.research.capital_footprint.scoring import add_scores
from src.trading.research.capital_footprint.backtest import (
    run_ic_analysis,
    run_ic_by_year,
    run_quantile_portfolio_full,
    run_event_study,
    run_feature_ablation,
    run_regime_robustness,
    classify_false_positives,
    classify_best_winners,
    top_stocks_current,
)
from src.trading.research.capital_footprint.a3_join import run_all_a3_enhancement_tests
from src.trading.research.capital_footprint.reporting import (
    save_feature_panel,
    save_score_panel,
    save_ic_results,
    save_quantile_results,
    save_event_study,
    save_a3_results,
    save_ablation_results,
    save_false_positives,
    save_best_winners,
    save_regime_robustness,
    save_top_current,
    write_feature_spec,
    write_readme,
    write_decision_memo,
    package_review_zip,
    CF_DIR,
)

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="VN Capital Footprint backtest pipeline")
    p.add_argument("--no-fa", action="store_true", help="Skip fundamental features")
    p.add_argument("--min-adv", type=float, default=1e9, help="Min ADV50 filter (VND)")
    p.add_argument("--start-date", default="2018-01-01", help="Feature panel start date")
    p.add_argument("--skip-a3", action="store_true", help="Skip A3 enhancement tests")
    p.add_argument("--quick", action="store_true", help="Quick mode: skip event study and false-positive analysis")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.time()

    print("=" * 65)
    print("VN Capital Footprint Research Pipeline")
    print("=" * 65)
    print(f"  Start date: {args.start_date}")
    print(f"  Min ADV50: {args.min_adv/1e9:.1f}bn VND")
    print(f"  Include FA: {not args.no_fa}")
    print(f"  Output: {CF_DIR}")
    print()

    CF_DIR.mkdir(parents=True, exist_ok=True)
    (CF_DIR / "charts").mkdir(exist_ok=True)

    # ── Step 1: Build feature panel ───────────────────────────────────────
    print("[1/8] Building feature panel...")
    panel = build_feature_panel(
        start_date=args.start_date,
        min_adv50_vnd=args.min_adv,
        include_fa=not args.no_fa,
    )
    print(f"  Panel: {panel.shape[0]:,} rows, {panel.shape[1]} cols")
    print(f"  Date: {panel['date'].min().date()} to {panel['date'].max().date()}")
    print()

    # ── Step 2: Compute composite scores ──────────────────────────────────
    print("[2/8] Computing composite scores...")
    panel = add_scores(panel)
    print()

    # Save panels
    save_feature_panel(panel)
    save_score_panel(panel)
    write_feature_spec()

    # ── Step 3: IC analysis ────────────────────────────────────────────────
    print("[3/8] Running IC analysis (Test 1)...")
    ic_results = run_ic_analysis(panel)
    ic_year = run_ic_by_year(panel)
    save_ic_results(ic_results, ic_year)

    if not ic_results.empty:
        raw_20d = ic_results[
            (ic_results["signal"] == "capital_footprint_score_raw") &
            (ic_results["forward_return"] == "fwd_ret_20d") &
            (ic_results["regime"] == "all_regimes") &
            (ic_results["liquidity_tier"] == "all")
        ]
        if not raw_20d.empty:
            row = raw_20d.iloc[0]
            print(f"  CF raw IC (20d, all): mean={row['ic_mean']:.4f}, t={row['ic_tstat']:.2f}, hit={row['ic_hit_rate']:.1%}")
    print()

    # ── Step 4: Quantile portfolio ─────────────────────────────────────────
    print("[4/8] Running quantile portfolio test (Test 2)...")
    q_results = run_quantile_portfolio_full(panel)
    save_quantile_results(q_results)
    print()

    # ── Step 5: Event study ────────────────────────────────────────────────
    event_results = pd.DataFrame()
    if not args.quick:
        print("[5/8] Running event study (Test 3)...")
        event_results = run_event_study(panel)
        save_event_study(event_results)
    else:
        print("[5/8] Event study skipped (--quick mode)")
        save_event_study(event_results)
    print()

    # ── Step 6: A3 enhancement tests ──────────────────────────────────────
    a3_results = {}
    if not args.skip_a3:
        print("[6/8] Running A3 enhancement tests (Test 4)...")
        a3_results = run_all_a3_enhancement_tests(panel)
        save_a3_results(a3_results)
    else:
        print("[6/8] A3 enhancement tests skipped")
    print()

    # ── Step 7: Ablation + regime robustness ──────────────────────────────
    print("[7/8] Running feature ablation (Test 6) + regime robustness (Test 5)...")
    ablation = run_feature_ablation(panel)
    save_ablation_results(ablation)

    regime_rob = run_regime_robustness(panel)
    save_regime_robustness(regime_rob)

    # False positives and best winners (if not quick mode)
    if not args.quick:
        fp = classify_false_positives(panel)
        save_false_positives(fp)
        bw = classify_best_winners(panel)
        save_best_winners(bw)
    print()

    # ── Step 8: Generate reports ───────────────────────────────────────────
    print("[8/8] Generating reports...")
    top_stocks = top_stocks_current(panel)
    save_top_current(top_stocks)

    date_range = (panel["date"].min().date().isoformat(), panel["date"].max().date().isoformat())

    # Build IC summary for README
    ic_summary = ""
    if not ic_results.empty:
        top_ics = ic_results[
            (ic_results["regime"] == "all_regimes") &
            (ic_results["liquidity_tier"] == "all") &
            (ic_results["forward_return"] == "fwd_ret_20d")
        ].nlargest(5, "ic_mean")
        if not top_ics.empty:
            ic_summary = "Top 5 signals by 20d IC (all regimes):\n"
            for _, row in top_ics.iterrows():
                ic_summary += f"  - {row['signal']}: IC={row['ic_mean']:.4f}, t={row['ic_tstat']:.2f}\n"

    write_readme(
        n_rows=len(panel),
        n_symbols=panel["symbol"].nunique(),
        date_range=date_range,
        ic_summary=ic_summary,
    )

    write_decision_memo(
        ic_results=ic_results,
        quantile_results=q_results,
        a3_results=a3_results,
        regime_results=regime_rob,
        top_stocks=top_stocks,
    )

    # Package zip
    zip_path = package_review_zip()

    elapsed = time.time() - t0
    print()
    print("=" * 65)
    print(f"Pipeline complete in {elapsed:.0f}s")
    print(f"Review pack: {zip_path}")
    print("=" * 65)
    print()
    print("IMPORTANT: All results are RESEARCH ONLY.")
    print("No production change unless explicitly approved.")


if __name__ == "__main__":
    main()
