"""Handler: generate-order-intent subcommand."""
from __future__ import annotations

import argparse
from pathlib import Path


def register(sub) -> None:
    p = sub.add_parser(
        "generate-order-intent",
        help="Order-intent dry run CSV only — no broker orders, no OMS execution",
    )
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--scan-path", type=Path, required=True)
    p.add_argument("--positions-path", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--allow-test-sample",
        action="store_true",
        help="Allow fixture/placeholder scan dates (tests only)",
    )
    p.add_argument(
        "--max-stale-days",
        type=int,
        default=7,
        help="Max days between requested and effective scan date",
    )
    p.set_defaults(func=handle)


def handle(args: argparse.Namespace, **_) -> int:
    import pandas as pd
    from src.trading.order_intent_dry_run import OrderIntentDryRunError, generate_order_intent_dry_run

    try:
        path, meta = generate_order_intent_dry_run(
            args.date,
            args.scan_path,
            args.positions_path,
            args.output,
            allow_test_sample=getattr(args, "allow_test_sample", False),
            max_stale_days=getattr(args, "max_stale_days", 7),
        )
        print(f"Wrote order-intent dry run: {path}")
        print(
            f"requested_date={meta['requested_date']} "
            f"effective_scan_date={meta['effective_scan_date']}"
        )
        print("This command does not send broker orders")
        df = pd.read_csv(path)
        flagged = (df["risk_flag"].astype(str).str.strip() != "").sum()
        if meta.get("fail_closed_any") or flagged:
            return 2
        return 0
    except OrderIntentDryRunError as e:
        print(f"FAIL-CLOSED: {e}")
        return 1
