"""Handler: apply-manual-review subcommand."""
from __future__ import annotations

import argparse


def register(sub) -> None:
    p = sub.add_parser("apply-manual-review", help="Merge manual review queue into intents")
    p.add_argument("--date", required=True)
    p.add_argument("--account", default=None)
    p.set_defaults(func=handle)


def handle(args: argparse.Namespace, **_) -> int:
    from src.trading.live.manual_review import apply_queue_to_intents, load_queue
    from src.trading.live.order_intent import load_order_intents, save_order_intents
    from src.trading.live.paper_accounts import build_live_config_for_account, get_default_account_id

    aid = getattr(args, "account", None) or get_default_account_id()
    lcfg, _ = build_live_config_for_account(aid, data_root_override=getattr(args, "data_root", None))
    intents = load_order_intents(lcfg, args.date)
    merged = apply_queue_to_intents(lcfg, args.date, intents)
    save_order_intents(lcfg, args.date, merged)
    print(f"Applied manual review queue ({len(load_queue(lcfg, args.date))} rows)")
    return 0
