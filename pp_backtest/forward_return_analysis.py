"""
forward_return_analysis.py
==========================
Pre-registered spec — DO NOT change parameters after first run.

Purpose:
    Test whether PP entry signals have forward-looking continuation edge
    on VN universe, independent of exit logic.

Method:
    - Use entry dates from existing ledger (pp_trade_ledger_baseline.csv or vn_realistic)
    - For each entry: compute f5 / f10 / f20 forward returns from entry close
    - No exit logic involved — pure price path after entry

Pre-registered decisions:
    - Windows: 5, 10, 20 bars
    - Metric: median f10 <= 0 → PP entry has no continuation edge on VN
    - Metric: median f10 > 0 → entry has edge; exit logic is the problem
    - Do NOT add new windows or filters after seeing results

Usage:
    python -m pp_backtest.forward_return_analysis [--ledger PATH] [--ohlcv-dir PATH]
    python -m pp_backtest.forward_return_analysis [--ledger PATH] [--use-fetch]  # use same API as backtest

Output:
    Console table + knowledge/forward_return_summary.json
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Config (pre-registered — do not tune)
# ---------------------------------------------------------------------------
FORWARD_BARS = [5, 10, 20]          # windows to measure
DEFAULT_LEDGER = "pp_backtest/pp_trade_ledger_baseline.csv"
DEFAULT_OHLCV_DIR = "data/ohlcv"    # optional: local CSVs
OUTPUT_JSON = "knowledge/forward_return_summary.json"
BAR_BUFFER_DAYS = 45                # calendar days after last entry to cover 20 bars


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_ohlcv_from_dir(symbol: str, ohlcv_dir: str) -> pd.DataFrame | None:
    """Load OHLCV for a symbol from local CSVs. Tries common file name patterns."""
    candidates = [
        Path(ohlcv_dir) / f"{symbol}.csv",
        Path(ohlcv_dir) / f"{symbol.upper()}.csv",
        Path(ohlcv_dir) / f"{symbol.lower()}.csv",
    ]
    for path in candidates:
        if path.exists():
            df = pd.read_csv(path, parse_dates=["date"])
            df = df.sort_values("date").reset_index(drop=True)
            return df
    return None


def fetch_ohlcv_for_symbol(
    symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    use_vnstock: bool = False,
) -> pd.DataFrame | None:
    """Fetch OHLCV from same source as backtest (FireAnt or vnstock)."""
    try:
        if use_vnstock:
            from pp_backtest.data import fetch_ohlcv_vnstock
            return fetch_ohlcv_vnstock(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        else:
            from pp_backtest.data import fetch_ohlcv_fireant
            return fetch_ohlcv_fireant(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    except Exception as e:
        print(f"[warn] fetch failed {symbol}: {e}", file=sys.stderr)
        return None


def compute_forward_returns(
    entry_date: pd.Timestamp,
    symbol: str,
    ohlcv: pd.DataFrame,
    windows: list[int],
) -> dict | None:
    """
    Compute forward returns at bar+N from entry_date close.
    Returns dict of {f5: float, f10: float, f20: float} or None if data missing.
    """
    idx_arr = ohlcv.index[ohlcv["date"] == entry_date].tolist()
    if not idx_arr:
        # Try nearest date (entry may be next-open; use next available bar)
        future = ohlcv[ohlcv["date"] >= entry_date]
        if future.empty:
            return None
        idx = future.index[0]
    else:
        idx = idx_arr[0]

    entry_close = ohlcv.loc[idx, "close"]
    if pd.isna(entry_close) or entry_close <= 0:
        return None

    result = {}
    for w in windows:
        target_idx = idx + w
        if target_idx >= len(ohlcv):
            result[f"f{w}"] = None  # not enough bars
        else:
            fwd_close = ohlcv.loc[target_idx, "close"]
            result[f"f{w}"] = (fwd_close / entry_close) - 1 if fwd_close > 0 else None

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Forward return analysis from PP entry signals")
    parser.add_argument("--ledger", default=DEFAULT_LEDGER, help="Path to trade ledger CSV")
    parser.add_argument("--ohlcv-dir", default=None, help="Directory with per-symbol OHLCV CSVs (if not set, use --use-fetch)")
    parser.add_argument("--use-fetch", action="store_true", help="Fetch OHLCV from API (same as backtest); no local CSVs needed")
    parser.add_argument("--vnstock", action="store_true", help="Use vnstock instead of FireAnt when --use-fetch")
    parser.add_argument("--out", default=OUTPUT_JSON, help="Output JSON path")
    args = parser.parse_args()

    use_fetch = args.use_fetch or (args.ohlcv_dir is None)
    if not use_fetch and not args.ohlcv_dir:
        args.ohlcv_dir = DEFAULT_OHLCV_DIR

    # --- Load ledger ---
    ledger_path = Path(args.ledger)
    if not ledger_path.exists():
        print(f"[ERROR] Ledger not found: {ledger_path}")
        sys.exit(1)

    ledger = pd.read_csv(ledger_path, parse_dates=["entry_date"])
    print(f"[info] Loaded ledger: {len(ledger)} trades from {ledger_path.name}")
    print(f"[info] Symbols: {sorted(ledger['symbol'].unique())}")
    print(f"[info] Date range: {ledger['entry_date'].min().date()} -> {ledger['entry_date'].max().date()}")
    print(f"[info] Forward windows: {FORWARD_BARS}")
    print(f"[info] OHLCV source: {'fetch (API)' if use_fetch else f'local dir {args.ohlcv_dir}'}")
    print()

    # --- Compute forward returns ---
    ohlcv_cache: dict[str, pd.DataFrame | None] = {}
    records = []
    skipped_no_ohlcv = 0
    skipped_no_data = 0

    if use_fetch:
        # Per-symbol date range: min(entry_date) to max(entry_date) + buffer for 20 bars
        symbol_ranges = ledger.groupby("symbol")["entry_date"].agg(["min", "max"])
    else:
        symbol_ranges = None

    for _, row in ledger.iterrows():
        symbol = row["symbol"]
        entry_date = row["entry_date"]

        if symbol not in ohlcv_cache:
            if use_fetch and symbol_ranges is not None:
                start = symbol_ranges.loc[symbol, "min"]
                end = symbol_ranges.loc[symbol, "max"] + timedelta(days=BAR_BUFFER_DAYS)
                ohlcv_cache[symbol] = fetch_ohlcv_for_symbol(symbol, start, end, use_vnstock=args.vnstock)
            else:
                ohlcv_cache[symbol] = load_ohlcv_from_dir(symbol, args.ohlcv_dir or "")

        ohlcv = ohlcv_cache[symbol]
        if ohlcv is None:
            skipped_no_ohlcv += 1
            continue

        fwd = compute_forward_returns(entry_date, symbol, ohlcv, FORWARD_BARS)
        if fwd is None:
            skipped_no_data += 1
            continue

        records.append({
            "symbol": symbol,
            "entry_date": entry_date,
            **fwd,
        })

    if not records:
        print("[ERROR] No forward returns computed. Check --ohlcv-dir or use --use-fetch.")
        sys.exit(1)

    df = pd.DataFrame(records)
    n_total = len(df)
    print(f"[info] Forward returns computed: {n_total} trades")
    print(f"[info] Skipped (no OHLCV): {skipped_no_ohlcv}")
    print(f"[info] Skipped (insufficient bars): {skipped_no_data}")
    print()

    # --- Summary stats ---
    print("=" * 60)
    print("FORWARD RETURN SUMMARY (pre-registered: median f10 is key)")
    print("=" * 60)

    summary = {}
    for w in FORWARD_BARS:
        col = f"f{w}"
        s = df[col].dropna()
        stats = {
            "n":          int(len(s)),
            "mean":       round(float(s.mean()), 4),
            "median":     round(float(s.median()), 4),
            "p25":        round(float(s.quantile(0.25)), 4),
            "p75":        round(float(s.quantile(0.75)), 4),
            "pct_positive": round(float((s > 0).mean()), 4),
        }
        summary[col] = stats
        print(f"  f{w:2d}: n={stats['n']:4d}  mean={stats['mean']:+.2%}  "
              f"median={stats['median']:+.2%}  "
              f"pct_pos={stats['pct_positive']:.1%}  "
              f"[p25={stats['p25']:+.2%}, p75={stats['p75']:+.2%}]")

    print()

    # --- Pre-registered decision rule ---
    f10_median = summary["f10"]["median"]
    f10_pct_pos = summary["f10"]["pct_positive"]

    print("DECISION (pre-registered):")
    if f10_median <= 0:
        verdict = "NO_EDGE"
        print(f"  median f10 = {f10_median:+.2%} <= 0")
        print("  -> PP entry has NO continuation edge on VN universe.")
        print("  -> Exit tweaks are unlikely to fix aggregate PF.")
        print("  -> Consider: universe filter (leader-only) or alternative entry signal.")
    else:
        verdict = "EDGE_EXISTS"
        print(f"  median f10 = {f10_median:+.2%} > 0")
        print("  -> PP entry has continuation edge.")
        print("  -> Problem is likely in exit logic or position sizing.")

    print()

    # --- Per-symbol breakdown ---
    print("PER-SYMBOL BREAKDOWN (f10 median):")
    per_symbol = (
        df.groupby("symbol")["f10"]
        .agg(n="count", median="median", pct_pos=lambda x: (x > 0).mean())
        .round(4)
        .sort_values("median", ascending=False)
    )
    print(per_symbol.to_string())
    print()

    # --- Save JSON ---
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "generated_at": datetime.now().isoformat(),
        "ledger": str(ledger_path),
        "n_trades": n_total,
        "skipped_no_ohlcv": skipped_no_ohlcv,
        "skipped_insufficient_bars": skipped_no_data,
        "forward_windows": FORWARD_BARS,
        "summary": summary,
        "verdict": verdict,
        "f10_median": f10_median,
        "f10_pct_positive": f10_pct_pos,
        "decision_rule": "median_f10 <= 0 -> NO_EDGE; > 0 -> EDGE_EXISTS",
        "per_symbol_f10": per_symbol.reset_index().to_dict(orient="records"),
    }
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"[info] Saved: {out_path}")


if __name__ == "__main__":
    main()
