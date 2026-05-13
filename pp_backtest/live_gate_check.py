#!/usr/bin/env python3
"""
Live deployment gate check.

Evaluates all approved gates for moving from paper trading to live capital.
Prints pass/fail status per gate and final recommendation.

Gates (from final_go_no_go.md):
  G1. >= 63 trading days of paper trading (3 calendar months)
  G2. >= 20 closed paper trades
  G3. Paper avg_trade_ret >= 4.0%
  G4. Paper hit rate >= 60%
  G5. Execution gap: < 5% of trades with |gap| > 2%
  G6. Drawdown resolution: current NAV within 10% of all-time paper NAV peak

Usage:
    .venv\\Scripts\\python.exe pp_backtest/live_gate_check.py
    .venv\\Scripts\\python.exe pp_backtest/live_gate_check.py --verbose
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

REPO    = Path(__file__).resolve().parents[1]
PT_DIR  = REPO / "data" / "paper_trade"

POSITIONS_CSV = PT_DIR / "positions.csv"
CLOSED_CSV    = PT_DIR / "closed_trades.csv"
NAV_CSV       = PT_DIR / "nav_history.csv"
AUDIT_CSV     = PT_DIR / "execution_audit.csv"

# Gate thresholds
GATE_MIN_DAYS     = 63      # ~3 calendar months of trading days
GATE_MIN_TRADES   = 20
GATE_MIN_AVG_RET  = 0.040   # 4%
GATE_MIN_HIT_RATE = 0.60    # 60%
GATE_MAX_GAP2PCT  = 0.05    # < 5% of fills with |gap| > 2%
GATE_DD_TOLERANCE = 0.10    # NAV within 10% of peak

# Backtest baselines for comparison
BT_AVG_RET  = 0.063         # 6.3% OOS
BT_HIT_RATE = 0.679         # 67.9%
BT_CAGR     = 0.123         # 12.3% (with ema_dist fill)


def load(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        for col in ["date", "entry_date", "exit_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def check_gates(verbose: bool = False) -> dict[str, dict]:
    closed    = load(CLOSED_CSV)
    nav_hist  = load(NAV_CSV)
    audit     = load(AUDIT_CSV)

    gates = {}

    # ── G1: Minimum paper-trade duration ─────────────────────────────────────
    if nav_hist.empty:
        n_days  = 0
        g1_pass = False
        g1_note = "No NAV history found"
    else:
        n_days  = len(nav_hist)
        g1_pass = n_days >= GATE_MIN_DAYS
        first   = nav_hist["date"].min()
        last    = nav_hist["date"].max()
        g1_note = f"{n_days} trading days  ({first.date()} -> {last.date()})"

    gates["G1_min_duration"] = {
        "pass":        g1_pass,
        "value":       n_days,
        "threshold":   GATE_MIN_DAYS,
        "description": f">= {GATE_MIN_DAYS} trading days paper trading",
        "note":        g1_note,
    }

    # ── G2: Minimum closed trades ─────────────────────────────────────────────
    n_trades = len(closed) if not closed.empty else 0
    gates["G2_min_trades"] = {
        "pass":        n_trades >= GATE_MIN_TRADES,
        "value":       n_trades,
        "threshold":   GATE_MIN_TRADES,
        "description": f">= {GATE_MIN_TRADES} closed paper trades",
        "note":        f"{n_trades} closed trades",
    }

    # ── G3: Paper avg_trade_ret ───────────────────────────────────────────────
    if not closed.empty and "net_return" in closed.columns:
        rets    = closed["net_return"].dropna()
        avg_ret = float(rets.mean()) if len(rets) > 0 else np.nan
        g3_pass = (not np.isnan(avg_ret)) and avg_ret >= GATE_MIN_AVG_RET
        g3_note = (f"{avg_ret:.1%} avg  "
                   f"(vs backtest baseline {BT_AVG_RET:.1%}, "
                   f"gate >= {GATE_MIN_AVG_RET:.0%})")
    else:
        avg_ret = np.nan
        g3_pass = False
        g3_note = "No closed trades yet"

    gates["G3_avg_trade_ret"] = {
        "pass":        g3_pass,
        "value":       avg_ret,
        "threshold":   GATE_MIN_AVG_RET,
        "description": f">= {GATE_MIN_AVG_RET:.0%} avg net trade return",
        "note":        g3_note,
    }

    # ── G4: Hit rate ──────────────────────────────────────────────────────────
    if not closed.empty and "net_return" in closed.columns:
        rets     = closed["net_return"].dropna()
        hit_rate = float((rets > 0).mean()) if len(rets) > 0 else np.nan
        g4_pass  = (not np.isnan(hit_rate)) and hit_rate >= GATE_MIN_HIT_RATE
        g4_note  = (f"{hit_rate:.1%} hit rate  "
                    f"(vs backtest {BT_HIT_RATE:.1%}, gate >= {GATE_MIN_HIT_RATE:.0%})")
    else:
        hit_rate = np.nan
        g4_pass  = False
        g4_note  = "No closed trades yet"

    gates["G4_hit_rate"] = {
        "pass":        g4_pass,
        "value":       hit_rate,
        "threshold":   GATE_MIN_HIT_RATE,
        "description": f">= {GATE_MIN_HIT_RATE:.0%} hit rate",
        "note":        g4_note,
    }

    # ── G5: Execution gap ─────────────────────────────────────────────────────
    if not audit.empty and "gap_pct" in audit.columns:
        gaps    = audit["gap_pct"].dropna()
        pct_bad = float((gaps.abs() > 0.02).mean()) if len(gaps) > 0 else np.nan
        g5_pass = (not np.isnan(pct_bad)) and pct_bad < GATE_MAX_GAP2PCT
        g5_note = (f"{pct_bad:.1%} of fills have |gap| > 2%  "
                   f"(gate < {GATE_MAX_GAP2PCT:.0%}, n={len(gaps)})")
    else:
        pct_bad = np.nan
        g5_pass = False
        g5_note = "No execution audit data. Run: execution_audit.py --backtest"

    gates["G5_execution_gap"] = {
        "pass":        g5_pass,
        "value":       pct_bad,
        "threshold":   GATE_MAX_GAP2PCT,
        "description": f"< {GATE_MAX_GAP2PCT:.0%} of trades with |gap| > 2%",
        "note":        g5_note,
    }

    # ── G6: Drawdown resolution ───────────────────────────────────────────────
    if not nav_hist.empty and "nav" in nav_hist.columns:
        nav_vals = nav_hist["nav"].dropna()
        current  = float(nav_vals.iloc[-1])
        peak     = float(nav_vals.max())
        dd_now   = (current - peak) / peak if peak > 0 else 0.0
        g6_pass  = abs(dd_now) <= GATE_DD_TOLERANCE
        g6_note  = (f"NAV={current:.4f}  peak={peak:.4f}  "
                    f"dd={dd_now:.1%}  "
                    f"(gate: within {GATE_DD_TOLERANCE:.0%} of peak)")
    else:
        dd_now   = np.nan
        g6_pass  = False
        g6_note  = "No NAV history"

    gates["G6_drawdown_resolution"] = {
        "pass":        g6_pass,
        "value":       dd_now,
        "threshold":   -GATE_DD_TOLERANCE,
        "description": f"Portfolio within {GATE_DD_TOLERANCE:.0%} of paper peak NAV",
        "note":        g6_note,
    }

    return gates


def recommendation(gates: dict) -> str:
    passed  = [k for k, v in gates.items() if v["pass"]]
    failed  = [k for k, v in gates.items() if not v["pass"]]
    n_pass  = len(passed)
    n_total = len(gates)

    # Hard blocks (all must pass for any live deployment)
    hard_gates = ["G1_min_duration", "G2_min_trades", "G3_avg_trade_ret",
                  "G4_hit_rate", "G6_drawdown_resolution"]
    hard_pass  = all(gates[g]["pass"] for g in hard_gates if g in gates)

    if n_pass == n_total:
        return "READY FOR TINY LIVE PILOT"
    elif hard_pass:
        return "CONDITIONALLY READY — soft gates only remaining; discretionary decision"
    elif n_pass >= 4:
        return "STAY PAPER — close to ready, 1-2 gates remaining"
    else:
        return "STAY PAPER ONLY"


def print_gate_report(gates: dict, verbose: bool) -> None:
    rec = recommendation(gates)
    passed = sum(1 for v in gates.values() if v["pass"])

    print("\n" + "=" * 70)
    print("LIVE DEPLOYMENT GATE CHECK")
    print(f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    for gate_id, g in gates.items():
        status = "[PASS]" if g["pass"] else "[FAIL]"
        print(f"\n  {gate_id}")
        print(f"    Status:    {status}")
        print(f"    Rule:      {g['description']}")
        print(f"    Current:   {g['note']}")
        if verbose and "value" in g:
            val = g["value"]
            thr = g["threshold"]
            if not (isinstance(val, float) and np.isnan(val)):
                print(f"    Value:     {val!r}  (threshold: {thr!r})")

    print("\n" + "=" * 70)
    print(f"  Gates passed:  {passed} / {len(gates)}")
    print(f"\n  RECOMMENDATION:  {rec}")
    print("=" * 70)

    if rec == "STAY PAPER ONLY":
        failed = [k for k, v in gates.items() if not v["pass"]]
        print(f"\n  Blocking gates: {', '.join(failed)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    PT_DIR.mkdir(parents=True, exist_ok=True)
    gates = check_gates(verbose=args.verbose)
    print_gate_report(gates, args.verbose)

    # Save gate status to CSV
    rows = []
    for gate_id, g in gates.items():
        rows.append({
            "gate_id":     gate_id,
            "pass":        g["pass"],
            "description": g["description"],
            "note":        g["note"],
            "checked_at":  datetime.now().isoformat(),
        })
    out = PT_DIR / "live_gate_status.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nGate status saved: {out}")


if __name__ == "__main__":
    main()
