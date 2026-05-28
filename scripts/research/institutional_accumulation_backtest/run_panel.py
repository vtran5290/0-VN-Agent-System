from __future__ import annotations

import argparse
import subprocess
import uuid
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.panel_worker import build_panel_chunk_job

from src.research.institutional_accumulation_backtest.audits import run_coverage_audit
from src.research.institutional_accumulation_backtest.data_loader import (
    discover_universe,
    load_benchmark_df,
    load_sector_map,
    resolve_sources,
)
from src.research.institutional_accumulation_backtest.manifest import write_manifest
from src.research.institutional_accumulation_backtest.panel import PanelConfig, build_panel
from src.research.institutional_accumulation_backtest.regimes import build_benchmark_regimes
from src.research.institutional_accumulation_backtest.schema import ContextMode, VinPolicy


def _git_commit() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL)
            .strip()
        )
    except Exception:
        return "unknown"


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning, module="src.scans.institutional_accumulation.indicators")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--end", default="latest")
    ap.add_argument("--cadence", default="weekly", choices=["weekly", "monthly"])
    ap.add_argument("--context-mode", default="ohlcv_only")
    ap.add_argument("--max-symbols", type=int, default=0)
    ap.add_argument("--chunk-size", type=int, default=200)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--workers", type=int, default=1, help="parallel symbol chunks (Windows spawn)")
    ap.add_argument("--consolidate-only", action="store_true", help="merge chunk parts only (no rebuild)")
    args = ap.parse_args()

    sources = resolve_sources()
    benchmark = load_benchmark_df(sources.benchmark_path)
    end = str(pd.to_datetime(benchmark["date"]).max().date()) if args.end == "latest" else args.end
    benchmark = benchmark[(pd.to_datetime(benchmark["date"]) >= pd.Timestamp(args.start)) & (pd.to_datetime(benchmark["date"]) <= pd.Timestamp(end))]
    symbols = discover_universe(sources.stocks_dir)
    max_symbols_used = None
    if args.max_symbols and args.max_symbols > 0:
        symbols = symbols[: args.max_symbols]
        max_symbols_used = args.max_symbols
    sectors = load_sector_map(sources.sector_map_path)
    regimes = build_benchmark_regimes(benchmark)
    cfg = PanelConfig(
        start=args.start,
        end=end,
        cadence=args.cadence,
        context_mode=ContextMode.from_cli(args.context_mode),
    )
    out_dir = Path("data/research/institutional_accumulation")
    out_dir.mkdir(parents=True, exist_ok=True)
    part_dir = out_dir / "panel_scores_parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    notes = {"blocked_columns": []}
    if args.chunk_size <= 0:
        args.chunk_size = max(1, len(symbols))
    chunk_jobs: list[tuple[int, list[str], Path]] = []
    if args.consolidate_only:
        chunk_jobs = []
    for i in range(0, len(symbols), args.chunk_size):
        if args.consolidate_only:
            continue
        chunk = symbols[i : i + args.chunk_size]
        part = part_dir / f"panel_part_{i:05d}_{i+len(chunk)-1:05d}.parquet"
        if args.resume and part.is_file():
            continue
        chunk_jobs.append((i, chunk, part))

    def _run_one(job: tuple[int, list[str], Path]) -> Path:
        i, chunk, part = job
        panel_chunk, notes_local = build_panel(
            cfg,
            benchmark=benchmark,
            benchmark_slice=benchmark,
            symbols=chunk,
            stocks_dir=sources.stocks_dir,
            sector_map=sectors,
            regimes=regimes,
            vin_policy=VinPolicy(),
        )
        panel_chunk.to_parquet(part, index=False)
        notes["blocked_columns"] = notes_local.get("blocked_columns", [])
        print(f"chunk {i:05d} symbols={len(chunk)} rows={len(panel_chunk)}", flush=True)
        return part

    if chunk_jobs:
        if args.workers > 1:
            payloads = [
                {
                    "symbols": chunk,
                    "part_path": str(part),
                    "benchmark_path": str(sources.benchmark_path),
                    "start": args.start,
                    "end": end,
                    "cadence": args.cadence,
                    "context_mode": args.context_mode,
                }
                for _, chunk, part in chunk_jobs
            ]
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(build_panel_chunk_job, payload) for payload in payloads]
                for fut in as_completed(futures):
                    result = fut.result()
                    notes["blocked_columns"] = result.get("blocked_columns", [])
                    print(
                        f"chunk done symbols={len(result.get('symbols', []))} rows={result.get('rows', 0)}",
                        flush=True,
                    )
        else:
            for job in chunk_jobs:
                _run_one(job)
    expected_parts: list[Path] = []
    for i in range(0, len(symbols), args.chunk_size):
        chunk = symbols[i : i + args.chunk_size]
        part = part_dir / f"panel_part_{i:05d}_{i+len(chunk)-1:05d}.parquet"
        if part.is_file():
            expected_parts.append(part)
    parts = expected_parts
    panel = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True) if parts else pd.DataFrame()
    if not panel.empty:
        panel = panel.drop_duplicates(subset=["scan_date", "ticker"], keep="last")
    panel_path = out_dir / "panel_scores.parquet"
    panel.to_parquet(panel_path, index=False)
    cov_df, cov_summary, run_status = run_coverage_audit(
        panel=panel,
        outcomes=None,
        requested_start=args.start,
        requested_end=end,
        cadence=args.cadence,
        context_mode=cfg.context_mode.value,
        max_symbols_used=max_symbols_used,
        source_ticker_count=len(discover_universe(sources.stocks_dir)),
        vnindex_available=not benchmark.empty,
        vnindex_non_null_rows=int(benchmark["close"].notna().sum()) if "close" in benchmark.columns else 0,
    )
    cov_df.to_csv(out_dir / "run_coverage_audit.csv", index=False)
    write_manifest(
        out_dir / "backtest_manifest.json",
        run_id=f"ia-backtest-{uuid.uuid4().hex[:8]}",
        git_commit=_git_commit(),
        data_start=args.start,
        data_end=end,
        rebalance_cadence=args.cadence,
        signal_timing="close_T_to_open_T_plus_1",
        universe_policy="liquid universe with min_history=120, adv20>=2B, adv50>=1.5B, ETF excluded",
        data_source=sources.source_label,
        context_mode=cfg.context_mode.value,
        outputs=[str(panel_path).replace("\\", "/")],
        blocked_columns=notes.get("blocked_columns", []),
        coverage_audit=cov_summary,
        final_run_status=run_status,
    )
    print(f"Wrote {panel_path} rows={len(panel)}")


if __name__ == "__main__":
    main()
