"""Handler: intraday-scan subcommand."""
from __future__ import annotations

import argparse
from pathlib import Path


def register(sub) -> None:
    p = sub.add_parser(
        "intraday-scan",
        help="Intraday A3/S3 preview scan (manual review only — no OMS routing)",
    )
    p.add_argument("--mode", choices=["pre-lunch", "pre-atc", "ad-hoc"], default="ad-hoc")
    p.add_argument("--symbols", default="", help="Comma-separated tickers (default: watchlist)")
    p.add_argument(
        "--volume-projection",
        default=None,
        choices=["session_time", "historical_curve", "no_projection"],
    )
    p.set_defaults(func=handle)


def handle(args: argparse.Namespace, **_) -> int:
    from src.trading.intraday.intraday_scan import run_intraday_scan

    syms = [s.strip() for s in (args.symbols or "").split(",") if s.strip()] or None
    df, meta = run_intraday_scan(
        symbols=syms,
        mode=args.mode,
        volume_projection=getattr(args, "volume_projection", None),
    )
    print(
        f"Intraday preview: status={meta.get('status')} rows={len(df)} "
        f"mode={args.mode} capability={meta.get('capability', {}).get('available')}"
    )
    ok_status = meta.get("status") in ("OK", "VNINDEX_ONLY_MACRO")
    return 0 if ok_status or len(df) > 0 else 1
