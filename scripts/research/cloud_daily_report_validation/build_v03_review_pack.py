"""Build v0.3 archive + label patch review pack zip.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

RESEARCH_ONLY_GUARD = "RESEARCH_ONLY_NOT_PRODUCTION"
print(f"[{RESEARCH_ONLY_GUARD}] Building v0.3 review pack...")

from src.research.cloud_daily_report_validation.review_pack import build_v03_review_pack
from src.research.cloud_daily_report_validation.schema import REVIEW_PACKAGES_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    date_str = args.date or str(date.today()).replace("-", "")
    logger.info("Building v0.3 review pack (date: %s)...", date_str)
    zip_path = build_v03_review_pack(date_str=date_str)
    print(f"\n[{RESEARCH_ONLY_GUARD}] v0.3 review pack complete.")
    print(f"  Path: {zip_path}")
    print(f"  Size: {zip_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build v0.3 archive+label review pack")
    parser.add_argument("--date", type=str, default=None, help="YYYYMMDD for archive manifest slice")
    args = parser.parse_args()
    main(args)
