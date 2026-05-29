"""Generate HTML validation reports for cloud daily report validation.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

RESEARCH_ONLY_GUARD = "RESEARCH_ONLY_NOT_PRODUCTION"
print(f"[{RESEARCH_ONLY_GUARD}] Generating HTML reports...")

import pandas as pd

from src.research.cloud_daily_report_validation.reporting import (
    generate_evidence_inventory_html,
    generate_validation_html,
)
from src.research.cloud_daily_report_validation.schema import OUTPUT_DIR, REPORTS_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _load_csv_if_exists(path: Path) -> pd.DataFrame:
    if path.is_file():
        try:
            return pd.read_csv(path)
        except Exception as e:
            logger.warning("Could not load %s: %s", path, e)
    return pd.DataFrame()


def main(args: argparse.Namespace) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Evidence inventory HTML (requires registry + inventory CSVs)
    registry_df = _load_csv_if_exists(OUTPUT_DIR / "evidence_inventory.csv")
    inventory_df = _load_csv_if_exists(OUTPUT_DIR / "output_inventory.csv")

    if not registry_df.empty or not inventory_df.empty:
        logger.info("Generating evidence inventory HTML...")
        html = generate_evidence_inventory_html(registry_df, inventory_df)
        out_path = REPORTS_DIR / "evidence_inventory.html"
        out_path.write_text(html, encoding="utf-8")
        logger.info("Written: %s", out_path)
    else:
        logger.warning("No registry/inventory CSVs found — run run_evidence_inventory.py first")

    # Main validation HTML (all test results)
    all_results: dict = {}
    test_files = {
        "final_action_validation": OUTPUT_DIR / "final_action_validation.csv",
        "t1_t2_gate_validation": OUTPUT_DIR / "t1_t2_gate_validation.csv",
        "exit_logic_validation": OUTPUT_DIR / "exit_logic_validation.csv",
        "ranking_validation": OUTPUT_DIR / "ranking_validation.csv",
        "rs_correction_validation": OUTPUT_DIR / "rs_correction_validation.csv",
        "c3_validation": OUTPUT_DIR / "c3_validation.csv",
        "s3_radar_validation": OUTPUT_DIR / "s3_radar_validation.csv",
        "portfolio_overlay_validation": OUTPUT_DIR / "portfolio_overlay_validation.csv",
        "portfolio_simulation": OUTPUT_DIR / "portfolio_simulation.csv",
    }
    for name, path in test_files.items():
        df = _load_csv_if_exists(path)
        if not df.empty:
            all_results[name] = df

    if all_results:
        logger.info("Generating main validation HTML (%d test sections)...", len(all_results))
        html = generate_validation_html(all_results)
        out_path = REPORTS_DIR / "validation_report.html"
        out_path.write_text(html, encoding="utf-8")
        alias_path = REPORTS_DIR / "cloud_daily_report_validation.html"
        alias_path.write_text(html, encoding="utf-8")
        logger.info("Written: %s", out_path)
        logger.info("Written: %s", alias_path)
    else:
        logger.warning("No validation CSVs found — run backtests first")

    print(f"\n[{RESEARCH_ONLY_GUARD}] HTML reports complete.")
    print(f"  Reports dir: {REPORTS_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate HTML validation reports")
    args = parser.parse_args()
    main(args)
