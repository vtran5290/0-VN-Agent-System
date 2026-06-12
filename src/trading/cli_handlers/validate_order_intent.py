"""Handler: validate-order-intent subcommand."""
from __future__ import annotations

import argparse
from pathlib import Path


def register(sub) -> None:
    p = sub.add_parser(
        "validate-order-intent",
        help="Validate order-intent CSV (placeholder dates, order_sent=NO)",
    )
    p.add_argument("--path", type=Path, required=True)
    p.add_argument(
        "--allow-test-sample",
        action="store_true",
        help="Allow placeholder dates only when filename contains test or sample",
    )
    p.set_defaults(func=handle)


def handle(args: argparse.Namespace, **_) -> int:
    from src.trading.order_intent_dry_run import OrderIntentDryRunError, validate_order_intent_csv

    try:
        validate_order_intent_csv(
            args.path,
            allow_test_sample=getattr(args, "allow_test_sample", False),
        )
        print(f"OK: {args.path}")
        return 0
    except OrderIntentDryRunError as e:
        print(f"FAIL-CLOSED: {e}")
        return 1
