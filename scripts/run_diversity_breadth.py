#!/usr/bin/env python3
"""Standalone runner for diversity-weighted breadth Gate B research.

Usage:
    python scripts/run_diversity_breadth.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.diversity_breadth import run_build
from src.research.diversity_breadth_test import run_gate_b_tests, write_gate_b_outputs

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run diversity breadth Gate B research pipeline")
    parser.add_argument(
        "--panel",
        type=Path,
        default=None,
        help="OHLCV panel parquet (default: data/research/ema_cloud/ohlcv_panel_ext2012.parquet)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "research" / "diversity_breadth",
        help="Output directory",
    )
    args = parser.parse_args()

    logger.info("Building diversity-weighted portfolio returns...")
    diversity = run_build(panel_path=args.panel, out_dir=args.out_dir)

    print("\n--- Diversity series (head) ---")
    print(diversity.head(3).to_string())
    print("\n--- Diversity series (tail) ---")
    print(diversity.tail(3).to_string())
    print(f"\nDate range: {diversity['date'].min()} -> {diversity['date'].max()}")
    spread_na = diversity["spread_p050_vs_p100"].isna().sum()
    print(f"spread_p050_vs_p100 NaN count: {spread_na} / {len(diversity)}")

    logger.info("Running Gate B tests...")
    results = run_gate_b_tests(diversity)
    json_path, md_path = write_gate_b_outputs(results, out_dir=args.out_dir)

    gv = results["gate_verdict"]
    t1 = results["test1_correlation"]
    t2 = results["test2_hit_rate"]
    t3 = results["test3_rolling_stability"]

    print("\n--- Gate B results ---")
    print(json.dumps(results, indent=2, default=str))
    print(f"\nWrote: {json_path}")
    print(f"Wrote: {md_path}")

    print("\n" + "=" * 60)
    print(f"GATE B VERDICT: {gv['verdict']}")
    print(f"  r = {t1.get('r')} (threshold > {gv['criteria']['r_threshold']})")
    print(f"  hit_rate = {t2.get('hit_rate')} (threshold > {gv['criteria']['hit_rate_threshold']})")
    print(
        f"  rolling pct r>{gv['criteria']['r_threshold']} = "
        f"{t3.get('pct_windows_r_above_threshold')} "
        f"(threshold > {gv['criteria']['rolling_pct_threshold']})"
    )
    print(f"  signal OK: {gv['signal_criterion_met']} | stability OK: {gv['stability_criterion_met']}")
    print("=" * 60)

    return 0 if gv["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
