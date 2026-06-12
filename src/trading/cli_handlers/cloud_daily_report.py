"""Handler: cloud-daily-report subcommand."""
from __future__ import annotations

import argparse
from pathlib import Path


def register(sub) -> None:
    p = sub.add_parser(
        "cloud-daily-report",
        help="Build smart daily cloud setup report (EOD / intraday preview)",
    )
    p.add_argument(
        "--mode",
        choices=["eod", "pre-lunch", "pre-atc", "auto"],
        default="auto",
        help="Report mode (default: auto-detect)",
    )
    p.add_argument("--scan-path", type=Path, default=None, help="Override EOD scan CSV path")
    p.set_defaults(func=handle)


def handle(args: argparse.Namespace, **_) -> int:
    from src.trading.reports.cloud_daily_report import write_report

    result = write_report(args.mode, scan_path=getattr(args, "scan_path", None))
    print(f"Cloud daily report: mode={result['mode']} status={result['report_status']}")
    print(f"  HTML: {result.get('html_latest')}")
    print(f"  MD:   {result.get('md_latest')}")
    print(f"  JSON: {result.get('json_path')}")
    for w in result.get("warnings") or []:
        print(f"  WARN: {w}")
    return 0 if result["report_status"] != "NEEDS_REVIEW" else 1
