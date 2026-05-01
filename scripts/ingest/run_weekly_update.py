"""
Run weekly update: optionally run existing report, then normalize to schema v1.0.
Output: data/processed/weekly_report.json
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from scripts.ingest.config import DATA_PROCESSED, DECISION_WEEKLY_JSON, LOGS_DIR, REPO
from scripts.ingest.normalize_weekly_report import normalize_weekly_report
from scripts.utils.io import write_json
from scripts.utils.logging_utils import setup_logging
from scripts.utils.validation import validate_weekly_report_payload


def run_existing_weekly() -> bool:
    """Run python -m src.report.weekly --render to refresh data/decision/weekly_report.json."""
    try:
        subprocess.run(
            [sys.executable, "-m", "src.report.weekly", "--render"],
            cwd=REPO,
            check=True,
            capture_output=True,
            timeout=120,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Weekly report ingestion: refresh + normalize")
    ap.add_argument("--skip-weekly", action="store_true", help="Skip running src.report.weekly; only normalize from existing JSON")
    ap.add_argument("--no-validate", action="store_true", help="Skip schema validation after normalize")
    args = ap.parse_args()
    log = setup_logging(LOGS_DIR)
    log.info("Weekly update started")
    if not args.skip_weekly:
        log.info("Running existing weekly report (src.report.weekly)...")
        if run_existing_weekly():
            log.info("Weekly report refreshed")
        else:
            log.warning("Weekly report run failed or skipped; normalizing from existing file if present")
    else:
        log.info("Skipping weekly report (--skip-weekly)")
    payload = normalize_weekly_report(DECISION_WEEKLY_JSON)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "weekly_report.json"
    write_json(out_path, payload)
    log.info("Wrote %s", out_path)
    if not args.no_validate:
        ok, errs = validate_weekly_report_payload(payload)
        if not ok:
            for e in errs:
                log.warning("Validation: %s", e)
        else:
            log.info("Validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
