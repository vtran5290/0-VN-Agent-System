"""Handler: data-health subcommand."""
from __future__ import annotations

import argparse
from pathlib import Path


def register(sub) -> None:
    p = sub.add_parser("data-health", help="Run data health check")
    p.add_argument("--asof", required=True)
    p.add_argument("--scan-path", type=Path, default=None)
    p.set_defaults(func=handle)


def handle(args: argparse.Namespace, **_) -> int:
    from src.trading.config import load_live_trading_config
    from src.trading.live.data_health import run_data_health, save_data_health
    from src.trading.live.scan_resolver import resolve_scan

    asof = args.asof
    lcfg = load_live_trading_config(data_root_override=getattr(args, "data_root", None))
    scan = resolve_scan(lcfg, asof, cli_scan_path=getattr(args, "scan_path", None))
    print(f"Scan: {scan.path} source={scan.resolved_scan_source} sample={scan.is_sample}")
    r = run_data_health(lcfg, asof)
    save_data_health(lcfg, r)
    print(f"Data health: {r.status} block={r.block_order_generation}")
    return 0
