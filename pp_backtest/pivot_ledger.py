# pp_backtest/pivot_ledger.py — Pivot tables from pp_trade_ledger.csv
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd
import numpy as np

_PP = Path(__file__).resolve().parent
DEFAULT_LEDGER = _PP / "pp_trade_ledger.csv"


def pivot1_by_reason(ledger: pd.DataFrame) -> pd.DataFrame:
    """Pivot 1: effectiveness by exit_reason. Uses hold_cal_days (fallback hold_days)."""
    hcol = "hold_cal_days" if "hold_cal_days" in ledger.columns else "hold_days"
    g = ledger.groupby("exit_reason", dropna=False)
    out = g.agg(
        count_trades=("ret", "count"),
        win_rate=("ret", lambda s: (s > 0).mean()),
        avg_ret=("ret", "mean"),
        median_ret=("ret", "median"),
        avg_hold_days=(hcol, "mean"),
        avg_mkt_dd_count=("mkt_dd_count", "mean"),
        avg_stk_dd_count=("stk_dd_count", "mean"),
    ).round(4)
    return out


def pivot2_tail_loss_by_reason(ledger: pd.DataFrame, ret_threshold: float = -0.05) -> pd.DataFrame:
    """Pivot 2: tail loss (ret <= threshold) by exit_reason."""
    tail = ledger[ledger["ret"] <= ret_threshold]
    g = tail.groupby("exit_reason", dropna=False)
    out = g.agg(
        count_trades=("ret", "count"),
        avg_ret=("ret", "mean"),
        median_ret=("ret", "median"),
        min_ret=("ret", "min"),
    ).round(4)
    return out


def pivot3_mfe_after_market_dd(ledger: pd.DataFrame, fetch_ohlcv, mfe_bars: int = 20) -> pd.DataFrame:
    """Pivot 3: MARKET_DD exits — MFE in next mfe_bars sessions."""
    mdd = ledger[ledger["exit_reason"] == "MARKET_DD"].copy()
    if mdd.empty:
        return pd.DataFrame()
    from datetime import timedelta
    mfe_list = []
    for _, row in mdd.iterrows():
        sym, exit_dt = row["symbol"], pd.to_datetime(row["exit_date"])
        exit_px = float(row["exit_px"])
        try:
            end_dt = exit_dt + timedelta(days=max(60, mfe_bars * 2))
            df = fetch_ohlcv(sym, exit_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
            if df is None or len(df) == 0:
                mfe_list.append({"symbol": sym, "exit_date": exit_dt, "mfe_pct": np.nan, "bars_used": 0})
                continue
            df["date"] = pd.to_datetime(df["date"])
            df = df[df["date"] > exit_dt].head(mfe_bars)
            if len(df) == 0:
                mfe_list.append({"symbol": sym, "exit_date": exit_dt, "mfe_pct": np.nan, "bars_used": 0})
                continue
            max_high = df["high"].max()
            mfe_pct = (max_high / exit_px - 1.0) * 100
            mfe_list.append({"symbol": sym, "exit_date": exit_dt, "mfe_pct": mfe_pct, "bars_used": len(df)})
        except Exception:
            mfe_list.append({"symbol": sym, "exit_date": exit_dt, "mfe_pct": np.nan, "bars_used": -1})
    return pd.DataFrame(mfe_list)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ap.add_argument("--tail", type=float, default=-0.05)
    ap.add_argument("--mfe", action="store_true")
    ap.add_argument("--mfe-bars", type=int, default=20)
    args = ap.parse_args()

    path = Path(args.ledger)
    if not path.exists():
        print(f"Ledger not found: {path}")
        return
    ledger = pd.read_csv(path)
    ledger["ret"] = ledger["ret"].astype(float)
    hcol = "hold_cal_days" if "hold_cal_days" in ledger.columns else "hold_days"
    ledger[hcol] = pd.to_numeric(ledger[hcol], errors="coerce")

    print("=== Pivot 1: Effectiveness by exit_reason ===")
    print(pivot1_by_reason(ledger).to_string())
    print("\n=== Pivot 2: Tail loss (ret <= {}) by exit_reason ===".format(args.tail))
    print(pivot2_tail_loss_by_reason(ledger, ret_threshold=args.tail).to_string())

    if args.mfe:
        print("\n=== Pivot 3: MFE after MARKET_DD (next {} bars) ===".format(args.mfe_bars))
        try:
            _REPO = path.resolve().parent.parent
            if str(_REPO) not in sys.path:
                sys.path.insert(0, str(_REPO))
            from pp_backtest.data import fetch_ohlcv_fireant
            p3 = pivot3_mfe_after_market_dd(ledger, fetch_ohlcv_fireant, mfe_bars=args.mfe_bars)
            if p3.empty:
                print("No MARKET_DD trades.")
            else:
                valid = p3["mfe_pct"].notna()
                print(p3.head(20).to_string())
                if valid.any():
                    print("MFE avg %:", p3.loc[valid, "mfe_pct"].mean())
        except Exception as e:
            print("MFE failed:", e)
    else:
        print("\n(Run with --mfe for MFE after MARKET_DD exits.)")


if __name__ == "__main__":
    main()
