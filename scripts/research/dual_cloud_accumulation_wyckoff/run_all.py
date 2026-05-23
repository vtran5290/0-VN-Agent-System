#!/usr/bin/env python3
"""Run all stages of the Dual Cloud Accumulation / Wyckoff research pipeline.

Stages:
  1  feature_value    — predictive value of accumulation/tightness features on A3
  2  a3_ranking       — candidate ranking: top-score vs all-signal baseline
  3  a3_t2_timing     — T2 add-on timing (≥4% pullback within 30 bars)
  4  s3_quality       — S3 max60 shadow quality filter
  5  wyckoff_tags     — incremental value of Wyckoff tags vs tightness
  6  robustness       — by-year / regime / liquidity robustness checks
  7  score_recalib    — score recalibration / feature ablation
  8  observation      — observation layer / forward validation ledger
  12  s3_shadow        — S3 paper-shadow contract validation
  13        sleeve        — Stage 13: Combined A3/S3 Sleeve Portfolio Simulation
  14        closure       — Stage 14: Research Closure, Coverage Audit, Monthly Runbook
  12b / 15  s3_maxhold    — Stage 12B: S3 MaxHold robustness patch (alias: 15)

Usage:
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py --ex-vin --workers 8
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py --stage 1 3    # run only stages 1 and 3
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py --stage 12b   # Stage 12B alias (= 15)
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py --stage 13    # Stage 13 — Sleeve sim
    .venv\\Scripts\\python.exe scripts/research/dual_cloud_accumulation_wyckoff/run_all.py --stage 14    # Stage 14 — Research closure
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _stage_1(ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage1_feature_value import run
    run(ex_vin=ex_vin, workers=workers)


def _stage_2(ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage2_a3_ranking import run
    run(ex_vin=ex_vin, workers=workers)


def _stage_3(ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage3_a3_t2_timing import run
    run(ex_vin=ex_vin, workers=workers)


def _stage_4(ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage4_s3_quality import run
    run(ex_vin=ex_vin, workers=workers)


def _stage_5(ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage5_wyckoff_tags import run
    run(ex_vin=ex_vin, workers=workers)


def _stage_6(_ex_vin: bool, _workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage6_robustness import run
    run()  # uses default horizon=63; override via stage6 CLI directly


def _stage_7(_ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage7_score_recalibration import run
    run(workers=workers)


def _stage_8(_ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage8_observation_layer import run
    run(workers=workers)


def _stage_9(_ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage9_forward_validation_update import run
    run(workers=workers)


def _stage_10(_ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage10_monthly_validation_report import run
    run(workers=workers)


def _stage_11(_ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage11_timing_pattern_decomposition import run
    run(workers=workers)


def _stage_12(_ex_vin: bool, workers: int) -> None:
    from scripts.research.dual_cloud_accumulation_wyckoff.stage12_s3_shadow_contract_validation import run
    run(workers=workers)


def _stage_13(_ex_vin: bool, workers: int) -> None:
    """Stage 13 — Combined A3/S3 Sleeve Portfolio Simulation."""
    from scripts.research.dual_cloud_accumulation_wyckoff.stage13_combined_sleeve_simulation import run
    run(workers=workers)


def _stage_14(_ex_vin: bool, workers: int) -> None:
    """Stage 14 — Research Closure, Coverage Audit, and Monthly Runbook."""
    from scripts.research.dual_cloud_accumulation_wyckoff.stage14_research_closure import run
    run(workers=workers)


def _stage_15(_ex_vin: bool, workers: int) -> None:
    """Stage 12B — S3 MaxHold Robustness Patch (integer alias: 15)."""
    from scripts.research.dual_cloud_accumulation_wyckoff.stage12b_s3_maxhold_robustness import run
    run(workers=workers)


# String aliases accepted on the CLI (mapped to integer stage numbers)
# NOTE: "12b" maps to 15 (Stage 12B was displaced by Stage 14 Research Closure)
_STAGE_ALIASES: dict[str, int] = {
    "12b": 15,
    "12B": 15,
}


STAGE_MAP = {
    1: ("Stage 1 — Feature Predictive Value",         _stage_1),
    2: ("Stage 2 — A3 Candidate Ranking",             _stage_2),
    3: ("Stage 3 — A3 T2 Timing",                    _stage_3),
    4: ("Stage 4 — S3 Shadow Quality",                _stage_4),
    5: ("Stage 5 — Wyckoff Tags",                    _stage_5),
    6: ("Stage 6 — Robustness Checks",                _stage_6),
    7: ("Stage 7 — Score Recalibration",              _stage_7),
    8: ("Stage 8 — Observation Layer",                _stage_8),
    9: ("Stage 9 — Forward Validation Update",        _stage_9),
   10: ("Stage 10 — Monthly Validation Report",       _stage_10),
   11: ("Stage 11 — Timing & Pattern Decomp",         _stage_11),
   12: ("Stage 12 — S3 Shadow Contract",              _stage_12),
   13: ("Stage 13 — Combined A3/S3 Sleeve Sim",       _stage_13),
   14: ("Stage 14 — Research Closure & Runbook",      _stage_14),
   15: ("Stage 12B — S3 MaxHold Robustness",          _stage_15),
}


def _parse_stage(value: str) -> int:
    """Accept integer stage numbers OR string aliases like '12b'."""
    if value in _STAGE_ALIASES:
        return _STAGE_ALIASES[value]
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Stage must be an integer or a known alias (e.g. '12b'). Got: {value!r}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run all (or selected) stages of the accumulation/Wyckoff research."
    )
    parser.add_argument(
        "--stage", nargs="+", type=_parse_stage,
        help="Stage numbers to run (integers or aliases like '12b'). Default: all.",
    )
    parser.add_argument("--ex-vin", action="store_true", default=True,
                        help="Exclude VIC, VHM, VRE (default: True)")
    parser.add_argument("--full-universe", action="store_true",
                        help="Include full universe (overrides --ex-vin)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel workers for per-symbol processing")
    args = parser.parse_args()

    ex_vin  = not args.full_universe
    workers = args.workers
    stages  = args.stage if args.stage else sorted(STAGE_MAP.keys())

    universe_label = "ex-VIN" if ex_vin else "full universe"
    log.info(
        "=== Dual Cloud Accumulation / Wyckoff Research ===\n"
        "Universe: %s | Workers: %d | Stages: %s",
        universe_label, workers, stages,
    )

    total_t0 = time.time()
    failed: list[int] = []
    for stage_num in stages:
        if stage_num not in STAGE_MAP:
            log.warning("Unknown stage %d — skipping.", stage_num)
            continue

        label, fn = STAGE_MAP[stage_num]
        log.info("── Starting %s ──", label)
        t0 = time.time()
        try:
            fn(ex_vin, workers)
            elapsed = time.time() - t0
            log.info("── %s done in %.1fs ──", label, elapsed)
        except Exception as exc:
            elapsed = time.time() - t0
            log.error("Stage %d failed in %.1fs: %s", stage_num, elapsed, exc, exc_info=True)
            failed.append(stage_num)

    total_elapsed = time.time() - total_t0
    if failed:
        log.error(
            "=== Pipeline FAILED stages %s in %.1fs ===",
            failed, total_elapsed,
        )
        raise SystemExit(f"Pipeline failed stages: {failed}")
    log.info(
        "=== Pipeline complete in %.1fs. Outputs: %s ===",
        total_elapsed,
        REPO / "outputs" / "research" / "dual_cloud_accumulation_wyckoff",
    )


if __name__ == "__main__":
    main()
