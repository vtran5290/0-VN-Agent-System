"""Phase 3: Full-history forward outcomes.

Computes forward returns at T+1 entry (no lookahead) for all scan dates
in the full-history panel.

RESEARCH_ONLY_NOT_PRODUCTION
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .fh_data_loader import ParquetSymbolLoader, load_fh_benchmark

RESEARCH_ONLY_FLAG = "RESEARCH_ONLY_NOT_PRODUCTION"
HORIZONS = (5, 10, 20, 60, 120)
EX_VIN = {"VIC", "VHM", "VRE"}


def _next_open(px: pd.DataFrame, scan_dt: pd.Timestamp) -> tuple[float | None, str | None]:
    """Return (open_price, date_str) for the first trading day after scan_dt."""
    future = px[px["date"] > scan_dt]
    if future.empty:
        return None, None
    row = future.iloc[0]
    price = float(row["open"])
    if price <= 0 or not np.isfinite(price):
        return None, None
    return price, str(row["date"].date())


def _forward_close(px: pd.DataFrame, entry_idx: int, h: int) -> tuple[float | None, str | None]:
    """Return (close_price, date_str) h bars after entry index."""
    j = entry_idx + h
    if j >= len(px):
        return None, None
    row = px.iloc[j]
    price = float(row["close"])
    if price <= 0 or not np.isfinite(price):
        return None, None
    return price, str(row["date"].date())


def _max_drawdown_window(px: pd.DataFrame, entry_idx: int, h: int) -> float | None:
    """Max drawdown from entry_open to h bars later, measured on close."""
    if entry_idx + h >= len(px):
        return None
    window = px.iloc[entry_idx : entry_idx + h + 1]["close"].astype(float).values
    if len(window) < 2:
        return None
    peak = window[0]
    mdd = 0.0
    for p in window[1:]:
        peak = max(peak, p)
        dd = p / peak - 1.0
        mdd = min(mdd, dd)
    return float(mdd)


def _hit_dd(px: pd.DataFrame, entry_idx: int, h: int, threshold: float) -> bool:
    """Did the close drop below threshold (e.g. -0.05) within h bars?"""
    mdd = _max_drawdown_window(px, entry_idx, h)
    if mdd is None:
        return False
    return mdd <= threshold


def compute_fh_forward_outcomes(
    panel: pd.DataFrame,
    loader: ParquetSymbolLoader,
    verbose: bool = True,
) -> pd.DataFrame:
    """Build forward outcome columns for the full-history panel.

    Entry: T+1 open (no lookahead).
    Returns join of panel + forward return columns.

    Memory-efficient: builds only outcome columns separately, then merges with panel.
    """
    panel = panel.copy()
    panel["scan_date"] = pd.to_datetime(panel["scan_date"], errors="coerce").dt.normalize()

    bench = load_fh_benchmark()
    bench["date"] = pd.to_datetime(bench["date"]).dt.normalize()
    bench = bench.sort_values("date").reset_index(drop=True)
    bench_idx = {pd.Timestamp(d): i for i, d in enumerate(bench["date"])}
    bench_close = bench["close"].astype(float).values

    # Build ONLY outcome columns (not full panel row dicts) — avoids OOM on 288k rows
    outcome_cols: list[dict[str, Any]] = []

    tickers = panel["ticker"].unique()
    for i, ticker in enumerate(tickers):
        if verbose and i % 200 == 0:
            print(f"[Phase 3] Outcomes: {i}/{len(tickers)} tickers")
        px = loader(ticker)
        if px is None or px.empty:
            continue
        px = px.sort_values("date").reset_index(drop=True)
        px["date"] = pd.to_datetime(px["date"]).dt.normalize()
        px_idx = {pd.Timestamp(d): j for j, d in enumerate(px["date"])}

        ticker_rows = panel[panel["ticker"] == ticker]
        for _, panel_row in ticker_rows.iterrows():
            scan_dt = panel_row["scan_date"]
            # Only store join keys + new outcome columns (not full row dict)
            oc: dict[str, Any] = {
                "scan_date": scan_dt,
                "ticker": ticker,
            }

            # Find T+1 entry
            future_px = px[px["date"] > scan_dt]
            if future_px.empty:
                oc.update({"entry_date": None, "entry_price_open_t1": None, "entry_price_close_t": None})
                for h in HORIZONS:
                    oc[f"ret_{h}d"] = None
                    oc[f"vnindex_ret_{h}d"] = None
                    oc[f"excess_ret_{h}d"] = None
                    oc[f"exit_date_{h}d"] = None
                oc["max_dd_20d"] = None
                oc["max_dd_60d"] = None
                oc["p_dd5_60d"] = None
                oc["p_dd10_60d"] = None
                outcome_cols.append(oc)
                continue

            entry_row = future_px.iloc[0]
            entry_dt = pd.Timestamp(entry_row["date"])
            entry_price = float(entry_row["open"])
            if entry_price <= 0 or not np.isfinite(entry_price):
                entry_price = None

            # Close at T (scan date) for reference
            scan_px = px[px["date"] == scan_dt]
            close_t = float(scan_px.iloc[-1]["close"]) if not scan_px.empty else None

            oc["entry_date"] = str(entry_dt.date())
            oc["entry_price_open_t1"] = entry_price
            oc["entry_price_close_t"] = close_t

            # Find entry index in px
            entry_idx = px_idx.get(entry_dt)
            if entry_idx is None:
                for h in HORIZONS:
                    oc[f"ret_{h}d"] = None
                    oc[f"vnindex_ret_{h}d"] = None
                    oc[f"excess_ret_{h}d"] = None
                    oc[f"exit_date_{h}d"] = None
                oc["max_dd_20d"] = None
                oc["max_dd_60d"] = None
                oc["p_dd5_60d"] = None
                oc["p_dd10_60d"] = None
                outcome_cols.append(oc)
                continue

            # Bench entry idx
            bench_entry_idx = bench_idx.get(entry_dt)

            for h in HORIZONS:
                exit_close, exit_date = _forward_close(px, entry_idx, h)
                if exit_close is not None and entry_price is not None and entry_price > 0:
                    ret = exit_close / entry_price - 1.0
                else:
                    ret = None
                oc[f"ret_{h}d"] = ret
                oc[f"exit_date_{h}d"] = exit_date

                if bench_entry_idx is not None:
                    b_entry = bench_close[bench_entry_idx - 1] if bench_entry_idx > 0 else None
                    b_exit_idx = bench_entry_idx + h
                    if b_exit_idx < len(bench_close) and b_entry and b_entry > 0:
                        b_ret = float(bench_close[b_exit_idx]) / float(b_entry) - 1.0
                    else:
                        b_ret = None
                else:
                    b_ret = None
                oc[f"vnindex_ret_{h}d"] = b_ret
                oc[f"excess_ret_{h}d"] = (
                    (ret - b_ret) if (ret is not None and b_ret is not None) else None
                )

            oc["max_dd_20d"] = _max_drawdown_window(px, entry_idx, 20)
            oc["max_dd_60d"] = _max_drawdown_window(px, entry_idx, 60)
            oc["p_dd5_60d"] = bool(_hit_dd(px, entry_idx, 60, -0.05))
            oc["p_dd10_60d"] = bool(_hit_dd(px, entry_idx, 60, -0.10))
            outcome_cols.append(oc)

    # Merge outcome columns back onto panel (memory-efficient join)
    oc_df = pd.DataFrame(outcome_cols)
    oc_df["scan_date"] = pd.to_datetime(oc_df["scan_date"]).dt.normalize()
    out = panel.merge(oc_df, on=["scan_date", "ticker"], how="left")

    # Ensure is_vin / is_ex_vin columns
    if "is_vin" not in out.columns:
        out["is_vin"] = out["ticker"].isin(EX_VIN)
    if "is_ex_vin" not in out.columns:
        out["is_ex_vin"] = ~out["ticker"].isin(EX_VIN)
    out["research_only_flag"] = RESEARCH_ONLY_FLAG
    return out


def save_fh_outcomes(outcomes: pd.DataFrame, out_dir: Path, out_path=None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = Path(out_path) if out_path is not None else out_dir / "full_history_forward_outcomes.parquet"
    outcomes.to_parquet(path, index=False)
    print(f"[Phase 3] Saved forward outcomes: {path} rows={len(outcomes):,}")
    return path
