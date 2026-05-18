"""Read-only roadmap / stage-gate status printer."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
DEFAULT_TRACKER = REPO / "data" / "roadmap" / "stage_tracker.yaml"

RISKY_FLAGS = (
    "live_trading_enabled",
    "copytrade_enabled",
    "content_auto_posting_enabled",
    "intraday_order_routing_enabled",
    "s3_production_enabled",
)


def load_tracker(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_TRACKER
    if not p.exists():
        raise FileNotFoundError(f"Stage tracker not found: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def print_roadmap_status(tracker: dict[str, Any]) -> int:
    """Print status; return 1 if any risky flag is true."""
    status = tracker.get("status") or {}
    evidence = tracker.get("evidence") or {}
    last_reviews = tracker.get("last_reviews") or {}
    blockers = tracker.get("blockers") or []

    print("=== Roadmap Status ===")
    print(f"as_of: {tracker.get('as_of', 'unknown')}")
    print(
        f"current_stage: {tracker.get('current_stage')} — "
        f"{tracker.get('current_stage_name', '')}"
    )
    print(
        f"next_stage: {tracker.get('next_stage')} — "
        f"{tracker.get('next_stage_name', '')}"
    )
    print(f"next_action: {tracker.get('next_action', '')}")
    print()
    print("--- Evidence ---")
    for k, v in evidence.items():
        print(f"  {k}: {v}")
    print()
    if last_reviews:
        print("--- Last reviews ---")
        for k, v in last_reviews.items():
            print(f"  {k}: {v}")
        print()
    print("--- Blockers ---")
    for b in blockers:
        print(f"  - {b}")
    print()
    print("--- Safety flags ---")
    risky_on = []
    for flag in RISKY_FLAGS:
        val = bool(status.get(flag, False))
        print(f"  {flag}: {val}")
        if val:
            risky_on.append(flag)
    if risky_on:
        print()
        print(f"WARNING: risky flags enabled: {', '.join(risky_on)}")
        return 1
    print()
    print("Real capital: NO-GO (by policy)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print roadmap stage status (read-only)")
    parser.add_argument(
        "--tracker",
        type=Path,
        default=DEFAULT_TRACKER,
        help="Path to stage_tracker.yaml",
    )
    args = parser.parse_args(argv)
    try:
        tracker = load_tracker(args.tracker)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    return print_roadmap_status(tracker)


if __name__ == "__main__":
    raise SystemExit(main())
