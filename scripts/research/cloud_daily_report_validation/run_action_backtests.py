"""Run A3 final action backtests for cloud daily report validation.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

RESEARCH_ONLY_GUARD = "RESEARCH_ONLY_NOT_PRODUCTION"
print(f"[{RESEARCH_ONLY_GUARD}] Starting action backtests...")

from src.research.cloud_daily_report_validation.action_tests import run_action_validation_full
from src.research.cloud_daily_report_validation.data_loader import get_scan_date_range, load_scan_files
from src.research.cloud_daily_report_validation.schema import OUTPUT_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Report scan date range
    scan_df = load_scan_files()
    min_date, max_date = get_scan_date_range(scan_df)
    logger.info("Scan data range: %s to %s (%d rows)", min_date, max_date, len(scan_df))

    if scan_df.empty:
        logger.warning("No scan data found — all tests will be BLOCKED_BY_DATA")
    else:
        counts = scan_df["final_action"].value_counts() if "final_action" in scan_df.columns else None
        if counts is not None:
            logger.info("final_action distribution:\n%s", counts.to_string())

    logger.info("Running action validation...")
    result = run_action_validation_full()

    blocked = (result["evidence_label"] == "BLOCKED_BY_DATA").sum() if "evidence_label" in result.columns else 0
    total = len(result)
    print(f"\n[{RESEARCH_ONLY_GUARD}] Action backtests complete.")
    print(f"  Results: {total} rows, {blocked} BLOCKED_BY_DATA")
    print(f"  Output: {OUTPUT_DIR / 'final_action_validation.csv'}")
    print(f"  Note: Expected to be mostly BLOCKED_BY_DATA with ~2wk scan history")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run A3 final action backtests")
    args = parser.parse_args()
    main(args)
