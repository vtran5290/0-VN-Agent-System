"""Run market context / breadth gate backtests for cloud daily report validation.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

RESEARCH_ONLY_GUARD = "RESEARCH_ONLY_NOT_PRODUCTION"
print(f"[{RESEARCH_ONLY_GUARD}] Starting market context backtests...")

from src.research.cloud_daily_report_validation.breadth_tests import run_t1_t2_gate_validation_full
from src.research.cloud_daily_report_validation.schema import OUTPUT_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Running T1/T2 gate validation...")
    result = run_t1_t2_gate_validation_full()
    blocked = (result["evidence_label"] == "BLOCKED_BY_DATA").sum() if "evidence_label" in result.columns else 0
    print(f"\n[{RESEARCH_ONLY_GUARD}] Market context backtests complete.")
    print(f"  T1/T2 gate: {len(result)} rows, {blocked} BLOCKED_BY_DATA")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run market context backtests")
    args = parser.parse_args()
    main(args)
