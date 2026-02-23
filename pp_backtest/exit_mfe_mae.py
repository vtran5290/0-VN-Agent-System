# pp_backtest/exit_mfe_mae.py — Test 2: MFE/MAE 20 bars post-exit by stratum (no re-attribution)
# Run from repo root: python -m pp_backtest.exit_mfe_mae [--bars 20]
# Requires ledger + fetch; outputs MFE_avg, MAE_avg, MFE_median, MAE_median per stratum.
from __future__ import annotations
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_PP = Path(__file__).resolve().parent
_REPO = _PP.parent
_LEDGER = _PP / "pp_trade_ledger.csv"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _reason_set(row):
    r = []
    if row.get("sell_v4") in (True, "True", "true"): r.append("SELL_V4")
    if row.get("sell_mkt_dd") in (True, "True", "true"): r.append("MARKET_DD")
    if row.get("sell_stk_dd") in (True, "True", "true"): r.append("STOCK_DD")
    return "|".join(r) if r else "NONE"


def _strata(df):
    df["reason_set"] = df.apply(_reason_set, axis=1)
    df["multi_reason"] = df["reason_set"].apply(lambda x: x.count("|") >= 1)
    return [
        ("SELL_V4 single", (df["exit_reason"] == "SELL_V4") & (df["reason_set"] == "SELL_V4")),
        ("SELL_V4 multi", (df["exit_reason"] == "SELL_V4") & df["multi_reason"]),
        ("MARKET_DD single", (df["exit_reason"] == "MARKET_DD") & (df["reason_set"] == "MARKET_DD")),
        ("MARKET_DD overlap", (df["exit_reason"] == "MARKET_DD") & (df["reason_set"] == "MARKET_DD|STOCK_DD")),
        ("STOCK_DD", (df["exit_reason"] == "STOCK_DD")),
    ]


def _mfe_mae_one(sym: str, exit_dt, exit_px: float, bars: pd.DataFrame) -> tuple[float, float, float, float]:
    """Returns (mfe_pct, mae_pct, time_to_MFE_bar, time_to_MAE_bar). Bar = 1-based."""
    if len(bars) == 0:
        return np.nan, np.nan, np.nan, np.nan
    max_high = bars["high"].max()
    min_low = bars["low"].min()
    mfe_pct = (max_high / exit_px - 1.0) * 100
    mae_pct = (min_low / exit_px - 1.0) * 100
    # First bar where running max high == max_high / running min low == min_low
    time_to_mfe = ((bars["high"].cummax() == max_high).values.argmax() + 1) if len(bars) else np.nan
    time_to_mae = ((bars["low"].cummin() == min_low).values.argmax() + 1) if len(bars) else np.nan
    return mfe_pct, mae_pct, float(time_to_mfe), float(time_to_mae)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(_LEDGER))
    ap.add_argument("--bars", type=int, default=20)
    ap.add_argument("--vnstock", action="store_true")
    args = ap.parse_args()

    if not Path(args.ledger).exists():
        print("Run backtest first: python -m pp_backtest.run")
        return 1
    df = pd.read_csv(args.ledger)
    for c in ["sell_v4", "sell_mkt_dd", "sell_stk_dd"]:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda x: str(x).lower() == "true")
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    df["exit_px"] = df["exit_px"].astype(float)

    try:
        from pp_backtest.data import fetch_ohlcv_fireant, fetch_ohlcv_vnstock
        fetch = fetch_ohlcv_vnstock if args.vnstock else fetch_ohlcv_fireant
    except Exception as e:
        print("Fetch not available:", e)
        return 1

    strata = _strata(df)
    symbols = df["symbol"].unique().tolist()
    cache = {}
    for sym in symbols:
        start = df[df["symbol"] == sym]["exit_date"].min().strftime("%Y-%m-%d")
        end = (df[df["symbol"] == sym]["exit_date"].max() + timedelta(days=90)).strftime("%Y-%m-%d")
        try:
            cache[sym] = fetch(sym, start, end)
            cache[sym]["date"] = pd.to_datetime(cache[sym]["date"])
        except Exception as e:
            print(f"[skip] {sym}: {e}")
            cache[sym] = pd.DataFrame()

    print(f"=== Test 2: MFE / MAE ({args.bars} bars post-exit) by stratum ===\n")
    for label, mask in strata:
        sub = df.loc[mask].copy()
        if len(sub) == 0:
            print(f"--- {label}: n=0 ---\n")
            continue
        mfe_list, mae_list, t_mfe_list, t_mae_list = [], [], [], []
        for _, row in sub.iterrows():
            sym, exit_dt, exit_px = row["symbol"], row["exit_date"], row["exit_px"]
            ohlc = cache.get(sym)
            if ohlc is None or len(ohlc) == 0:
                mfe_list.append(np.nan); mae_list.append(np.nan)
                t_mfe_list.append(np.nan); t_mae_list.append(np.nan)
                continue
            after = ohlc[ohlc["date"] > exit_dt].head(args.bars)
            mfe_pct, mae_pct, t_mfe, t_mae = _mfe_mae_one(sym, exit_dt, exit_px, after)
            mfe_list.append(mfe_pct); mae_list.append(mae_pct)
            t_mfe_list.append(t_mfe); t_mae_list.append(t_mae)
        mfe = pd.Series(mfe_list)
        mae = pd.Series(mae_list)
        t_mfe = pd.Series(t_mfe_list)
        t_mae = pd.Series(t_mae_list)
        valid_mfe = mfe.notna()
        valid_mae = mae.notna()
        valid_t = t_mfe.notna() & t_mae.notna()
        mfe_avg = mfe[valid_mfe].mean() if valid_mfe.any() else np.nan
        mae_avg = mae[valid_mae].mean() if valid_mae.any() else np.nan
        mfe_med = mfe[valid_mfe].median() if valid_mfe.any() else np.nan
        mae_med = mae[valid_mae].median() if valid_mae.any() else np.nan
        t_mfe_med = t_mfe[valid_t].median() if valid_t.any() else np.nan
        t_mae_med = t_mae[valid_t].median() if valid_t.any() else np.nan
        print(f"--- {label}: n={len(sub)} ---")
        print(f"  MFE (20 bars): avg={mfe_avg:.2f}%  median={mfe_med:.2f}%")
        print(f"  MAE (20 bars): avg={mae_avg:.2f}%  median={mae_med:.2f}%")
        print(f"  time_to_MFE (bar): median={t_mfe_med:.0f}  |  time_to_MAE (bar): median={t_mae_med:.0f}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
