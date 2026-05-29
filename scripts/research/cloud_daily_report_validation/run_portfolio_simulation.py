"""Run portfolio simulation for cloud daily report validation.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

RESEARCH_ONLY_GUARD = "RESEARCH_ONLY_NOT_PRODUCTION"
print(f"[{RESEARCH_ONLY_GUARD}] Starting portfolio simulation...")

from src.research.cloud_daily_report_validation.portfolio_simulation import run_portfolio_simulation_full
from src.research.cloud_daily_report_validation.schema import OUTPUT_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Running portfolio simulation...")
    result = run_portfolio_simulation_full()

    status = result["status"].iloc[0] if "status" in result.columns and len(result) > 0 else "unknown"
    print(f"\n[{RESEARCH_ONLY_GUARD}] Portfolio simulation complete.")
    print(f"  Status: {status}")
    print("  Note: Expected BLOCKED_BY_DATA — need 30+ trading days of scan history")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run portfolio simulation")
    args = parser.parse_args()
    main(args)
