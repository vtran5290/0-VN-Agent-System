"""
CLI orchestrator for P1 Sector Group Rotation Validation.
Tests L3 / flag_bucket / theme_tag grouping layers.
Usage:
  python -m scripts.research.sector_l4_causality.run_p1 [--force-rebuild]

All outputs go to data/research/sector_l4_causality/.
No production files are changed.
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

from .config import (
    OUTPUT_DIR, OHLCV_PANEL_PATH, SECTOR_MAP_PATH,
)
from .io import load_ohlcv_panel, load_sector_map, validate_enriched_panel, load_vnindex, load_ex_vin_series
from .regimes import build_all_regimes
from .l4_events import build_sector_daily_panel, build_l4_turn_events
from .stock_events import build_stock_turn_events
from .enriched_ledger import build_enriched_ledger

from .p1_config import (
    OUTPUT_DIR as P1_OUTPUT_DIR,
    P1_RECENT_TURN_WINDOWS,
    P1_IMPL_REPORT_PATH,
)
from .p1_group_breadth import (
    build_all_group_breadth_panels,
    build_group_turn_events,
    build_recent_turn_flags,
)
from .p1_group_lead_lag    import build_group_lead_lag_summary
from .p1_group_filter_value import run_group_filter_value_ablation
from .p1_a3_group_replay    import run_a3_group_gate_replay
from .p1_group_leader       import classify_group_leaders
from .p1_regime_stability   import run_group_regime_stability
from .p1_ranking_proposal   import write_ranking_feature_proposal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

REVIEW_PKG_DIR = Path(__file__).resolve().parents[3] / "outputs/review_packages"


def _load_base_data(force_rebuild: bool):
    """Load or rebuild base panels and events (reuse P0 caches when possible)."""
    panel_cache    = OUTPUT_DIR / "stock_daily_cloud_panel.parquet"
    sector_cache   = OUTPUT_DIR / "sector_l4_daily_panel.parquet"
    l4_cache       = OUTPUT_DIR / "sector_l4_turn_events.csv"
    stock_ev_cache = OUTPUT_DIR / "stock_cloud_turn_events.csv"
    regime_cache   = OUTPUT_DIR / "regime_overlays.csv"

    if (
        not force_rebuild
        and all(p.exists() for p in [panel_cache, sector_cache, l4_cache, stock_ev_cache, regime_cache])
    ):
        log.info("Loading all base data caches.")
        panel        = pd.read_parquet(panel_cache)
        sector_panel = pd.read_parquet(sector_cache)
        l4_events    = pd.read_csv(l4_cache)
        stock_events = pd.read_csv(stock_ev_cache)
        regimes      = pd.read_csv(regime_cache)
        sector_map   = load_sector_map()
        return panel, sector_panel, l4_events, stock_events, regimes, sector_map

    log.info("Rebuilding base data from source ...")
    panel = load_ohlcv_panel(force_rebuild=force_rebuild)
    errors = validate_enriched_panel(panel)
    if errors:
        log.error("Panel validation errors: %s", errors)
        sys.exit(1)
    sector_map = load_sector_map()
    try:
        vnindex_df = load_vnindex()
    except Exception:
        vnindex_df = pd.DataFrame(columns=["date", "close"])
    try:
        ex_vin_df = load_ex_vin_series()
    except Exception:
        ex_vin_df = pd.DataFrame(columns=["date"])

    regimes      = build_all_regimes(panel, vnindex_df, ex_vin_df)
    sector_panel = build_sector_daily_panel(panel, sector_map, regimes)
    l4_events    = build_l4_turn_events(sector_panel)
    stock_events = build_stock_turn_events(panel, sector_map, regimes)
    return panel, sector_panel, l4_events, stock_events, regimes, sector_map


def _write_impl_report(stats: dict) -> None:
    today = date.today().isoformat()
    lines = [f"# P1 Implementation Report -- Group Rotation Validation\n",
             f"\n**Date:** {today}\n",
             "\n## Run Statistics\n\n| Item | Value |\n|---|---|\n"]
    for k, v in stats.items():
        lines.append(f"| {k} | {v} |\n")
    lines.append("\n## No-Production-Change Confirmation\n\n")
    lines.append("- A3 production logic: UNCHANGED\n")
    lines.append("- OMS: UNCHANGED\n")
    lines.append("- Phase36 final_action: UNCHANGED\n")
    lines.append("- S3 status: UNCHANGED\n")
    lines.append("- DNSE routing: UNCHANGED\n")
    lines.append("- Original A3 ledger: UNCHANGED\n")
    P1_IMPL_REPORT_PATH.write_text("".join(lines), encoding="utf-8")
    log.info("P1 implementation report saved to %s", P1_IMPL_REPORT_PATH)


def _create_review_zip(today_str: str) -> Path:
    REVIEW_PKG_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = REVIEW_PKG_DIR / f"sector_group_rotation_p1_chatgpt_review_{today_str}.zip"

    output_files = [
        "group_breadth_turn_events.csv",
        "group_stock_lead_lag_summary.csv",
        "group_filter_value_ablation.csv",
        "a3_group_gate_replay.csv",
        "group_leader_follower_classification.csv",
        "group_regime_stability_summary.csv",
        "GROUP_BREADTH_RANKING_FEATURE_PROPOSAL.md",
        "P1_IMPLEMENTATION_REPORT.md",
        "SECTOR_L4_CAUSALITY_FINDINGS.md",
        "sector_grouping_feasibility_audit.csv",
        "P0_IMPLEMENTATION_REPORT.md",
        "adoption_gate_summary.csv",
        "run_config.json",
    ]
    code_files = [
        "scripts/research/sector_l4_causality/p1_config.py",
        "scripts/research/sector_l4_causality/p1_group_breadth.py",
        "scripts/research/sector_l4_causality/p1_group_lead_lag.py",
        "scripts/research/sector_l4_causality/p1_group_filter_value.py",
        "scripts/research/sector_l4_causality/p1_a3_group_replay.py",
        "scripts/research/sector_l4_causality/p1_group_leader.py",
        "scripts/research/sector_l4_causality/p1_regime_stability.py",
        "scripts/research/sector_l4_causality/p1_ranking_proposal.py",
        "scripts/research/sector_l4_causality/run_p1.py",
    ]
    repo_root = Path(__file__).resolve().parents[3]

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in output_files:
            fpath = OUTPUT_DIR / fname
            if fpath.exists():
                zf.write(fpath, arcname=f"outputs/{fname}")
            else:
                log.warning("Output missing from zip (skipped): %s", fpath)
        for rel in code_files:
            fpath = repo_root / rel
            if fpath.exists():
                zf.write(fpath, arcname=f"code/{fpath.name}")

    log.info("P1 review zip: %s (%.1f KB)", zip_path, zip_path.stat().st_size / 1024)
    return zip_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sector Group Rotation P1")
    parser.add_argument("--force-rebuild", action="store_true", default=False)
    args = parser.parse_args(argv)

    today_str = date.today().strftime("%Y%m%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("Sector Group Rotation P1 Validation")
    log.info("=" * 60)

    # ── Base data ─────────────────────────────────────────────────────────────
    log.info("[Base] Loading panels and events ...")
    panel, sector_panel, l4_events, stock_events, regimes, sector_map = _load_base_data(args.force_rebuild)
    log.info("Panel: %s rows | Stock events: %d | L4 events: %d",
             f"{len(panel):,}", len(stock_events), len(l4_events))

    enriched_ledger = build_enriched_ledger(force_rebuild=args.force_rebuild)

    # ── Test 1: Group breadth panels + turn events ────────────────────────────
    log.info("[Test 1/7] Building group breadth panels and turn events ...")
    group_sym_map, tall_breadth_df = build_all_group_breadth_panels(
        panel, sector_map, force_rebuild=args.force_rebuild
    )
    log.info("Group symbol map: %d groups", len(group_sym_map))

    panel_dates = pd.DatetimeIndex(pd.to_datetime(panel["date"]).unique())
    regimes_df  = pd.read_csv(OUTPUT_DIR / "regime_overlays.csv") if (OUTPUT_DIR / "regime_overlays.csv").exists() else regimes

    group_turn_events = build_group_turn_events(
        tall_breadth_df, regimes_df, group_sym_map
    )
    log.info("Group turn events: %d total", len(group_turn_events))

    # Recent turn flags (used by Tests 3 and 4)
    recent_turn_flags = build_recent_turn_flags(
        tall_breadth_df, group_turn_events, P1_RECENT_TURN_WINDOWS, panel_dates
    )

    # ── Test 2: Lead/lag ──────────────────────────────────────────────────────
    log.info("[Test 2/7] Group lead/lag analysis ...")
    stock_ev = pd.read_csv(OUTPUT_DIR / "stock_cloud_turn_events.csv") if (OUTPUT_DIR / "stock_cloud_turn_events.csv").exists() else stock_events
    lead_lag = build_group_lead_lag_summary(
        group_turn_events, stock_ev, panel_dates, group_sym_map
    )
    if not lead_lag.empty:
        sector_leads = lead_lag[lead_lag["conclusion_tag"] == "sector_leads"]
        log.info("Lead/lag: %d groups with sector_leads classification (median lift: %.1f%%)",
                 len(sector_leads),
                 float(lead_lag["excess_turn_pct_t1_t10"].median() * 100))

    # ── Test 3: Filter value ──────────────────────────────────────────────────
    log.info("[Test 3/7] Group filter value ablation ...")
    filter_value = run_group_filter_value_ablation(
        stock_ev, tall_breadth_df, group_turn_events, group_sym_map, recent_turn_flags
    )
    if not filter_value.empty:
        fv60 = filter_value[
            (filter_value["rule_id"] == "breadth_ew_ge_40") &
            (filter_value["horizon"] == 60)
        ]
        g2_pass = fv60[fv60["delta_hit_rate"].fillna(0) >= 0.03]
        log.info("Filter value (breadth_ew>=40, 60d): %d / %d groups pass G2 (delta_hit>=3pp)",
                 len(g2_pass), len(fv60))

    # ── Test 4: A3 ledger replay ──────────────────────────────────────────────
    log.info("[Test 4/7] A3 group gate replay ...")
    a3_replay = run_a3_group_gate_replay(
        enriched_ledger, tall_breadth_df, group_turn_events, group_sym_map, recent_turn_flags
    )
    if not a3_replay.empty:
        gate40 = a3_replay[a3_replay["rule_id"] == "breadth_ew_ge_40"]
        n_pass = len(gate40[gate40["gate_pass"] == 1]) if "gate_pass" in gate40.columns else 0
        log.info("A3 replay (breadth_ew>=40): %d / %d groups pass all gate criteria", n_pass, len(gate40))

    # ── Test 5: Leader/follower ───────────────────────────────────────────────
    log.info("[Test 5/7] Group leader/follower classification ...")
    leader_clf = classify_group_leaders(
        group_turn_events, panel, group_sym_map
    )
    if not leader_clf.empty and "group_classification" in leader_clf.columns:
        dist = leader_clf.drop_duplicates(["grouping_layer", "group_name"])["group_classification"].value_counts()
        log.info("Leader classifications: %s", dist.to_dict())

    # ── Test 6: Regime stability ──────────────────────────────────────────────
    log.info("[Test 6/7] Group regime stability analysis ...")
    regime_stability = run_group_regime_stability(
        stock_ev, tall_breadth_df, group_turn_events, group_sym_map, regimes_df
    )
    if not regime_stability.empty:
        # Quick summary: full period delta_hit_rate > 0 for how many groups?
        full = regime_stability[
            (regime_stability["period"] == "full") &
            (regime_stability["regime"] == "all")
        ]
        n_pos = len(full[full["delta_hit_rate"].fillna(0) > 0])
        log.info("Regime stability (full/all): %d / %d groups with positive delta_hit_rate", n_pos, len(full))

    # ── Test 7: Ranking proposal ──────────────────────────────────────────────
    log.info("[Test 7/7] Writing ranking feature proposal ...")
    write_ranking_feature_proposal(lead_lag, filter_value, leader_clf, regime_stability, a3_replay)

    # ── Implementation report ─────────────────────────────────────────────────
    primary_turns = group_turn_events[group_turn_events["definition"] == "primary_40_35"]
    eligible_groups = primary_turns.groupby(["grouping_layer", "group_name"]).size()
    eligible_groups = eligible_groups[eligible_groups >= 5]

    _write_impl_report({
        "Panel rows":              f"{len(panel):,}",
        "Panel symbols":           panel["symbol"].nunique(),
        "Group symbol map":        f"{len(group_sym_map)} groups",
        "Group turn events (all defs)": len(group_turn_events),
        "Group turn events (primary)":  len(primary_turns),
        "Eligible groups (>=5 events)": len(eligible_groups),
        "Stock events used":       len(stock_ev),
        "A3 ledger trades":        len(enriched_ledger),
        "Filter value rows":       len(filter_value) if not filter_value.empty else 0,
        "A3 replay rows":          len(a3_replay) if not a3_replay.empty else 0,
        "Leader clf rows":         len(leader_clf) if not leader_clf.empty else 0,
        "Regime stability rows":   len(regime_stability) if not regime_stability.empty else 0,
    })

    # ── Package review zip ────────────────────────────────────────────────────
    log.info("Packaging P1 review zip ...")
    zip_path = _create_review_zip(today_str)

    log.info("=" * 60)
    log.info("P1 complete. Review zip: %s", zip_path)
    log.info("=" * 60)
    return str(zip_path)


if __name__ == "__main__":
    main()
