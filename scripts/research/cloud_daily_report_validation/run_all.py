"""Run all cloud daily report validation phases in order.

Produces all 15 required output CSVs + 2 HTML reports + review pack.

RESEARCH_ONLY_NOT_PRODUCTION

Usage:
    .venv\\Scripts\\python.exe scripts/research/cloud_daily_report_validation/run_all.py
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

from src.research.cloud_daily_report_validation.action_tests import run_action_validation_full
from src.research.cloud_daily_report_validation.breadth_tests import run_t1_t2_gate_validation_full
from src.research.cloud_daily_report_validation.c3_tests import run_c3_validation_full
from src.research.cloud_daily_report_validation.data_loader import get_scan_date_range, load_scan_files
from src.research.cloud_daily_report_validation.evidence_inventory import build_evidence_registry
from src.research.cloud_daily_report_validation.evidence_search import run_evidence_search_full
from src.research.cloud_daily_report_validation.exit_tests import run_exit_logic_validation_full
from src.research.cloud_daily_report_validation.market_context_tests import run_market_context_validation_full
from src.research.cloud_daily_report_validation.output_inventory import build_output_inventory
from src.research.cloud_daily_report_validation.portfolio_overlay_tests import run_portfolio_overlay_validation_full
from src.research.cloud_daily_report_validation.portfolio_simulation import run_portfolio_simulation_full
from src.research.cloud_daily_report_validation.ranking_tests import run_ranking_validation_full
from src.research.cloud_daily_report_validation.reporting import (
    generate_evidence_inventory_html,
    generate_validation_html,
)
from src.research.cloud_daily_report_validation.review_pack import build_review_pack
from src.research.cloud_daily_report_validation.rs_tests import run_rs_correction_validation_full
from src.research.cloud_daily_report_validation.s3_tests import run_s3_radar_validation_full
from src.research.cloud_daily_report_validation.schema import OUTPUT_DIR, REPORTS_DIR
from src.research.cloud_daily_report_validation.validation_summary import (
    write_all_portfolio_outputs,
    write_validation_summary,
)

RESEARCH_ONLY_GUARD = "RESEARCH_ONLY_NOT_PRODUCTION"


def _alias(src_name: str, dst_name: str) -> None:
    src = OUTPUT_DIR / src_name
    dst = OUTPUT_DIR / dst_name
    if src.is_file():
        shutil.copy2(src, dst)
        logger.info("Aliased %s → %s", src_name, dst_name)


def main() -> None:
    print(f"\n{'='*60}")
    print(f"  {RESEARCH_ONLY_GUARD}")
    print(f"  Cloud Daily Report Validation v0.2 — Full Run")
    print(f"  Date: {date.today()}")
    print(f"{'='*60}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    results_log: list[tuple[str, int, str]] = []

    # Phase 0: Evidence registry
    logger.info("[0] Building evidence registry (with dist risk JSON parse) ...")
    registry_df = build_evidence_registry()
    registry_df.to_csv(OUTPUT_DIR / "evidence_inventory.csv", index=False)
    registry_df.to_csv(OUTPUT_DIR / "cloud_dashboard_evidence_registry.csv", index=False)
    results_log.append(("cloud_dashboard_evidence_registry", len(registry_df), "OK"))

    # Phase 3: Real evidence search
    logger.info("[3] Running repo-wide evidence search ...")
    hits = run_evidence_search_full()
    results_log.append(("evidence_search_hits", len(hits), "OK"))

    # Phase 1: Output inventory
    logger.info("[1] Building output inventory ...")
    inventory_df = build_output_inventory()
    inventory_df.to_csv(OUTPUT_DIR / "output_inventory.csv", index=False)
    inventory_df.to_csv(OUTPUT_DIR / "cloud_dashboard_output_inventory.csv", index=False)
    results_log.append(("cloud_dashboard_output_inventory", len(inventory_df), "OK"))

    # Report scan range
    scan_df = load_scan_files()
    min_d, max_d = get_scan_date_range(scan_df)
    logger.info("Scan data: %s to %s (%d rows)", min_d, max_d, len(scan_df))

    # Phase 5.1: Action tests
    logger.info("[5.1] Running final_action validation ...")
    action_result = run_action_validation_full()
    results_log.append(("final_action_validation", len(action_result), "OK"))

    # Phase 5.2: T1/T2 gate
    logger.info("[5.2] Running T1/T2 gate validation ...")
    breadth_result = run_t1_t2_gate_validation_full()
    results_log.append(("t1_t2_gate_validation", len(breadth_result), "OK"))

    # Phase 5.3: Exit logic
    logger.info("[5.3] Running exit logic validation ...")
    exit_result = run_exit_logic_validation_full()
    results_log.append(("exit_logic_validation", len(exit_result), "OK"))

    # Phase 5.4: Ranking
    logger.info("[5.4] Running ranking validation ...")
    ranking_result = run_ranking_validation_full()
    results_log.append(("ranking_validation", len(ranking_result), "OK"))

    # Phase 5.5: S3 radar
    logger.info("[5.5] Running S3 radar validation ...")
    s3_result = run_s3_radar_validation_full()
    results_log.append(("s3_radar_validation", len(s3_result), "OK"))

    # Phase 5.6: Market context
    logger.info("[5.6] Running market context validation ...")
    market_result = run_market_context_validation_full()
    results_log.append(("market_context_validation", len(market_result), "OK"))

    # Phase 5.7: RS correction (label: INCONCLUSIVE_DIRECTIONAL_ONLY)
    logger.info("[5.7] Running RS correction validation ...")
    rs_result = run_rs_correction_validation_full()
    results_log.append(("rs_correction_validation", len(rs_result), "OK"))

    # Phase 5.8: C3 validation
    logger.info("[5.8] Running RS C3 validation ...")
    c3_result = run_c3_validation_full()
    _alias("c3_validation.csv", "rs_c3_validation.csv")
    results_log.append(("rs_c3_validation", len(c3_result), "OK"))

    # Phase 5.9: Portfolio overlay
    logger.info("[5.9] Running portfolio overlay validation ...")
    overlay_result = run_portfolio_overlay_validation_full()
    results_log.append(("portfolio_overlay_validation", len(overlay_result), "OK"))

    # Phase 6: Portfolio simulation (BLOCKED_BY_DATA)
    logger.info("[6] Writing portfolio simulation outputs (BLOCKED_BY_DATA) ...")
    write_all_portfolio_outputs()
    sim_result = run_portfolio_simulation_full()
    results_log.append(("cloud_action_portfolio_metrics", 7, "OK (BLOCKED_BY_DATA)"))
    results_log.append(("cloud_action_equity_curves", 4, "OK (BLOCKED_BY_DATA)"))
    results_log.append(("cloud_action_turnover_capacity", 3, "OK (BLOCKED_BY_DATA)"))

    # Phase 7: Validation summary
    logger.info("[7] Writing cloud_validation_summary.csv ...")
    write_validation_summary()
    results_log.append(("cloud_validation_summary", 13, "OK"))

    # HTML reports
    logger.info("[HTML] Generating reports ...")
    html_ev = generate_evidence_inventory_html(registry_df, inventory_df)
    (REPORTS_DIR / "evidence_inventory.html").write_text(html_ev, encoding="utf-8")
    all_results = {
        "final_action_validation": action_result,
        "t1_t2_gate_validation": breadth_result,
        "exit_logic_validation": exit_result,
        "ranking_validation": ranking_result,
        "market_context_validation": market_result,
        "rs_correction_validation": rs_result,
        "c3_validation": c3_result,
        "s3_radar_validation": s3_result,
        "portfolio_overlay_validation": overlay_result,
        "portfolio_simulation": sim_result,
    }
    html_val = generate_validation_html(all_results)
    (REPORTS_DIR / "validation_report.html").write_text(html_val, encoding="utf-8")

    # Review pack (captures real pytest output)
    logger.info("[PACK] Building review pack ...")
    date_str = str(date.today()).replace("-", "")
    zip_path = build_review_pack(date_str=date_str)

    # Final summary
    required = [
        "cloud_dashboard_output_inventory.csv", "cloud_dashboard_evidence_registry.csv",
        "final_action_validation.csv", "t1_t2_gate_validation.csv", "exit_logic_validation.csv",
        "ranking_validation.csv", "s3_radar_validation.csv", "market_context_validation.csv",
        "rs_correction_validation.csv", "rs_c3_validation.csv", "portfolio_overlay_validation.csv",
        "cloud_action_portfolio_metrics.csv", "cloud_action_equity_curves.csv",
        "cloud_action_turnover_capacity.csv", "cloud_validation_summary.csv",
        "evidence_search_hits.csv",
    ]
    print(f"\n{'='*60}")
    print(f"  {RESEARCH_ONLY_GUARD} — COMPLETE")
    print(f"{'='*60}")
    print("\nRequired output files:")
    all_ok = True
    for fname in required:
        p = OUTPUT_DIR / fname
        status = "OK" if p.is_file() else "MISSING"
        if status == "MISSING":
            all_ok = False
        print(f"  [{status}] {fname}")
    print(f"\nOverall: {'ALL OK' if all_ok else 'SOME MISSING — check logs'}")
    print(f"Review pack: {zip_path}")
    print(f"Reports:     {REPORTS_DIR}")


if __name__ == "__main__":
    main()
