"""
CLI orchestrator for P0.1 Sector L4 Causality review fixes.
Runs Tasks 1-5 from the ChatGPT P0.1 review handoff.
Usage:
  python -m scripts.research.sector_l4_causality.run_p01 [--force-rebuild]

All outputs go to data/research/sector_l4_causality/.
No production files are changed.
"""
from __future__ import annotations
import argparse
import logging
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

from .config import (
    OUTPUT_DIR, OHLCV_PANEL_PATH, SECTOR_MAP_PATH,
)
from .io import load_ohlcv_panel, load_sector_map, validate_enriched_panel
from .l4_events import build_sector_daily_panel, build_l4_turn_events
from .stock_events import build_stock_turn_events
from .enriched_ledger import build_enriched_ledger
from .filter_value import (
    run_a3_ledger_replay_enriched,
    run_ablation_by_sector_size,
)
from .sector_grouping import build_sector_grouping_feasibility
from .report import append_p01_section

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

REVIEW_PKG_DIR = Path(__file__).resolve().parents[3] / "outputs/review_packages"


def _load_or_rebuild(force_rebuild: bool):
    """Load cached panels / events or rebuild if force_rebuild."""
    panel_cache = OUTPUT_DIR / "stock_daily_cloud_panel.parquet"
    sector_cache = OUTPUT_DIR / "sector_l4_daily_panel.parquet"
    l4_cache = OUTPUT_DIR / "sector_l4_turn_events.csv"
    stock_ev_cache = OUTPUT_DIR / "stock_cloud_turn_events.csv"

    if (
        not force_rebuild
        and panel_cache.exists()
        and sector_cache.exists()
        and l4_cache.exists()
        and stock_ev_cache.exists()
    ):
        log.info("Loading all caches (pass --force-rebuild to regenerate).")
        panel = pd.read_parquet(panel_cache)
        sector_panel = pd.read_parquet(sector_cache)
        l4_events = pd.read_csv(l4_cache)
        stock_events = pd.read_csv(stock_ev_cache)
        sector_map = load_sector_map()
        return panel, sector_panel, l4_events, stock_events, sector_map

    log.info("Rebuilding panels from source parquet ...")
    panel = load_ohlcv_panel(force_rebuild=force_rebuild)
    errors = validate_enriched_panel(panel)
    if errors:
        log.error("Panel validation errors: %s", errors)
        sys.exit(1)

    sector_map = load_sector_map()
    from .regimes import build_all_regimes
    from .io import load_vnindex, load_ex_vin_series
    try:
        vnindex_df = load_vnindex()
    except Exception:
        vnindex_df = pd.DataFrame(columns=["date", "close"])
    try:
        ex_vin_df = load_ex_vin_series()
    except Exception:
        ex_vin_df = pd.DataFrame(columns=["date"])
    regimes = build_all_regimes(panel, vnindex_df, ex_vin_df)

    sector_panel = build_sector_daily_panel(panel, sector_map, regimes)
    l4_events = build_l4_turn_events(sector_panel)
    stock_events = build_stock_turn_events(panel, sector_map, regimes)

    return panel, sector_panel, l4_events, stock_events, sector_map


def _create_review_zip(today_str: str) -> Path:
    """Package all P0.1 outputs into a review zip."""
    REVIEW_PKG_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = REVIEW_PKG_DIR / f"sector_l4_causality_p0_1_chatgpt_review_{today_str}.zip"

    # Files to include
    output_files = [
        "a3_ledger_enriched_with_sector_l4.csv",
        "a3_ledger_sector_gate_replay_enriched.csv",
        "filter_value_ablation_by_sector_size.csv",
        "sector_grouping_feasibility_audit.csv",
        "SECTOR_L4_CAUSALITY_FINDINGS.md",
        "P0_IMPLEMENTATION_REPORT.md",
        # Carry over key P0 outputs for context
        "adoption_gate_summary.csv",
        "adoption_gate_detail.csv",
        "sector_l4_coverage_audit.csv",
        "small_sector_diagnostics.csv",
        "sector_stock_lead_lag_summary.csv",
        "filter_value_ablation_full.csv",
        "filter_value_ablation_ex_vin.csv",
        "placebo_sector_shuffle_summary.csv",
        "leader_vs_sector_classification.csv",
        "a3_ledger_sector_gate_replay.csv",
        "run_config.json",
    ]

    # Code files to diff-review
    code_files = [
        "scripts/research/sector_l4_causality/enriched_ledger.py",
        "scripts/research/sector_l4_causality/sector_grouping.py",
        "scripts/research/sector_l4_causality/filter_value.py",
        "scripts/research/sector_l4_causality/report.py",
        "scripts/research/sector_l4_causality/run_p01.py",
    ]

    repo_root = Path(__file__).resolve().parents[3]

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in output_files:
            fpath = OUTPUT_DIR / fname
            if fpath.exists():
                zf.write(fpath, arcname=f"outputs/{fname}")
                log.debug("Zipped: outputs/%s", fname)
            else:
                log.warning("Output missing (skipped): %s", fpath)
        for rel in code_files:
            fpath = repo_root / rel
            if fpath.exists():
                zf.write(fpath, arcname=f"code/{fpath.name}")
                log.debug("Zipped code: %s", fpath.name)

    log.info("P0.1 review zip: %s (%.1f KB)", zip_path, zip_path.stat().st_size / 1024)
    return zip_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sector L4 Causality P0.1")
    parser.add_argument("--force-rebuild", action="store_true", default=False)
    args = parser.parse_args(argv)

    today_str = date.today().strftime("%Y%m%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("Sector L4 Causality P0.1 Review Fixes")
    log.info("=" * 60)

    # Load (cached or rebuild)
    panel, sector_panel, l4_events, stock_events, sector_map = _load_or_rebuild(args.force_rebuild)

    log.info(
        "Panel: %s rows, %d symbols | Sector panel: %s rows | "
        "L4 events: %d | Stock events: %d",
        f"{len(panel):,}", panel["symbol"].nunique(),
        f"{len(sector_panel):,}",
        len(l4_events), len(stock_events),
    )

    # ── Task 1: Enriched A3 ledger ────────────────────────────────────────────
    log.info("[Task 1/5] Building enriched A3 ledger ...")
    enriched_ledger = build_enriched_ledger(force_rebuild=args.force_rebuild)
    log.info("Enriched ledger: %d rows", len(enriched_ledger))

    # ── Task 2: A3 gate replay with enriched ledger ───────────────────────────
    log.info("[Task 2/5] Running enriched A3 sector gate replay ...")
    enriched_replay = run_a3_ledger_replay_enriched(enriched_ledger, sector_panel)
    if not enriched_replay.empty:
        for _, r in enriched_replay.iterrows():
            log.info(
                "  [replay] %-18s n=%d blocked=%d retention=%.3f bl_ratio=%.2f gate=%s",
                r["rule_id"], r["n_trades"], r["n_blocked"],
                r["retention_pct"], r["blocked_loser_winner_ratio"],
                r["adoption_gate_pass"],
            )

    # ── Task 3: Filter-value by sector-size bucket ────────────────────────────
    log.info("[Task 3/5] Running filter-value ablation by sector-size bucket ...")
    ablation_by_size = run_ablation_by_sector_size(stock_events, sector_panel, sector_map)
    if not ablation_by_size.empty:
        # Print key n_ge_5 result at 60d
        key = ablation_by_size[
            (ablation_by_size["sector_size_group"] == "n_ge_5") &
            (ablation_by_size["rule_id"] == "l4_ew_ge_40") &
            (ablation_by_size["horizon"] == 60)
        ]
        if not key.empty:
            log.info(
                "n_ge_5 / l4_ew_ge_40 / 60d: delta_hit_rate=%.4f, delta_mean=%.4f, n=%d",
                key.iloc[0]["delta_hit_rate"],
                key.iloc[0]["delta_mean"],
                key.iloc[0]["n_gate"],
            )

    # ── Task 4: Sector grouping feasibility ───────────────────────────────────
    log.info("[Task 4/5] Building sector grouping feasibility audit ...")
    grouping_audit = build_sector_grouping_feasibility(
        sector_map, stock_events, panel, l4_events
    )
    if not grouping_audit.empty:
        eligible = grouping_audit[grouping_audit["eligible_for_p1"] == 1]
        log.info("P1-eligible groupings: %d", len(eligible))

    # ── Task 5: Update findings report ───────────────────────────────────────
    log.info("[Task 5/5] Appending P0.1 section to findings report ...")
    append_p01_section(enriched_replay, ablation_by_size, grouping_audit)

    # ── Package review zip ────────────────────────────────────────────────────
    log.info("Packaging P0.1 review zip ...")
    zip_path = _create_review_zip(today_str)

    log.info("=" * 60)
    log.info("P0.1 complete. Review zip: %s", zip_path)
    log.info("=" * 60)
    return str(zip_path)


if __name__ == "__main__":
    main()
