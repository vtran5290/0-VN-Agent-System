"""Handler: manual-review subcommand."""
from __future__ import annotations

import argparse


def register(sub) -> None:
    p = sub.add_parser("manual-review", help="Show manual review queue for date")
    p.add_argument("--date", required=True)
    p.add_argument("--account", default=None)
    p.set_defaults(func=handle)


def handle(args: argparse.Namespace, **_) -> int:
    from src.trading.live.manual_review import pending_summary
    from src.trading.live.paper_accounts import build_live_config_for_account, get_default_account_id

    aid = getattr(args, "account", None) or get_default_account_id()
    lcfg, _ = build_live_config_for_account(aid, data_root_override=getattr(args, "data_root", None))
    summary = pending_summary(lcfg, args.date)
    print(summary)
    return 0
