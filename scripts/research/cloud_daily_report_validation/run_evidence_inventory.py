"""Run evidence inventory and output inventory for cloud daily report validation.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

RESEARCH_ONLY_GUARD = "RESEARCH_ONLY_NOT_PRODUCTION"
print(f"[{RESEARCH_ONLY_GUARD}] Starting evidence inventory...")

from src.research.cloud_daily_report_validation.evidence_inventory import (
    build_evidence_registry,
    search_existing_evidence,
)
from src.research.cloud_daily_report_validation.output_inventory import build_output_inventory
from src.research.cloud_daily_report_validation.reporting import generate_evidence_inventory_html
from src.research.cloud_daily_report_validation.schema import OUTPUT_DIR, REPORTS_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Search existing evidence
    logger.info("Searching existing evidence paths...")
    existing = search_existing_evidence()
    for key, info in existing.items():
        status = "EXISTS" if info["exists"] else "MISSING"
        logger.info("  [%s] %s — %s", status, key, info["path"])

    # Build evidence registry
    logger.info("Building evidence registry...")
    registry_df = build_evidence_registry()
    registry_out = OUTPUT_DIR / "evidence_inventory.csv"
    registry_df.to_csv(registry_out, index=False)
    logger.info("Evidence registry written: %s (%d rows)", registry_out, len(registry_df))

    # Build output inventory
    logger.info("Building output inventory...")
    inventory_df = build_output_inventory()
    inventory_out = OUTPUT_DIR / "output_inventory.csv"
    inventory_df.to_csv(inventory_out, index=False)
    logger.info("Output inventory written: %s (%d rows)", inventory_out, len(inventory_df))

    # Generate HTML report
    logger.info("Generating evidence inventory HTML...")
    html = generate_evidence_inventory_html(registry_df, inventory_df)
    html_out = REPORTS_DIR / "evidence_inventory.html"
    html_out.write_text(html, encoding="utf-8")
    logger.info("HTML report written: %s", html_out)

    print(f"\n[{RESEARCH_ONLY_GUARD}] Evidence inventory complete.")
    print(f"  Registry: {registry_out} ({len(registry_df)} rows)")
    print(f"  Inventory: {inventory_out} ({len(inventory_df)} rows)")
    print(f"  HTML: {html_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run cloud daily report evidence inventory")
    args = parser.parse_args()
    main(args)
