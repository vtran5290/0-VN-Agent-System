from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser(description="Checkpointed quick recalibration search.")
    ap.add_argument("--source-root", default="minervini_backtest/outputs/accumulation_scan/base_pp_breakout_closed_loop_v1")
    ap.add_argument("--source-iter", default="iter_03")
    ap.add_argument("--grid-file", default="", help="Optional explicit grid json (list of parameter rows).")
    ap.add_argument("--baseline-score", type=float, default=None, help="Optional baseline override.")
    ap.add_argument("--target-score", type=float, default=None, help="Optional stopping target; defaults to baseline.")
    ap.add_argument("--out-root", default="minervini_backtest/outputs/accumulation_scan/base_pp_breakout_quick_recalibration_round3_medium")
    ap.add_argument("--trend", choices=["relaxed", "medium", "none"], default="medium")
    ap.add_argument("--start-try", type=int, default=1)
    ap.add_argument("--end-try", type=int, default=21)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--min-adv20", type=float, default=2_000_000_000.0)
    args = ap.parse_args()

    src = Path(args.source_root) / args.source_iter
    if args.grid_file:
        grid_path = Path(args.grid_file)
        if not grid_path.exists():
            raise FileNotFoundError(f"Missing grid file: {grid_path}")
        grid = json.loads(grid_path.read_text(encoding="utf-8"))
        if args.baseline_score is not None:
            baseline = float(args.baseline_score)
        else:
            baseline_path = src / "summary_oos_robustness.csv"
            if not baseline_path.exists():
                raise FileNotFoundError(
                    f"Missing baseline summary at {baseline_path}. Pass --baseline-score to override."
                )
            baseline = float(pd.read_csv(baseline_path)["robustness_score"].max())
    else:
        baseline_path = src / "summary_oos_robustness.csv"
        grid_path = src / "recommended_next_grid.json"
        if not baseline_path.exists() or not grid_path.exists():
            raise FileNotFoundError(f"Missing baseline/grid under {src}")
        baseline = float(pd.read_csv(baseline_path)["robustness_score"].max())
        grid = json.loads(grid_path.read_text(encoding="utf-8"))

    target_score = float(args.target_score) if args.target_score is not None else baseline
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    best = baseline
    best_try = args.source_iter
    found = False

    print(
        f"[quick] baseline={baseline:.12f} target={target_score:.12f} grid={len(grid)} trend={args.trend}",
        flush=True,
    )
    for t in range(int(args.start_try), int(args.end_try) + 1):
        s = (t - 1) * int(args.batch_size)
        e = min(len(grid), s + int(args.batch_size))
        if s >= len(grid):
            print("[quick] reached end of grid", flush=True)
            break

        run_dir = out_root / f"try_{t:02d}"
        sum_path = run_dir / "summary_oos_robustness.csv"
        if sum_path.exists():
            df = pd.read_csv(sum_path)
            cur = float(df["robustness_score"].max()) if len(df) else float("-inf")
            print(f"[quick] try {t} already done best={cur:.12f}", flush=True)
        else:
            chunk = grid[s:e]
            gf = out_root / f"grid_try_{t:02d}.json"
            gf.write_text(json.dumps(chunk, indent=2), encoding="utf-8")
            cmd = [
                sys.executable,
                "minervini_backtest/scripts/research_base_pp_breakout_robust.py",
                "--start-year",
                "2018",
                "--trend",
                str(args.trend),
                "--min-adv20",
                str(float(args.min_adv20)),
                "--grid-file",
                str(gf),
                "--out-dir",
                str(run_dir),
            ]
            print(f"[quick] try {t}: configs={len(chunk)}", flush=True)
            rc = subprocess.call(cmd)
            if rc != 0 or not sum_path.exists():
                print(f"[quick] try {t} failed rc={rc}", flush=True)
                continue
            df = pd.read_csv(sum_path)
            cur = float(df["robustness_score"].max()) if len(df) else float("-inf")
            print(f"[quick] try {t} best={cur:.12f}", flush=True)

        if cur > best:
            best = cur
            best_try = f"try_{t:02d}"
        if cur > target_score:
            print(f"[quick] FOUND TARGET at try {t}: {cur:.12f} > {target_score:.12f}", flush=True)
            found = True
            break

    report = {
        "baseline": baseline,
        "target_score": target_score,
        "best_found": best,
        "best_try": best_try,
        "found_better": found,
        "trend": args.trend,
        "start_try": int(args.start_try),
        "end_try": int(args.end_try),
        "batch_size": int(args.batch_size),
    }
    (out_root / "quick_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("[quick] done", json.dumps(report), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
