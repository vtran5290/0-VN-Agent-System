"""
Phase-2 closed-loop orchestrator for base/PP/breakout research.

Loop:
1) run robust event study
2) read OOS robustness + run manifest
3) generate next grid (exploit + small neighborhood mutations)
4) rerun

Research-only automation (no live trading claims).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent

_BASE_DAYS = [70, 80, 90]
_MIN_DEPTH = [0.10, 0.12]
_MAX_DEPTH = [0.28, 0.32]
_MIN_POS = [0.50, 0.55]
_MAX_DIST = [0.08, 0.12]
_ANTI = [1, 2, 3]
_PP = ["rung2", "rung3", "ge2"]
_EB = [0.0015, 0.003]
_FAM = ["sma20", "sma50"]
_MULT = [1.25, 1.35, 1.50]


def _nearest(vals: list[float], x: float) -> float:
    return min(vals, key=lambda v: abs(v - x))


def _neighbors(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Small auditable mutation set around one row."""
    base = {
        "base_days": int(row["base_days"]),
        "min_base_depth": float(row["min_base_depth"]),
        "max_base_depth": float(row["max_base_depth"]),
        "min_base_pos": float(row["min_base_pos"]),
        "max_dist_pivot": float(row["max_dist_pivot"]),
        "anti_drift_mode": int(row["anti_drift_mode"]),
        "pp_bucket": str(row["pp_bucket"]),
        "entry_buffer": float(row["entry_buffer"]),
        "breakout_vol_family": str(row["breakout_vol_family"]),
        "breakout_vol_mult": float(row["breakout_vol_mult"]),
    }
    out = [base]

    def add(mut: dict[str, Any]) -> None:
        r = dict(base)
        r.update(mut)
        out.append(r)

    bd = base["base_days"]
    add({"base_days": _BASE_DAYS[max(0, _BASE_DAYS.index(_nearest(_BASE_DAYS, bd)) - 1)]})
    add({"base_days": _BASE_DAYS[min(len(_BASE_DAYS) - 1, _BASE_DAYS.index(_nearest(_BASE_DAYS, bd)) + 1)]})

    anti = base["anti_drift_mode"]
    if anti > 1:
        add({"anti_drift_mode": anti - 1})
    if anti < 3:
        add({"anti_drift_mode": anti + 1})

    add({"pp_bucket": "ge2"})
    add({"pp_bucket": "rung2"})
    add({"pp_bucket": "rung3"})

    add({"entry_buffer": 0.0015})
    add({"entry_buffer": 0.003})

    fam = base["breakout_vol_family"]
    add({"breakout_vol_family": "sma50" if fam == "sma20" else "sma20"})

    m = base["breakout_vol_mult"]
    mi = _MULT.index(_nearest(_MULT, m))
    add({"breakout_vol_mult": _MULT[max(0, mi - 1)]})
    add({"breakout_vol_mult": _MULT[min(len(_MULT) - 1, mi + 1)]})

    add({"min_base_depth": _MIN_DEPTH[0], "max_base_depth": _MAX_DEPTH[1], "min_base_pos": _MIN_POS[0], "max_dist_pivot": _MAX_DIST[0]})
    add({"min_base_depth": _MIN_DEPTH[1], "max_base_depth": _MAX_DEPTH[0], "min_base_pos": _MIN_POS[1], "max_dist_pivot": _MAX_DIST[1]})
    return out


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        k = json.dumps(r, sort_keys=True)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _build_next_grid(run_dir: Path, top_k: int, min_n_oos: int, max_next: int) -> dict[str, Any]:
    rob = pd.read_csv(run_dir / "summary_oos_robustness.csv")
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    manifest = meta.get("grid_manifest", [])
    by_id = {m.get("param_set_id"): m.get("params", {}) for m in manifest}
    if rob.empty:
        return {"source_run_dir": str(run_dir), "selected_param_ids": [], "recommended_grid": []}

    rob = rob.sort_values("robustness_score", ascending=False)
    rob = rob[rob["n_oos"] >= min_n_oos]
    top = rob.head(top_k)

    seeds: list[dict[str, Any]] = []
    sel_ids: list[str] = []
    for _, r in top.iterrows():
        pid = str(r["param_set_id"])
        row = by_id.get(pid)
        if row:
            seeds.append(row)
            sel_ids.append(pid)

    generated: list[dict[str, Any]] = []
    for s in seeds:
        generated.extend(_neighbors(s))
    grid = _dedupe_rows(generated)[:max_next]
    return {
        "source_run_dir": str(run_dir),
        "selected_param_ids": sel_ids,
        "top_k": int(top_k),
        "min_n_oos": int(min_n_oos),
        "max_next": int(max_next),
        "recommended_grid": grid,
    }


def _run_robust(
    python_exe: str,
    robust_script: Path,
    out_dir: Path,
    *,
    start_year: int,
    max_symbols: int,
    min_adv20: float,
    trend: str,
    max_configs: int,
    grid_profile: str | None = None,
    grid_file: Path | None = None,
) -> None:
    cmd = [
        python_exe,
        str(robust_script),
        "--start-year",
        str(start_year),
        "--min-adv20",
        str(min_adv20),
        "--trend",
        trend,
        "--out-dir",
        str(out_dir),
    ]
    if max_symbols > 0:
        cmd += ["--max-symbols", str(max_symbols)]
    if max_configs > 0:
        cmd += ["--max-configs", str(max_configs)]
    if grid_file is not None:
        cmd += ["--grid-file", str(grid_file)]
    else:
        cmd += ["--grid-profile", str(grid_profile or "phase1")]
    print("[loop] running:", " ".join(cmd), flush=True)
    env = dict(**{"PYTHONUNBUFFERED": "1"}, **dict())
    # Merge current env while forcing unbuffered child output.
    import os

    env = {**os.environ, **env}
    p = subprocess.Popen(cmd, env=env)
    t0 = time.time()
    while True:
        rc = p.poll()
        if rc is not None:
            if rc != 0:
                raise subprocess.CalledProcessError(rc, cmd)
            elapsed = int(time.time() - t0)
            print(f"[loop] child done in {elapsed}s", flush=True)
            return
        elapsed = int(time.time() - t0)
        # Heartbeat every 60s so long runs do not look stalled/aborted.
        print(f"[loop] child running... {elapsed}s elapsed", flush=True)
        time.sleep(60)


def main() -> int:
    ap = argparse.ArgumentParser(description="Closed-loop phase-2 runner for robust event-study.")
    ap.add_argument("--iterations", type=int, default=2, help="Number of robust-study iterations to run.")
    ap.add_argument("--seed-grid-profile", choices=["smoke", "phase1", "full", "full_plus_pct"], default="phase1")
    ap.add_argument("--top-k", type=int, default=24, help="Top OOS robust configs to seed next grid.")
    ap.add_argument("--min-n-oos", type=int, default=120, help="Min OOS rows required for a config to be selected.")
    ap.add_argument("--max-next-configs", type=int, default=192, help="Cap configs in auto-generated next grid.")
    ap.add_argument("--max-symbols", type=int, default=0)
    ap.add_argument("--start-year", type=int, default=2018)
    ap.add_argument("--min-adv20", type=float, default=2e9)
    ap.add_argument("--trend", choices=["medium", "relaxed", "none"], default="relaxed")
    ap.add_argument("--max-configs-initial", type=int, default=0)
    ap.add_argument("--max-configs-next", type=int, default=0)
    ap.add_argument(
        "--resume",
        action="store_true",
        help="If set, skip iterations already completed (run_meta + summary_oos_robustness exist).",
    )
    ap.add_argument(
        "--loop-out-dir",
        default="minervini_backtest/outputs/accumulation_scan/base_pp_breakout_closed_loop_v1",
    )
    args = ap.parse_args()

    robust_script = REPO / "minervini_backtest" / "scripts" / "research_base_pp_breakout_robust.py"
    if not robust_script.exists():
        raise FileNotFoundError(f"missing robust script: {robust_script}")

    loop_root = REPO / args.loop_out_dir
    loop_root.mkdir(parents=True, exist_ok=True)

    report_lines = [
        "# Closed-loop run report",
        "",
        "Research-only automation. No live profitability claims.",
        "",
    ]

    next_grid_file: Path | None = None
    for i in range(1, int(args.iterations) + 1):
        run_dir = loop_root / f"iter_{i:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        done_marker = (run_dir / "run_meta.json").exists() and (run_dir / "summary_oos_robustness.csv").exists()
        if done_marker and args.resume:
            print(f"[loop] iter_{i:02d} already complete, skipping due to --resume", flush=True)
        else:
            _run_robust(
                sys.executable,
                robust_script,
                run_dir,
                start_year=int(args.start_year),
                max_symbols=int(args.max_symbols),
                min_adv20=float(args.min_adv20),
                trend=str(args.trend),
                max_configs=int(args.max_configs_initial if i == 1 else args.max_configs_next),
                grid_profile=str(args.seed_grid_profile) if i == 1 and next_grid_file is None else None,
                grid_file=next_grid_file,
            )

        fb = _build_next_grid(run_dir, int(args.top_k), int(args.min_n_oos), int(args.max_next_configs))
        next_grid_file = run_dir / "recommended_next_grid.json"
        next_grid_file.write_text(json.dumps(fb["recommended_grid"], indent=2), encoding="utf-8")
        (run_dir / "feedback_meta.json").write_text(json.dumps(fb, indent=2), encoding="utf-8")

        selected = len(fb.get("selected_param_ids", []))
        next_n = len(fb.get("recommended_grid", []))
        report_lines.append(f"- Iter {i:02d}: run_dir=`{run_dir}` selected={selected} next_grid={next_n}")

    report_lines.append("")
    report_lines.append(f"- Final suggested grid file: `{next_grid_file}`" if next_grid_file else "- No next grid generated.")
    (loop_root / "loop_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"[loop] finished. root={loop_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
