"""Handler: resolve-scan subcommand."""
from __future__ import annotations

import argparse
from pathlib import Path


def register(sub) -> None:
    p = sub.add_parser("resolve-scan", help="Resolve Phase36 scan path for date")
    p.add_argument("--date", required=True)
    p.add_argument("--scan-path", type=Path, default=None)
    p.add_argument("--allow-sample", action="store_true")
    p.add_argument("--use-latest-scan-date", action="store_true")
    p.set_defaults(func=handle)


def handle(args: argparse.Namespace, **_) -> int:
    from src.trading.config import load_live_trading_config
    from src.trading.live.scan_resolver import resolve_scan

    lcfg = load_live_trading_config(data_root_override=getattr(args, "data_root", None))
    r = resolve_scan(
        lcfg,
        args.date,
        cli_scan_path=getattr(args, "scan_path", None),
        allow_sample=True if getattr(args, "allow_sample", False) else None,
        use_latest_scan_date=getattr(args, "use_latest_scan_date", False),
    )
    for w in r.warnings:
        print(f"warn={w}")
    for e in r.errors:
        print(f"error={e}")
    print(
        f"path={r.path} source={r.resolved_scan_source} hash={r.scan_hash} "
        f"sample={r.is_sample} stale={r.is_stale} blocked={r.blocked} "
        f"scan_date={r.scan_date} requested_date={r.requested_date} "
        f"effective_date={r.effective_date}"
    )
    return 0 if not r.blocked else 1
