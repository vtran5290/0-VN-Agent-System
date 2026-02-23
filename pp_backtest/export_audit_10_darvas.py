# pp_backtest/export_audit_10_darvas.py — Sample 10 Darvas trades for audit (stop monotonic, add sequencing, avg_entry)
# Run from repo root: python -m pp_backtest.export_audit_10_darvas [--ledger pp_backtest/pp_trade_ledger.csv]
from __future__ import annotations
import argparse
from pathlib import Path

import pandas as pd

_PP = Path(__file__).resolve().parent
DEFAULT_LEDGER = _PP / "pp_trade_ledger.csv"
AUDIT_OUT = _PP / "audit_10_darvas.csv"


def main():
    ap = argparse.ArgumentParser(description="Export 10 Darvas trades for audit.")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER), help="Path to pp_trade_ledger.csv")
    ap.add_argument("-o", "--out", default=str(AUDIT_OUT), help="Output CSV path")
    args = ap.parse_args()

    path = Path(args.ledger)
    if not path.exists():
        print(f"Ledger not found: {path}")
        return 1
    df = pd.read_csv(path)

    if "engine" not in df.columns:
        print("Ledger has no 'engine' column. Run backtest with --entry darvas first.")
        return 1

    darvas = df[df["engine"].astype(str).str.strip().str.lower() == "darvas"].copy()
    if darvas.empty:
        print("No Darvas trades in ledger.")
        print("To generate: python -m pp_backtest.run --no-gate --entry darvas --start 2018-01-01 --end 2024-12-31 [--watchlist config/watchlist_80.txt]")
        # Optionally export 10 rows from any engine for column-structure reference
        if len(df) >= 10:
            out_path = Path(args.out)
            sample = df.head(10)
            sample.to_csv(out_path, index=False)
            print(f"Exported 10 rows (any engine) for column reference: {out_path}")
        return 0 if len(df) >= 10 else 1

    # Target: 4 n_units=1, 4 n_units=2, 2 exit by DARVAS_BOX (by stop)
    u1 = darvas[darvas["n_units"] == 1]
    u2 = darvas[darvas["n_units"] >= 2]
    by_stop = darvas[darvas["exit_reason"].astype(str).str.strip() == "DARVAS_BOX"]

    chosen = []
    for subset, n in [(u1, 4), (u2, 4), (by_stop, 2)]:
        if len(subset) >= n:
            chosen.append(subset.head(n))
        elif len(subset) > 0:
            chosen.append(subset)
    if not chosen:
        chosen = [darvas.head(10)]
    out_df = pd.concat(chosen, ignore_index=True).drop_duplicates().head(10)

    cols = [
        "engine", "symbol", "entry_date", "exit_signal_date", "exit_date",
        "entry_px", "exit_px", "avg_entry_1", "avg_entry_final",
        "stop_at_entry", "stop_at_exit", "n_units", "add_date", "add_px",
        "exit_reason", "hold_trading_bars", "hold_cal_days", "entry_bar_index", "ret",
    ]
    out_cols = [c for c in cols if c in out_df.columns]
    out_df[out_cols].to_csv(Path(args.out), index=False)
    print(f"Exported {len(out_df)} Darvas trades to {args.out}")
    print("Columns:", ", ".join(out_cols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
