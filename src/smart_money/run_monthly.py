from __future__ import annotations

import argparse
from typing import Optional

from .consensus import build_monthly_payload
from .io import (
    EXTRACTED_DIR,
    load_funds_for_month,
    load_monthly_consensus,
    write_monthly_consensus,
)


def build_and_save_monthly(month: str, prev_month: Optional[str] = None) -> str:
    """
    High-level helper:
    - Load all per-fund JSONs for `month`.
    - Optionally load previous-month per-fund JSONs (if prev_month provided).
    - Build consensus payload.
    - Write to data/smart_money/monthly/smart_money_<month>.json.
    Returns the path as a string.
    """
    funds = load_funds_for_month(month)
    prev_funds = load_funds_for_month(prev_month) if prev_month else None

    payload = build_monthly_payload(month=month, funds=funds, prev_month_funds=prev_funds)
    out_path = write_monthly_consensus(month, payload)
    return str(out_path)


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(description="Build Smart Money monthly consensus JSON.")
    parser.add_argument("--month", required=True, help="Target month in YYYY-MM format.")
    parser.add_argument(
        "--prev-month",
        help="Optional previous month (YYYY-MM) for deltas; if omitted, deltas.vs_prev_month will have nulls.",
    )
    args = parser.parse_args(argv)

    if not EXTRACTED_DIR.exists():
        print(f"EXTRACTED_DIR does not exist: {EXTRACTED_DIR}")
        return

    prev_month = args.prev_month
    # If prev_month is not explicitly provided, we do not infer here; keep it explicit.
    path_str = build_and_save_monthly(args.month, prev_month)
    print(f"Wrote Smart Money monthly consensus: {path_str}")


if __name__ == "__main__":
    main()

