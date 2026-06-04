"""
CLI orchestrator for P0 Sector L4 Causality research.
Usage:
  python -m scripts.research.sector_l4_causality.run_all [options]

All outputs go to data/research/sector_l4_causality/.
No production files are changed.
"""
from __future__ import annotations
import argparse
import json
import logging
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    OUTPUT_DIR, OHLCV_PANEL_PATH, SECTOR_MAP_PATH,
    VNINDEX_PARQUET, EX_VIN_SERIES_PATH, PLACEBO_ITERS_P0,
)
from .io import load_ohlcv_panel, load_sector_map, load_vnindex, load_ex_vin_series, validate_enriched_panel
from .coverage import build_coverage_audit, small_sector_diagnostics
from .regimes import build_all_regimes
from .l4_events import build_sector_daily_panel, build_l4_turn_events
from .stock_events import build_stock_turn_events
from .lead_lag import build_lead_lag_summary
from .leader import classify_leaders
from .filter_value import (
    compute_baseline, run_ablation, run_regime_stratified,
    run_threshold_sweep, run_a3_ledger_replay,
)
from .placebo import run_placebo
from .adoption_gates import evaluate_gates
from .report import generate_findings_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def _write_missing_fields(fields: list[str]) -> None:
    path = OUTPUT_DIR / "missing_fields_to_add.md"
    text = "# Missing Fields\n\nThese fields are referenced in the plan but not available in current repo data:\n\n"
    for f in fields:
        text += f"- {f}\n"
    path.write_text(text, encoding="utf-8")
    log.info("Missing fields written to %s", path)


def _write_run_config(args, panel: pd.DataFrame) -> dict:
    cfg = {
        "run_date":         date.today().isoformat(),
        "git_commit":       _git_commit(),
        "ohlcv_panel":      str(OHLCV_PANEL_PATH),
        "panel_latest_date": str(panel["date"].max())[:10],
        "start_date":       args.start,
        "end_date":         args.end if args.end != "latest" else str(panel["date"].max())[:10],
        "include_unknown":  args.include_unknown,
        "min_l4_symbols":   args.min_l4_symbols,
        "placebo_iters":    args.placebo_iters,
        "run_placebo":      args.run_placebo,
        "full_and_ex_vin":  args.full_and_ex_vin,
    }
    out = OUTPUT_DIR / "run_config.json"
    out.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    log.info("Run config saved to %s", out)
    return cfg


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sector L4 Causality P0")
    parser.add_argument("--start",           default="2012-01-01")
    parser.add_argument("--end",             default="latest")
    parser.add_argument("--output-dir",      default=str(OUTPUT_DIR))
    parser.add_argument("--include-unknown", action="store_true", default=False)
    parser.add_argument("--min-l4-symbols",  type=int, default=5)
    parser.add_argument("--run-placebo",     action="store_true", default=True)
    parser.add_argument("--placebo-iters",   type=int, default=PLACEBO_ITERS_P0)
    parser.add_argument("--full-and-ex-vin", action="store_true", default=True)
    parser.add_argument("--write-report",    action="store_true", default=True)
    parser.add_argument("--force-rebuild",   action="store_true", default=False)
    args = parser.parse_args(argv)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("=" * 60)
    log.info("Sector L4 Causality P0 — output dir: %s", OUTPUT_DIR)
    log.info("=" * 60)

    # ── Step 1: Load and enrich OHLCV panel ──────────────────────────────────
    log.info("[1/10] Loading enriched panel …")
    panel = load_ohlcv_panel(force_rebuild=args.force_rebuild)
    errors = validate_enriched_panel(panel)
    if errors:
        log.error("Panel validation failed: %s", errors)
        sys.exit(1)
    log.info("Panel: %s rows, %d symbols, dates %s to %s",
             f"{len(panel):,}", panel["symbol"].nunique(),
             str(panel["date"].min())[:10], str(panel["date"].max())[:10])

    run_config = _write_run_config(args, panel)

    # ── Step 2: Sector map ────────────────────────────────────────────────────
    log.info("[2/10] Loading sector map …")
    sector_map = load_sector_map()

    # ── Step 3: Coverage audit ────────────────────────────────────────────────
    log.info("[3/10] Coverage audit …")
    coverage_audit = build_coverage_audit(sector_map, panel)
    small_sector_diagnostics(coverage_audit)

    # ── Step 4: Regime overlays ───────────────────────────────────────────────
    log.info("[4/10] Building regime overlays …")
    try:
        vnindex_df = load_vnindex()
    except Exception as e:
        log.warning("Could not load VNINDEX: %s", e)
        vnindex_df = pd.DataFrame(columns=["date", "close"])
    try:
        ex_vin_df = load_ex_vin_series()
    except Exception as e:
        log.warning("Could not load ex-VIN series: %s", e)
        ex_vin_df = pd.DataFrame(columns=["date"])

    regimes = build_all_regimes(panel, vnindex_df, ex_vin_df)

    # ── Step 5: Sector daily panel ────────────────────────────────────────────
    log.info("[5/10] Building sector daily panel …")
    sector_panel = build_sector_daily_panel(
        panel, sector_map, regimes,
        include_unknown=args.include_unknown,
    )

    # ── Step 6: L4 turn events ────────────────────────────────────────────────
    log.info("[6/10] Detecting L4 turn events …")
    end_date = args.end if args.end != "latest" else None
    l4_events = build_l4_turn_events(sector_panel, start_date=args.start, end_date=end_date)
    log.info("L4 events: %d total, %d primary",
             len(l4_events),
             len(l4_events[l4_events["definition"] == "primary_40_35"]))

    # ── Step 7: Stock cloud turn events ──────────────────────────────────────
    log.info("[7/10] Building stock cloud turn events …")
    stock_events = build_stock_turn_events(
        panel, sector_map, regimes,
        start_date=args.start, end_date=end_date,
    )
    log.info("Stock turn events: %d", len(stock_events))

    # ── Step 8: Analytical modules ────────────────────────────────────────────
    log.info("[8/10] Running P0 analytics …")

    panel_dates = pd.DatetimeIndex(panel["date"].unique())
    lead_lag    = build_lead_lag_summary(l4_events, stock_events, panel_dates)
    leader_clf  = classify_leaders(l4_events, panel, sector_map)

    compute_baseline(stock_events)
    abl_full   = run_ablation(stock_events, sector_panel, ex_vin_only=False)
    abl_exv    = run_ablation(stock_events, sector_panel, ex_vin_only=True)
    regime_strat = run_regime_stratified(stock_events, sector_panel)
    thresh_sweep = run_threshold_sweep(stock_events, sector_panel)
    ledger_replay = run_a3_ledger_replay(sector_panel)

    # ── Step 9: Placebo ───────────────────────────────────────────────────────
    if args.run_placebo:
        log.info("[9/10] Running placebo shuffles (%d iters) …", args.placebo_iters)
        # Get real delta_hit_rate at 60d from ablation
        real_dhr = np.nan
        if not abl_full.empty and "delta_hit_rate" in abl_full.columns:
            r = abl_full[
                abl_full["rule_id"].str.contains("ge_40", na=False) &
                (abl_full["horizon"] == 60)
            ]
            if not r.empty:
                real_dhr = float(r.iloc[0]["delta_hit_rate"])
        import numpy as _np
        placebo_res = run_placebo(
            stock_events, sector_map, panel,
            real_delta_hit_rate_60d=real_dhr if not _np.isnan(real_dhr) else 0.0,
            n_iters=args.placebo_iters,
        )
    else:
        log.info("[9/10] Placebo skipped (--run-placebo not set).")
        placebo_res = pd.DataFrame()

    # ── Step 10: Adoption gates + report ─────────────────────────────────────
    log.info("[10/10] Evaluating adoption gates …")
    gate_summary = evaluate_gates(
        lead_lag, abl_full, abl_exv,
        ledger_replay, placebo_res, coverage_audit,
    )
    final_verdict = gate_summary.iloc[0]["final_verdict"] if not gate_summary.empty else "DASHBOARD_WARNING_ONLY"
    log.info("Final verdict: %s", final_verdict)

    # Missing fields
    _write_missing_fields([
        "native_market_cap — not available; adv50 used as liquidity proxy",
        "foreign_flow_daily — not available; P2 only",
        "beta_vs_vnindex — not pre-computed; derive from rolling returns if needed",
    ])

    # Findings report
    if args.write_report:
        generate_findings_report(
            run_config, coverage_audit, l4_events,
            lead_lag, abl_full, abl_exv,
            ledger_replay, placebo_res, leader_clf, gate_summary,
        )

    log.info("=" * 60)
    log.info("P0 pipeline complete. Outputs in: %s", OUTPUT_DIR)
    log.info("Verdict: %s", final_verdict)
    log.info("=" * 60)
    return final_verdict


if __name__ == "__main__":
    main()
