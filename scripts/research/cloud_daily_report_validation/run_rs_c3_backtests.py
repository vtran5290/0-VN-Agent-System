"""Run RS correction and C3 backtests for cloud daily report validation.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

RESEARCH_ONLY_GUARD = "RESEARCH_ONLY_NOT_PRODUCTION"
print(f"[{RESEARCH_ONLY_GUARD}] Starting RS/C3 backtests...")

from src.research.cloud_daily_report_validation.c3_tests import run_c3_validation_full
from src.research.cloud_daily_report_validation.rs_tests import run_rs_correction_validation_full
from src.research.cloud_daily_report_validation.schema import OUTPUT_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Running RS correction validation...")
    rs_result = run_rs_correction_validation_full()
    logger.info("Running C3 validation...")
    c3_result = run_c3_validation_full()

    print(f"\n[{RESEARCH_ONLY_GUARD}] RS/C3 backtests complete.")
    print(f"  RS correction: {len(rs_result)} rows")
    print(f"  C3 validation: {len(c3_result)} rows (all CONTEXT_ONLY/DISPLAY_ONLY)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RS/C3 backtests")
    args = parser.parse_args()
    main(args)
