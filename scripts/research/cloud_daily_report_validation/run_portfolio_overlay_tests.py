"""Run portfolio overlay tests for cloud daily report validation.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

RESEARCH_ONLY_GUARD = "RESEARCH_ONLY_NOT_PRODUCTION"
print(f"[{RESEARCH_ONLY_GUARD}] Starting portfolio overlay tests...")

from src.research.cloud_daily_report_validation.portfolio_overlay_tests import run_portfolio_overlay_validation_full
from src.research.cloud_daily_report_validation.schema import OUTPUT_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Running portfolio overlay validation...")
    result = run_portfolio_overlay_validation_full()

    print(f"\n[{RESEARCH_ONLY_GUARD}] Portfolio overlay tests complete.")
    print(f"  Results: {len(result)} rows (all BLOCKED_BY_DATA — no historical positions)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run portfolio overlay tests")
    args = parser.parse_args()
    main(args)
