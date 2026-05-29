"""Script: Archive daily Cloud Daily Report inputs into dated snapshots.

Usage:
  .venv\Scripts\python.exe scripts/research/cloud_daily_report_validation/archive_daily_inputs.py
  .venv\Scripts\python.exe scripts/research/cloud_daily_report_validation/archive_daily_inputs.py --date 20260529
  .venv\Scripts\python.exe scripts/research/cloud_daily_report_validation/archive_daily_inputs.py --dry-run

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.research.cloud_daily_report_validation.archive_daily_inputs import run_archive

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Archive daily Cloud Daily Report inputs.")
    p.add_argument(
        "--date",
        metavar="YYYYMMDD",
        help="Date to archive under (default: today)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be archived without writing files",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    archive_date: date | None = None
    if args.date:
        try:
            archive_date = date(int(args.date[:4]), int(args.date[4:6]), int(args.date[6:8]))
        except (ValueError, IndexError):
            print(f"ERROR: Invalid date format '{args.date}' — expected YYYYMMDD")
            sys.exit(1)

    df, date_mp, cum_mp = run_archive(archive_date=archive_date, dry_run=args.dry_run)

    print("\nArchive manifest:")
    for _, row in df.iterrows():
        status = "OK " if row["exists"] else "---"
        note = row["notes"]
        print(f"  [{status}] {row['file_type']:35s}  {note}")

    if not args.dry_run:
        print(f"\nDate manifest:       {date_mp}")
        print(f"Cumulative manifest: {cum_mp}")
        print(
            f"\nSummary: {(df['notes'] == 'archived').sum()} archived, "
            f"{(df['notes'] == 'already_archived_identical').sum()} identical (skipped), "
            f"{(~df['exists']).sum()} source missing"
        )
    else:
        print("\nDry run — no files written.")


if __name__ == "__main__":
    main()
