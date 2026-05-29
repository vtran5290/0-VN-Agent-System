"""Run output inventory for cloud daily report validation.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

RESEARCH_ONLY_GUARD = "RESEARCH_ONLY_NOT_PRODUCTION"
print(f"[{RESEARCH_ONLY_GUARD}] Starting output inventory...")

from src.research.cloud_daily_report_validation.output_inventory import build_output_inventory
from src.research.cloud_daily_report_validation.schema import OUTPUT_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Building output inventory...")
    df = build_output_inventory()
    out_path = OUTPUT_DIR / "output_inventory.csv"
    df.to_csv(out_path, index=False)
    logger.info("Output inventory written: %s (%d rows)", out_path, len(df))

    # Print section summary
    if "section" in df.columns and "output_type" in df.columns:
        summary = df.groupby(["section", "output_type"]).size().reset_index(name="count")
        print("\nOutput inventory summary:")
        print(summary.to_string(index=False))

    print(f"\n[{RESEARCH_ONLY_GUARD}] Output inventory complete: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run cloud daily report output inventory")
    args = parser.parse_args()
    main(args)
