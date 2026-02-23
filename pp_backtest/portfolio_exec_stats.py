"""
portfolio_exec_stats.py  [v2 — stress test + time-weighted exposure]
=====================================================================
Replay K=5 FIFO selection (same logic as portfolio_sim),
collect the executed subset, compute:
  - PF_exec      (PF on executed trades only)
  - EV_exec      (mean return of executed trades)
  - median_exec  (median return of executed trades)
  - exposure_tw  (time-weighted: slot-weeks used / total slot-weeks)

Cost stress test: --stress runs RT30/40/60 in one shot.

Usage:
    # Base only
    python -m pp_backtest.portfolio_exec_stats pp_backtest/pp_weekly_ledger.csv

    # Single fee level
    python -m pp_backtest.portfolio_exec_stats pp_backtest/pp_weekly_ledger.csv --fee-bps 40

    # Full stress test (RT30 / RT40 / RT60)
    python -m pp_backtest.portfolio_exec_stats pp_backtest/pp_weekly_ledger.csv --stress
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Base cost already embedded in ledger returns (match run_weekly FEE_BPS)
BASE_FEE_BPS = 30


def week_end(d: pd.Timestamp) -> pd.Timestamp:
    dof = d.dayofweek
    if dof <= 4:
        return d + pd.Timedelta(days=4 - dof)
    return d - pd.Timedelta(days=dof - 4)


def replay_k5(df: pd.DataFrame, K: int, extra_fee: float = 0.0) -> tuple[list[dict], list[tuple]]:
    """
    Replay FIFO K-slot selection.
    extra_fee: additional cost per trade as decimal (e.g. 0.001 for 10bps).

    Returns:
        trades_taken : list of executed trade dicts (ret after extra_fee applied)
        week_slots   : list of (week, slots_used) for time-weighted exposure
    """
    df = df.sort_values(["entry_week", "symbol"]).reset_index(drop=True)
    weeks = sorted(set(df["entry_week"].tolist() + df["exit_week"].tolist()))

    open_slots = K
    open_positions: list[dict] = []
    trades_taken: list[dict] = []
    week_slots: list[tuple] = []
    idx = 0
    n = len(df)

    for w in weeks:
        exiting = [p for p in open_positions if p["exit_week"] <= w]
        for p in exiting:
            open_positions.remove(p)
            open_slots += 1

        week_slots.append((w, K - open_slots))

        while idx < n and df.iloc[idx]["entry_week"] <= w:
            row = df.iloc[idx]
            idx += 1
            if row["entry_week"] == w and open_slots > 0:
                ret_adj = float(row["ret"]) - extra_fee
                rec = {
                    "symbol": row["symbol"],
                    "entry_week": row["entry_week"],
                    "exit_week": row["exit_week"],
                    "ret": ret_adj,
                }
                open_positions.append(rec)
                trades_taken.append(rec)
                open_slots -= 1

    return trades_taken, week_slots


def compute_stats(
    trades_taken: list[dict],
    week_slots: list[tuple],
    K: int,
    label: str,
    n_total: int,
) -> tuple[float, float, float, float] | None:
    rets = np.array([t["ret"] for t in trades_taken], dtype=float)
    n_exec = len(rets)

    if n_exec == 0:
        print(f"  [{label}] No trades executed.")
        return None

    wins = rets[rets > 0].sum()
    losses = rets[rets <= 0].sum()
    pf_exec = (wins / -losses) if losses < 0 else float("nan")
    median_exec = float(np.median(rets))
    ev_exec = float(np.mean(rets))

    total_slot_weeks = len(week_slots) * K
    used_slot_weeks = sum(s for _, s in week_slots)
    exposure_tw = used_slot_weeks / total_slot_weeks if total_slot_weeks > 0 else 0.0

    pf_str = f"{pf_exec:.3f}" if np.isfinite(pf_exec) else "nan"
    print(f"\n  [{label}]")
    print(f"    Executed / Total signals : {n_exec} / {n_total}")
    print(f"    PF_exec                  : {pf_str}")
    print(f"    EV_exec  (mean ret)      : {ev_exec*100:+.2f}%")
    print(f"    Median   (executed)      : {median_exec*100:+.2f}%")
    print(f"    Exposure_tw (time-wtd)   : {exposure_tw*100:.1f}%")
    print(f"    Winners / Losers         : {(rets>0).sum()} / {(rets<=0).sum()}")
    if (rets > 0).any():
        print(f"    Avg win                  : {rets[rets>0].mean()*100:+.2f}%")
    if (rets <= 0).any():
        print(f"    Avg loss                 : {rets[rets<=0].mean()*100:+.2f}%")

    return (pf_exec, ev_exec, median_exec, exposure_tw)


def run(
    ledger_path: str,
    K: int = 5,
    fee_bps: int | None = None,
    stress: bool = False,
) -> None:
    path = Path(ledger_path)
    if not path.exists():
        print(f"[ERROR] Ledger not found: {path}")
        sys.exit(1)

    df = pd.read_csv(path)
    for col in ("entry_date", "exit_date", "ret", "symbol"):
        if col not in df.columns:
            print(f"[ERROR] Missing column: {col}")
            sys.exit(1)

    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    df["entry_week"] = df["entry_date"].apply(week_end)
    df["exit_week"] = df["exit_date"].apply(week_end)

    n_total = len(df)

    print()
    print("=" * 60)
    print(f"Portfolio Exec Stats  (K={K}, base_fee={BASE_FEE_BPS}bps already in ledger)")
    print(f"Ledger : {path.name}  |  Total signals: {n_total}")
    print("=" * 60)

    if stress:
        scenarios = [
            (BASE_FEE_BPS, 0.0, f"RT {BASE_FEE_BPS}bps (base, already in ret)"),
            (40, (40 - BASE_FEE_BPS) / 10000.0, "RT 40bps  (+10bps extra)"),
            (60, (60 - BASE_FEE_BPS) / 10000.0, "RT 60bps  (+30bps extra)"),
        ]
        results: list[tuple[str, tuple[float, float, float, float] | None]] = []
        for total_bps, extra_fee, label in scenarios:
            trades_taken, week_slots = replay_k5(df.copy(), K, extra_fee)
            r = compute_stats(trades_taken, week_slots, K, label, n_total)
            results.append((label, r))

        print()
        print("-" * 60)
        print("STRESS TEST SUMMARY (executed subset)")
        print("-" * 60)
        print(f"  {'Scenario':<38} {'PF_exec':>8} {'EV':>7} {'Exp_tw':>8}")
        for label, r in results:
            if r is not None:
                pf, ev, _med, exp = r
                pf_str = f"{pf:.3f}" if np.isfinite(pf) else " nan"
                print(f"  {label:<38} {pf_str:>8} {ev*100:>+6.2f}% {exp*100:>7.1f}%")

        print()
        print("Decision rule (pre-registered):")
        print("  RT40 PF_exec > 1.15 AND EV > 0 -> pilot ok")
        print("  RT60 PF_exec ~ 1.0  AND EV ~ 0 -> do not scale")
    else:
        total_bps = fee_bps if fee_bps is not None else BASE_FEE_BPS
        extra_fee = (total_bps - BASE_FEE_BPS) / 10000.0
        label = f"RT {total_bps}bps"
        trades_taken, week_slots = replay_k5(df.copy(), K, extra_fee)
        compute_stats(trades_taken, week_slots, K, label, n_total)

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exec-subset stats + cost stress for weekly portfolio sim"
    )
    parser.add_argument("ledger", help="Path to pp_weekly_ledger.csv")
    parser.add_argument("--k", type=int, default=5, help="Max concurrent positions (default 5)")
    parser.add_argument(
        "--fee-bps",
        type=int,
        default=None,
        help="Total RT fee bps to simulate (default: base already in ledger)",
    )
    parser.add_argument("--stress", action="store_true", help="Run RT30 / RT40 / RT60 stress in one shot")
    args = parser.parse_args()
    run(args.ledger, args.k, args.fee_bps, args.stress)


if __name__ == "__main__":
    main()
