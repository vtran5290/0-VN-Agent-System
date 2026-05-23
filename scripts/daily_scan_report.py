"""Backward-compatible CLI entry — canonical module: scripts.reporting.daily_scan_report."""
from __future__ import annotations

from scripts.reporting.daily_scan_report import main, write_daily_scan_report

if __name__ == "__main__":
    raise SystemExit(main())
