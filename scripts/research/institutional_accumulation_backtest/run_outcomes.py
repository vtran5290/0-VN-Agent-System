from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.research.institutional_accumulation_backtest.audits import benchmark_validation_csv, run_coverage_audit
from src.research.institutional_accumulation_backtest.data_loader import (
    discover_universe,
    load_benchmark_df,
    load_symbol_df,
    resolve_sources,
)
from src.research.institutional_accumulation_backtest.manifest import write_manifest
from src.research.institutional_accumulation_backtest.outcomes import compute_forward_outcomes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="data/research/institutional_accumulation/panel_scores.parquet")
    ap.add_argument("--chunk-size", type=int, default=250)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    panel = pd.read_parquet(args.panel)
    src = resolve_sources()
    benchmark = load_benchmark_df(src.benchmark_path)
    prices_by_ticker: dict[str, pd.DataFrame] = {}
    for t in sorted(panel["ticker"].dropna().unique()):
        d = load_symbol_df(src.stocks_dir, str(t))
        if d is not None and not d.empty:
            prices_by_ticker[str(t)] = d
    out_path = Path("data/research/institutional_accumulation/forward_outcomes_panel.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    part_dir = out_path.parent / "outcomes_parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[Path] = []
    tickers = sorted(panel["ticker"].dropna().unique().tolist())
    if args.chunk_size <= 0:
        args.chunk_size = max(1, len(tickers))
    for i in range(0, len(tickers), args.chunk_size):
        sub_tickers = tickers[i : i + args.chunk_size]
        part = part_dir / f"outcomes_part_{i:05d}_{i+len(sub_tickers)-1:05d}.parquet"
        if args.resume and part.is_file():
            chunks.append(part)
            continue
        sub_panel = panel[panel["ticker"].isin(sub_tickers)].copy()
        sub_prices = {k: v for k, v in prices_by_ticker.items() if k in set(sub_tickers)}
        sub_out = compute_forward_outcomes(sub_panel, sub_prices, benchmark)
        sub_out.to_parquet(part, index=False)
        chunks.append(part)
    out = pd.concat([pd.read_parquet(p) for p in chunks], ignore_index=True) if chunks else pd.DataFrame()
    out.to_parquet(out_path, index=False)
    benchmark_validation_csv(benchmark, out, out_path.parent / "benchmark_validation.csv")
    _write_vin_ticker_audit(
        panel=panel,
        outcomes=out,
        prices_by_ticker=prices_by_ticker,
        path=out_path.parent / "vin_ticker_audit.csv",
    )
    max_symbols_used = None
    cadence = "weekly"
    requested_start = str(pd.to_datetime(panel["scan_date"]).min().date()) if not panel.empty else ""
    requested_end = str(pd.to_datetime(panel["scan_date"]).max().date()) if not panel.empty else ""
    mpath = out_path.parent / "backtest_manifest.json"
    manifest: dict = {}
    if mpath.is_file():
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
            ms = (manifest.get("coverage_audit") or {}).get("max_symbols_used")
            if ms not in ("", None):
                max_symbols_used = int(ms)
            cadence = str(manifest.get("rebalance_cadence") or cadence)
            requested_start = str(manifest.get("data_start") or requested_start)
            requested_end = str(manifest.get("data_end") or requested_end)
        except Exception:
            max_symbols_used = None

    cov_df, cov_summary, run_status = run_coverage_audit(
        panel=panel,
        outcomes=out,
        requested_start=requested_start,
        requested_end=requested_end,
        cadence=cadence,
        context_mode=str(panel["context_mode"].iloc[0]) if not panel.empty and "context_mode" in panel.columns else "",
        max_symbols_used=max_symbols_used,
        source_ticker_count=len(discover_universe(src.stocks_dir)),
        vnindex_available=not benchmark.empty,
        vnindex_non_null_rows=int(out[[c for c in out.columns if c.startswith("vnindex_ret_")]].notna().any(axis=1).sum())
        if not out.empty
        else 0,
    )
    cov_df.to_csv(out_path.parent / "run_coverage_audit.csv", index=False)
    if manifest:
        outputs = list(manifest.get("outputs") or [])
        if str(out_path).replace("\\", "/") not in outputs:
            outputs.append(str(out_path).replace("\\", "/"))
        write_manifest(
            mpath,
            run_id=str(manifest.get("run_id") or "ia-backtest"),
            git_commit=str(manifest.get("git_commit") or "unknown"),
            data_start=requested_start,
            data_end=requested_end,
            rebalance_cadence=cadence,
            signal_timing=str(manifest.get("signal_timing") or "close_T_to_open_T_plus_1"),
            universe_policy=str(manifest.get("universe_policy") or ""),
            data_source=str(manifest.get("data_source") or ""),
            context_mode=str(manifest.get("fund_context_mode") or ""),
            outputs=outputs,
            blocked_columns=list(manifest.get("blocked_columns") or []),
            coverage_audit=cov_summary,
            final_run_status=run_status,
        )
    print(f"Wrote {out_path} rows={len(out)} status={run_status}")


def _write_vin_ticker_audit(
    *,
    panel: pd.DataFrame,
    outcomes: pd.DataFrame,
    prices_by_ticker: dict[str, pd.DataFrame],
    path: Path,
) -> None:
    rows = []
    vin = ["VIC", "VHM", "VRE", "VPL"]
    for t in vin:
        src_df = prices_by_ticker.get(t)
        present = src_df is not None and not src_df.empty
        first = str(pd.to_datetime(src_df["date"]).min().date()) if present else ""
        last = str(pd.to_datetime(src_df["date"]).max().date()) if present else ""
        bars = int(len(src_df)) if present else 0
        in_panel = bool((panel["ticker"] == t).any()) if not panel.empty else False
        in_out = bool((outcomes["ticker"] == t).any()) if not outcomes.empty else False
        reason = ""
        if not present:
            reason = "missing_in_source_data"
        elif not in_panel:
            reason = "excluded_by_liquidity_or_filters"
        elif not in_out:
            reason = "missing_forward_data_or_alignment"
        if t == "VPL" and bars < 252:
            reason = (reason + "; " if reason else "") + "vpl_lt_252_bars_event_study_excluded"
        rows.append(
            {
                "ticker": t,
                "present_in_source": present,
                "first_date": first,
                "last_date": last,
                "bar_count": bars,
                "included_in_panel": in_panel,
                "included_in_outcomes": in_out,
                "reason_if_excluded": reason,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


if __name__ == "__main__":
    main()
