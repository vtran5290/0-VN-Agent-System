"""Handler: distribution-risk subcommand."""
from __future__ import annotations

import argparse


def register(sub) -> None:
    p = sub.add_parser(
        "distribution-risk",
        help="Build VNINDEX Distribution Risk Lens research outputs (context only)",
    )
    p.add_argument("--start", default="2012-01-01")
    p.add_argument("--as-of", default="latest", help="YYYY-MM-DD or latest")
    p.set_defaults(func=handle)


def handle(args: argparse.Namespace, **_) -> int:
    from src.market.distribution_risk_lens.pipeline import run_distribution_risk_lens

    as_of = None if getattr(args, "as_of", "latest") == "latest" else args.as_of
    result = run_distribution_risk_lens(start=getattr(args, "start", "2012-01-01"), as_of=as_of)
    print(f"Distribution risk lens: rows={result['n_features']} -> {result['outputs_dir']}")
    print(f"  JSON: {result['outputs_dir']}/distribution_risk_latest.json")
    artifacts = result.get("artifacts") or {}
    if artifacts.get("html"):
        print(f"  HTML: {artifacts['html']}")
    if artifacts.get("md"):
        print(f"  MD:   {artifacts['md']}")
    for w in result.get("warnings") or []:
        print(f"  WARN: {w}")
    return 0
