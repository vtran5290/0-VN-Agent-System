# pp_backtest/exit_diagnosis.py — Test 3 overlap + Test 1 hold_cal_days (stratified; no re-attribution)
# Run from repo root: python -m pp_backtest.exit_diagnosis
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = Path(__file__).resolve().parent / "pp_trade_ledger.csv"


def _pf(ser):
    wins = ser[ser > 0].sum()
    losses = ser[ser < 0].sum()
    if losses == 0:
        return float("nan") if wins == 0 else 999.0
    return wins / abs(losses)


def main():
    if not _LEDGER.exists():
        print("Run backtest first: python -m pp_backtest.run")
        return 1
    df = pd.read_csv(_LEDGER)

    for c in ["sell_v4", "sell_mkt_dd", "sell_stk_dd"]:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda x: str(x).lower() == "true")

    def reason_set(row):
        r = []
        if row.get("sell_v4"):
            r.append("SELL_V4")
        if row.get("sell_mkt_dd"):
            r.append("MARKET_DD")
        if row.get("sell_stk_dd"):
            r.append("STOCK_DD")
        return "|".join(r) if r else "NONE"

    df["reason_set"] = df.apply(reason_set, axis=1)
    df["has_mkt_dd"] = df["reason_set"].str.contains("MARKET_DD")
    df["has_stk_dd"] = df["reason_set"].str.contains("STOCK_DD")
    df["multi_reason"] = df["reason_set"].apply(lambda x: x.count("|") >= 1)

    print("=== Reason-set overlap (attribution = exit_reason, priority SELL_V4 > MARKET_DD > STOCK_DD) ===\n")
    for er in ["SELL_V4", "MARKET_DD", "STOCK_DD"]:
        sub = df[df["exit_reason"] == er]
        n = len(sub)
        if n == 0:
            continue
        only_er = sub["reason_set"] == er
        also_mkt = sub["has_mkt_dd"].sum()
        also_stk = sub["has_stk_dd"].sum()
        multi = sub["multi_reason"].sum()
        print(f"--- exit_reason = {er} (n={n}) ---")
        print(f"  Single-reason (only {er}):     {only_er.sum():4d}  ({100*only_er.mean():.1f}%)")
        print(f"  reason_set contains MARKET_DD: {also_mkt:4d}  ({100*sub['has_mkt_dd'].mean():.1f}%)")
        print(f"  reason_set contains STOCK_DD:  {also_stk:4d}  ({100*sub['has_stk_dd'].mean():.1f}%)")
        print(f"  Multi-reason (2+ flags True):   {multi:4d}  ({100*sub['multi_reason'].mean():.1f}%)")
        print(sub["reason_set"].value_counts().head(10).to_string())
        print()
    print("=== Overlap matrix (count by exit_reason x reason_set) ===")
    cross = pd.crosstab(df["exit_reason"], df["reason_set"])
    print(cross.to_string())

    # Stratified groups (no re-attribution; keep exit_reason as decision reality)
    strata = [
        ("SELL_V4 single", (df["exit_reason"] == "SELL_V4") & (df["reason_set"] == "SELL_V4")),
        ("SELL_V4 multi", (df["exit_reason"] == "SELL_V4") & df["multi_reason"]),
        ("MARKET_DD single", (df["exit_reason"] == "MARKET_DD") & (df["reason_set"] == "MARKET_DD")),
        ("MARKET_DD overlap", (df["exit_reason"] == "MARKET_DD") & (df["reason_set"] == "MARKET_DD|STOCK_DD")),
        ("STOCK_DD", (df["exit_reason"] == "STOCK_DD")),
    ]
    hcol = "hold_cal_days" if "hold_cal_days" in df.columns else "hold_days"
    print(f"\n=== Test 1: {hcol}.describe() by stratum (stratify, no re-attribute) ===")
    for label, mask in strata:
        sub = df.loc[mask]
        if len(sub) == 0:
            print(f"\n--- {label}: n=0 ---")
            continue
        h = sub[hcol].dropna()
        wr = (sub["ret"] > 0).mean()
        pf = _pf(sub["ret"])
        avg_ret = sub["ret"].mean()
        print(f"\n--- {label}: n={len(sub)} | win_rate={wr:.2%} | avg_ret={avg_ret:.4f} | PF={pf:.3f} ---")
        print(h.describe().to_string())

    # hold_cal_days == 1 anomaly (bắt buộc trước khi quyết định soften)
    one_day = df[df[hcol] == 1]
    if len(one_day) > 0:
        print(f"\n=== {hcol} == 1 (anomaly: entry today, exit next day) ===")
        print("ret.describe():")
        print(one_day["ret"].describe().to_string())
        print("\nret by exit_reason (count, mean, median):")
        print(one_day.groupby("exit_reason")["ret"].agg(["count", "mean", "median"]).round(6).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
