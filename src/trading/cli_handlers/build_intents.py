"""Handler: build-intents subcommand."""
from __future__ import annotations

import argparse
from pathlib import Path


def register(sub) -> None:
    p = sub.add_parser(
        "build-intents",
        help="Build order intents from scan (production-safe default)",
    )
    p.add_argument("--asof", required=True)
    p.add_argument("--scan-path", type=Path, default=None)
    p.add_argument("--allow-sample", action="store_true", help="Allow sample scan CSV")
    p.add_argument("--test-mode", action="store_true", help="Relax stale-scan block for fixtures")
    p.set_defaults(func=handle)


def handle(args: argparse.Namespace, **_) -> int:
    from src.trading.config import load_live_trading_config
    from src.trading.live.data_health import load_data_health_status, run_data_health, save_data_health
    from src.trading.live.order_intent import build_order_intents, save_order_intents
    from src.trading.live.paper_ledger import PaperLedger
    from src.trading.live.scan_resolver import resolve_scan

    asof = args.asof
    lcfg = load_live_trading_config(data_root_override=getattr(args, "data_root", None))
    if getattr(args, "allow_sample", False):
        lcfg.allow_sample_scan = True
    test_mode = bool(getattr(args, "test_mode", False))
    scan = resolve_scan(
        lcfg, asof,
        cli_scan_path=getattr(args, "scan_path", None),
        test_mode=test_mode,
    )
    if scan.blocked:
        print(f"Scan blocked: {scan.errors}")
        return 1
    print(
        f"Scan: {scan.path} source={scan.resolved_scan_source} hash={scan.scan_hash} "
        f"sample={scan.is_sample} stale={scan.is_stale}"
    )
    hs = load_data_health_status(lcfg)
    if hs.get("status") == "UNKNOWN":
        r = run_data_health(lcfg, asof)
        save_data_health(lcfg, r)
        hs = r.to_status_dict()
    intents = build_order_intents(
        lcfg,
        asof,
        hs,
        scan_path=scan.path,
        scan_resolve=scan,
        ledger=PaperLedger(lcfg),
        latest_panel_date=hs.get("latest_panel_date", ""),
        test_mode=test_mode,
    )
    p = save_order_intents(lcfg, asof, intents)
    print(f"Wrote {len(intents)} intents to {p}")
    return 0
