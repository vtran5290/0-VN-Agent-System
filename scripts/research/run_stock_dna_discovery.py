"""
Stock DNA Discovery — CLI runner
Builds the feature panel, detects touch events across all candidate lines/tolerances,
runs walk-forward scoring, builds symbol profiles, and runs the shuffled-null benchmark.

Usage:
  python scripts/research/run_stock_dna_discovery.py \
    --start 2016-01-01 \
    --end 2026-05-31 \
    --min-adv-vnd 5000000000 \
    --output-dir data/research/stock_dna

RESEARCH ONLY — does not modify production A3 logic, OMS, or DNSE.
"""
import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.features import build_dna_panel
from src.trading.research.stock_dna.profiles import (
    _oos_cutoff_date,
    build_symbol_profiles,
    build_walkforward_line_scores,
    collect_all_touch_events,
    compute_oos_lift,
)
from src.trading.research.stock_dna.reporting import (
    save_line_scores,
    save_open_questions,
    save_symbol_profiles_csv,
    save_symbol_profiles_json,
)
from src.trading.research.stock_dna.scoring import assign_edge_confidence, run_shuffled_null_benchmark
from src.trading.research.stock_dna.schema import DNA_DIR, RESEARCH_ONLY_LABEL, assert_output_path_safe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("stock_dna.discovery")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock DNA Discovery pipeline")
    parser.add_argument("--start",       default="2016-01-01",  help="Panel start date")
    parser.add_argument("--end",         default=None,          help="Panel end date (default: latest available)")
    parser.add_argument("--min-adv-vnd", default=5_000_000_000, type=float, help="Minimum ADV20 in VND")
    parser.add_argument("--output-dir",  default=str(DNA_DIR),  help="Output directory")
    parser.add_argument("--data-dir",    default="data",         help="Root data directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    data_dir   = Path(args.data_dir)

    assert_output_path_safe(output_dir)

    logger.info("=" * 60)
    logger.info("Stock DNA Discovery — %s", RESEARCH_ONLY_LABEL)
    logger.info("=" * 60)

    # Step 1: Build feature panel
    logger.info("[1/5] Building DNA feature panel...")
    panel = build_dna_panel(
        data_dir=data_dir,
        start_date=args.start,
        end_date=args.end,
        min_adv20_vnd=args.min_adv_vnd,
        apply_liquidity_filter=True,
    )
    logger.info("Panel: %d rows, %d symbols", len(panel), panel["symbol"].nunique())

    if panel.empty:
        logger.error("Panel is empty — check data sources. Exiting.")
        sys.exit(1)

    # Step 2: Collect all touch events
    logger.info("[2/5] Collecting touch events across all candidate lines and tolerances...")
    touch_df = collect_all_touch_events(panel)
    logger.info("Touch events: %d total", len(touch_df))

    if touch_df.empty:
        logger.warning("No touch events detected — verify panel has sufficient history and liquid stocks.")

    # Step 3: Walk-forward line scoring
    logger.info("[3/5] Building walk-forward line scores...")
    if not touch_df.empty:
        wf_scores = build_walkforward_line_scores(panel, touch_df)
        save_line_scores(wf_scores, output_dir)
        logger.info("Walk-forward scores: %d rows", len(wf_scores))
    else:
        wf_scores = __import__("pandas").DataFrame()
        logger.warning("Skipping walk-forward scoring — no touch events.")

    # Step 4: Build symbol profiles
    logger.info("[4/5] Building per-symbol DNA profiles...")
    if not wf_scores.empty:
        profiles = build_symbol_profiles(touch_df, wf_scores, panel)
        save_symbol_profiles_csv(profiles, output_dir)
        save_symbol_profiles_json(profiles, output_dir)

        n_med = len(profiles[profiles["confidence"].isin(["MEDIUM", "HIGH"])])
        n_rej = len(profiles[profiles["confidence"] == "NONE"])
        logger.info(
            "Profiles: %d total, %d MEDIUM+, %d NONE (rejected)",
            len(profiles), n_med, n_rej,
        )
    else:
        profiles = __import__("pandas").DataFrame()
        logger.warning("Skipping profile build — no walk-forward scores.")

    # Populate oos_lift on profiles now that we have full touch_df
    if not profiles.empty and not touch_df.empty:
        oos_start = _oos_cutoff_date(panel)
        oos_lift_result = compute_oos_lift(touch_df, profiles, oos_start)
        profiles["oos_lift"] = oos_lift_result.get("z_score", float("nan"))
        logger.info(
            "OOS lift z=%.2f, selected_br=%.3f, baseline_br=%.3f, pass=%s",
            oos_lift_result.get("z_score", float("nan")),
            oos_lift_result.get("selected_bounce_rate_20d", float("nan")),
            oos_lift_result.get("baseline_bounce_rate_20d", float("nan")),
            oos_lift_result.get("pass_fail", False),
        )
        # Re-save with oos_lift populated
        save_symbol_profiles_csv(profiles, output_dir)
        save_symbol_profiles_json(profiles, output_dir)

        # Save full OOS lift detail as JSON for report
        import json
        oos_lift_path = output_dir / "stock_dna_oos_lift.json"
        oos_lift_serializable = {
            k: (v if not isinstance(v, float) or not __import__("math").isnan(v) else None)
            for k, v in oos_lift_result.items()
            if not isinstance(v, dict)
        }
        oos_lift_serializable["by_year"]   = oos_lift_result.get("by_year", {})
        oos_lift_serializable["by_regime"] = oos_lift_result.get("by_regime", {})
        with open(oos_lift_path, "w", encoding="utf-8") as f:
            json.dump(oos_lift_serializable, f, indent=2, default=str)
        logger.info("OOS lift detail saved: %s", oos_lift_path)

    # Step 5: Shuffled-null benchmark
    logger.info("[5/5] Running shuffled-null benchmark...")
    null_result: dict = {}
    if not touch_df.empty and not profiles.empty:
        null_result = run_shuffled_null_benchmark(touch_df, profiles)
        from src.trading.research.stock_dna.reporting import save_null_benchmark
        save_null_benchmark(null_result, output_dir)
        logger.info(
            "Null benchmark: z=%.2f, passes=%s",
            null_result.get("z_score", float("nan")),
            null_result.get("passes_null_test", False),
        )
    else:
        logger.warning("Skipping null benchmark — insufficient data.")

    # Post-step: enrich profiles with per_symbol_null_z, edge_confidence, production_status
    if not profiles.empty and null_result:
        from src.trading.research.stock_dna.schema import DNAConfidence, DNAProductionStatus

        by_sym_z: dict = null_result.get("by_symbol_z_score", {})

        # Universe median bounce rate across MEDIUM+ profiles — used as directional baseline
        # for the bounce_rate differential fed to assign_edge_confidence (council v3 fix)
        med_plus_mask = profiles["confidence"].isin([DNAConfidence.MEDIUM.value, DNAConfidence.HIGH.value])
        universe_br_median = float(
            profiles.loc[med_plus_mask, "bounce_rate_20d"].dropna().median()
        ) if med_plus_mask.any() else 0.50

        def _prod_status(row: "pd.Series") -> str:  # type: ignore[name-defined]
            sc = row.get("sample_confidence", row.get("confidence", DNAConfidence.NONE.value))
            ec = row.get("edge_confidence", "NONE")
            if sc in (DNAConfidence.NONE.value, DNAConfidence.LOW.value):
                return DNAProductionStatus.REJECT.value if sc == DNAConfidence.NONE.value else DNAProductionStatus.WATCHLIST_ONLY.value
            # MEDIUM or HIGH sample confidence
            if ec in ("WEAK", "MODERATE", "STRONG"):
                return DNAProductionStatus.RESEARCH_ANNOTATION_ONLY.value
            return DNAProductionStatus.WATCHLIST_ONLY.value

        for idx, row in profiles.iterrows():
            sym = row["symbol"]
            z = by_sym_z.get(sym, float("nan"))
            profiles.at[idx, "per_symbol_null_z"] = z
            br = row.get("bounce_rate_20d", float("nan"))
            # lift = differential vs universe median (council v3: must be > 0 for directional gate)
            lift_diff = (float(br) - universe_br_median) if not __import__("math").isnan(float(br) if br is not None else float("nan")) else float("nan")
            ec = assign_edge_confidence(
                per_symbol_null_z=z,
                lift=lift_diff,
                median_fwd_ret=row.get("median_fwd_ret_20d", float("nan")),
            )
            profiles.at[idx, "edge_confidence"] = ec
            profiles.at[idx, "production_status"] = _prod_status(profiles.loc[idx])

        save_symbol_profiles_csv(profiles, output_dir)
        save_symbol_profiles_json(profiles, output_dir)

        n_raa = (profiles["production_status"] == DNAProductionStatus.RESEARCH_ANNOTATION_ONLY.value).sum()
        n_wl  = (profiles["production_status"] == DNAProductionStatus.WATCHLIST_ONLY.value).sum()
        logger.info(
            "Post-step production_status: RESEARCH_ANNOTATION_ONLY=%d, WATCHLIST_ONLY=%d",
            n_raa, n_wl,
        )

    # Save open questions
    save_open_questions(output_dir)

    logger.info("=" * 60)
    logger.info("Discovery complete. Outputs in: %s", output_dir)
    logger.info("Next step: run run_stock_dna_a3_overlay_backtest.py")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
